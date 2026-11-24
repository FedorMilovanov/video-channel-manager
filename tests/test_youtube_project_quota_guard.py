from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from video_channel_manager.platforms.http import HttpOperationClass, RetryPolicy, execute_http_request
from video_channel_manager.platforms.youtube.client import YouTubeApiClient, YouTubeApiError
from video_channel_manager.platforms.youtube.comments import YouTubeCommentWriter, YouTubeCommentError
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import YOUTUBE_FORCE_SSL_SCOPE
from video_channel_manager.platforms.youtube.store import (
    ProjectQuotaGuard,
    TokenStore,
    YouTubeQuotaBlocked,
    quota_exhaustion_reason,
)
from video_channel_manager.platforms.youtube.writer import YouTubeDescriptionWriter, YouTubeWriteError
from video_channel_manager.youtube_release_provider import YouTubeReleaseProvider, YouTubeReleaseProviderError


def _rejection(reason: str) -> httpx.Response:
    return httpx.Response(403, json={"error": {"message": "Rejected", "errors": [{"reason": reason}]}})


@pytest.mark.parametrize("reason", ["quotaExceeded", "dailyLimitExceeded"])
def test_project_stop_survives_new_instances_and_resets_at_pacific_midnight(tmp_path: Path, reason: str) -> None:
    now = datetime(2026, 11, 24, 7, 59, tzinfo=UTC)
    first = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "poet", now=lambda: now)
    second = ProjectQuotaGuard(first.path, "lord-god", now=lambda: now)
    assert first(lambda: _rejection(reason), "GET", "videos").status_code == 403
    with pytest.raises(YouTubeQuotaBlocked, match="2026-11-23"):
        second(lambda: pytest.fail("blocked request reached HTTP"), "PUT", "videos")
    now += timedelta(minutes=1)
    assert second(lambda: httpx.Response(200), "GET", "videos").status_code == 200
    with closing(sqlite3.connect(first.path)) as db:
        assert db.execute("SELECT day, account, count FROM attempts ORDER BY day").fetchall() == [
            ("2026-11-23", "poet", 1),
            ("2026-11-24", "lord-god", 1),
        ]


@pytest.mark.parametrize("reason", ["userRateLimitExceeded", "rateLimitExceeded", "insufficientPermissions", "forbidden"])
def test_nonquota_rejection_does_not_stop_project(tmp_path: Path, reason: str) -> None:
    guard = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "poet")
    assert guard(lambda: _rejection(reason), "GET", "videos").status_code == 403
    assert guard(lambda: httpx.Response(200), "GET", "videos").status_code == 200


def test_reason_detection_is_narrow() -> None:
    assert quota_exhaustion_reason(httpx.Response(429)) is None
    assert quota_exhaustion_reason(httpx.Response(403, text="invalid JSON")) is None
    assert quota_exhaustion_reason(httpx.Response(403, json=[])) is None
    assert quota_exhaustion_reason(httpx.Response(403, json={"error": {"message": "quota text"}})) is None
    assert quota_exhaustion_reason(
        httpx.Response(403, json={"error": {"message": "You have exceeded your quota."}})
    ) == "quotaExceeded"


def test_project_key_is_not_the_alias_or_oauth_client(tmp_path: Path) -> None:
    a = ProjectQuotaGuard.for_client(tmp_path, "123-abc.apps.googleusercontent.com", "poet")
    b = ProjectQuotaGuard.for_client(tmp_path, "123-def.apps.googleusercontent.com", "milovi")
    c = ProjectQuotaGuard.for_client(tmp_path, "456-abc.apps.googleusercontent.com", "poet")
    assert a is not None and b is not None and c is not None
    assert a.path == b.path != c.path
    assert ProjectQuotaGuard.for_client(tmp_path, "fake-client", "poet") is None
    with pytest.raises(YouTubeQuotaBlocked):
        ProjectQuotaGuard.for_client(None, "123-abc.apps.googleusercontent.com", "poet")


def test_concurrent_admissions_are_atomic_and_failed_attempts_are_counted(tmp_path: Path) -> None:
    path = tmp_path / "quota.sqlite3"

    def run(i: int) -> int:
        guard = ProjectQuotaGuard(path, f"channel-{i % 3}")
        return guard(lambda: httpx.Response(500), "GET", "videos").status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(run, range(30))) == [500] * 30
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT SUM(count) FROM attempts").fetchone()[0] == 30


def test_safe_read_retry_records_each_attempt_and_mutations_still_have_one_attempt(tmp_path: Path) -> None:
    guard = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "poet")
    responses = iter([httpx.Response(503), httpx.Response(200), httpx.Response(503)])
    for operation, expected in [(HttpOperationClass.SAFE_READ, 2), (HttpOperationClass.AMBIGUOUS_MUTATION, 1)]:
        result = execute_http_request(
            lambda: next(responses),
            provider="YouTube",
            operation=operation,
            method="GET" if operation is HttpOperationClass.SAFE_READ else "PUT",
            resource="videos",
            retry_policy=RetryPolicy(max_attempts=2),
            sleep=lambda _: None,
            attempt_guard=guard,
        )
        assert result.attempts == expected
    with closing(sqlite3.connect(guard.path)) as db:
        assert db.execute("SELECT SUM(count) FROM attempts").fetchone()[0] == 3


def test_unavailable_ledger_fails_closed_before_http(tmp_path: Path) -> None:
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("file", encoding="utf-8")
    guard = ProjectQuotaGuard(blocked / "quota.sqlite3", "poet")
    with pytest.raises(YouTubeQuotaBlocked, match="ledger unavailable"):
        guard(lambda: pytest.fail("ledger failure must not dispatch"), "GET", "videos")


def test_real_client_path_stops_other_canonical_adapters_without_provider_calls(tmp_path: Path) -> None:
    store = TokenStore(tmp_path)
    for alias in ("poet", "lord-god", "milovi"):
        store.save_token(
            alias,
            OAuthToken(
                access_token="fake",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                scopes=[YOUTUBE_FORCE_SSL_SCOPE],
            ),
        )
    config = InstalledClientConfig(client_id="123-abc.apps.googleusercontent.com", client_secret="fake")
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.method)
        return _rejection("quotaExceeded")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        reader = YouTubeApiClient(client_config=config, token_store=store, account_alias="poet", http_client=http)
        with pytest.raises(YouTubeApiError):
            reader.get_video("example-id")
        writer = YouTubeDescriptionWriter(
            client_config=config, token_store=store, account_alias="lord-god", http_client=http
        )
        with pytest.raises(YouTubeWriteError, match="no dispatch"):
            writer.read_description("example-id")
        comments = YouTubeCommentWriter(
            client_config=config, token_store=store, account_alias="milovi", http_client=http
        )
        with pytest.raises(YouTubeCommentError, match="no dispatch"):
            comments.read_video_identity("example-id")
        release = YouTubeReleaseProvider(
            client_config=config, token_store=store, account_alias="milovi", http_client=http
        )
        with pytest.raises(YouTubeReleaseProviderError, match="no dispatch"):
            release.read_video("example-id")
        result = release.update_metadata_status(video_id="example-id", snippet={}, status={})
        assert result.provider_effect == "confirmed_absent"
        assert "quota_blocked" in result.evidence
        status = release.query_upload_status(
            session_url="https://www.googleapis.com/upload/youtube/v3/videos?upload_id=example",
            media_size_bytes=100,
        )
        assert status.provider_effect == "may_exist"
        assert "status_query_quota_blocked" in status.evidence
    assert requests == ["GET"]
