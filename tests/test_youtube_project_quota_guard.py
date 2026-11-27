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
    quota_cost,
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


@pytest.mark.parametrize(
    "reason", ["userRateLimitExceeded", "rateLimitExceeded", "insufficientPermissions", "forbidden"]
)
def test_nonquota_rejection_does_not_stop_project(tmp_path: Path, reason: str) -> None:
    guard = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "poet")
    assert guard(lambda: _rejection(reason), "GET", "videos").status_code == 403
    assert guard(lambda: httpx.Response(200), "GET", "videos").status_code == 200


def test_reason_detection_is_narrow() -> None:
    assert quota_exhaustion_reason(httpx.Response(429)) is None
    assert quota_exhaustion_reason(httpx.Response(403, text="invalid JSON")) is None
    assert quota_exhaustion_reason(httpx.Response(403, json=[])) is None
    assert quota_exhaustion_reason(httpx.Response(403, json={"error": {"message": "quota text"}})) is None
    assert (
        quota_exhaustion_reason(httpx.Response(403, json={"error": {"message": "You have exceeded your quota."}}))
        == "quotaExceeded"
    )


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


@pytest.mark.parametrize("mode", ["ok", "foreign", "missing", "duplicate"])
def test_recent_candidates_are_bounded_and_channel_bound(tmp_path: Path, mode: str) -> None:
    store = TokenStore(tmp_path)
    store.save_token("poet", OAuthToken(access_token="fake", expires_at=datetime.now(UTC) + timedelta(hours=1)))
    config = InstalledClientConfig(client_id="fake", client_secret="fake")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        resource = request.url.path.rsplit("/", 1)[-1]
        calls.append(resource)
        assert "pageToken" not in request.url.params
        if resource == "channels":
            return httpx.Response(
                200, json={"items": [{"id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
            )
        if resource == "playlistItems":
            assert request.url.params["maxResults"] == "2"
            return httpx.Response(
                200,
                json={
                    "items": [{"contentDetails": {"videoId": value}} for value in ("A", "B")],
                    "nextPageToken": "must-not-follow",
                },
            )
        assert resource == "videos" and request.url.params["id"] == "A,B"
        ids = {"ok": ["B", "A"], "foreign": ["A", "B"], "missing": ["A"], "duplicate": ["A", "A"]}[mode]
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": value,
                        "snippet": {"channelId": "UC2" if mode == "foreign" else "UC1", "title": value},
                        "contentDetails": {"duration": "PT10S"},
                        "fileDetails": {"fileName": f"{value}.mp4"},
                    }
                    for value in ids
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = YouTubeApiClient(client_config=config, token_store=store, account_alias="poet", http_client=http)
        if mode == "ok":
            records = client.list_recent_videos("UC1", limit=2)
            assert [item.ref.remote_id for item in records] == ["A", "B"]
            assert records[0].metadata["fileDetails"]["fileName"] == "A.mp4"
        else:
            with pytest.raises(YouTubeApiError):
                client.list_recent_videos("UC1", limit=2)
    assert calls == ["channels", "playlistItems", "videos"]


@pytest.mark.parametrize(
    "method,resource,expected",
    [
        ("GET", "videos", ("shared", 1)),
        ("PUT", "videos", ("shared", 50)),
        ("PUT", "playlists", ("shared", 50)),
        ("PUT", "playlists.update", ("shared", 50)),
        ("POST", "commentThreads", ("shared", 50)),
        ("GET", "captions", ("shared", 50)),
        ("POST", "captions.insert", ("shared", 400)),
        ("PUT", "captions.update", ("shared", 450)),
        ("GET", "captions.download", ("shared", 200)),
        ("GET", "search", ("search", 1)),
        ("POST", "videos.insert.resumable-session", ("uploads", 1)),
        ("PUT", "videos.insert.resumable-status", ("uploads", 1)),
        ("GET", "unknown", None),
    ],
)
def test_weighted_method_costs(method: str, resource: str, expected: tuple[str, int] | None) -> None:
    assert quota_cost(method, resource) == expected


def test_local_allowance_reserves_postflight_against_another_channel(tmp_path: Path) -> None:
    first = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "poet")
    second = ProjectQuotaGuard(first.path, "lord-god")
    day = first.budget_status()["pacific_day"]
    assert isinstance(day, str)
    first.configure_day(day=day, allowances={"shared": 55, "search": 1, "uploads": 0}, evidence="reviewed console")
    with first.reserve(54):
        assert first(lambda: httpx.Response(200), "PUT", "videos").status_code == 200
        assert second(lambda: httpx.Response(200), "GET", "videos").status_code == 200
        with pytest.raises(YouTubeQuotaBlocked, match="allowance exhausted"):
            second(lambda: pytest.fail("reserved postflight allowance was stolen"), "GET", "videos")
        with first.reserve(4):
            assert first(lambda: httpx.Response(200), "GET", "videos").status_code == 200
        assert second(lambda: httpx.Response(200), "GET", "search").status_code == 200
        with pytest.raises(YouTubeQuotaBlocked, match="allowance exhausted"):
            second(lambda: pytest.fail("search bucket exhausted"), "GET", "search")
    assert second(lambda: httpx.Response(200), "GET", "videos").status_code == 200
    with pytest.raises(YouTubeQuotaBlocked, match="Unpriced"):
        second(lambda: pytest.fail("unknown method under configured policy"), "GET", "unknown")
    with pytest.raises(ValueError, match="already configured"):
        first.configure_day(day=day, allowances={"shared": 99, "search": 9, "uploads": 9}, evidence="no refill")
    status = first.budget_status()
    assert status["google_remaining"] is None
    assert status["buckets"] == {
        "shared": {"estimated_units": 53, "reserved_units": 0, "local_remaining": 2},
        "search": {"estimated_units": 1, "reserved_units": 0, "local_remaining": 0},
        "uploads": {"estimated_units": 0, "reserved_units": 0, "local_remaining": 0},
    }


def test_allowance_is_additional_to_existing_local_estimates_and_expires(tmp_path: Path) -> None:
    now = datetime(2026, 11, 24, 7, 59, tzinfo=UTC)
    guard = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "poet", now=lambda: now)
    guard(lambda: httpx.Response(200), "PUT", "videos")
    guard(lambda: httpx.Response(200), "GET", "unpriced")
    assert guard.budget_status()["unpriced_attempts"] == 1
    guard.configure_day(
        day="2026-11-23", allowances={"shared": 1, "search": 0, "uploads": 0}, evidence="reviewed console"
    )
    guard(lambda: httpx.Response(200), "GET", "videos")
    with pytest.raises(YouTubeQuotaBlocked, match="allowance exhausted"):
        guard(lambda: pytest.fail("allowance exhausted"), "GET", "videos")
    now += timedelta(minutes=1)
    with pytest.raises(YouTubeQuotaBlocked, match="allowance.*missing"):
        guard(lambda: pytest.fail("stale day"), "GET", "videos")
    guard.configure_day(day="2026-11-24", allowances={"shared": 1, "search": 0, "uploads": 0}, evidence="new day")
    guard(lambda: httpx.Response(200), "GET", "videos")


def test_reservation_failure_releases_unused_units_but_retains_attempts(tmp_path: Path) -> None:
    guard = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "poet")
    day = guard.budget_status()["pacific_day"]
    assert isinstance(day, str)
    guard.configure_day(day=day, allowances={"shared": 50, "search": 0, "uploads": 0}, evidence="console")
    with pytest.raises(httpx.ConnectError):
        with guard.reserve(50):

            def fail() -> httpx.Response:
                raise httpx.ConnectError("synthetic failure")

            guard(fail, "GET", "videos")
    with guard.reserve(49):
        with pytest.raises(YouTubeQuotaBlocked, match="Nested"):
            with guard.reserve(50):
                pytest.fail("nested reservation exceeded")
        with pytest.raises(YouTubeQuotaBlocked, match="day or bucket changed"):
            guard(lambda: pytest.fail("wrong bucket"), "GET", "search")
        with pytest.raises(YouTubeQuotaBlocked, match="reservation exhausted"):
            guard(lambda: pytest.fail("insufficient reservation"), "PUT", "videos")
    assert guard(lambda: httpx.Response(200), "GET", "videos").status_code == 200


def test_concurrent_reservation_cannot_exceed_configured_allowance(tmp_path: Path) -> None:
    from threading import Barrier

    guard = ProjectQuotaGuard(tmp_path / "quota.sqlite3", "operator")
    day = guard.budget_status()["pacific_day"]
    assert isinstance(day, str)
    guard.configure_day(day=day, allowances={"shared": 50, "search": 0, "uploads": 0}, evidence="console")
    barrier = Barrier(2)

    def run(alias: str) -> bool:
        local = ProjectQuotaGuard(guard.path, alias)
        barrier.wait(timeout=5)
        try:
            with local.reserve(50):
                local(lambda: httpx.Response(200), "PUT", "videos")
            return True
        except YouTubeQuotaBlocked:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, ("poet", "lord-god"))) == [False, True]


@pytest.mark.parametrize("allowance,expected_puts", [(54, 0), (55, 1)])
def test_description_reserves_write_and_read_retry_headroom(tmp_path: Path, allowance: int, expected_puts: int) -> None:
    store = TokenStore(tmp_path)
    store.save_token(
        "poet",
        OAuthToken(
            access_token="fake",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=[YOUTUBE_FORCE_SSL_SCOPE],
        ),
    )
    config = InstalledClientConfig(client_id="123-abc.apps.googleusercontent.com", client_secret="fake")
    guard = ProjectQuotaGuard.for_client(tmp_path, config.client_id, "other-channel")
    assert guard is not None
    day = guard.budget_status()["pacific_day"]
    assert isinstance(day, str)
    guard.configure_day(day=day, allowances={"shared": allowance, "search": 0, "uploads": 0}, evidence="console")
    description = "old"
    puts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal description, puts
        if request.method == "PUT":
            puts += 1
            with pytest.raises(YouTubeQuotaBlocked, match="allowance exhausted"):
                guard(lambda: pytest.fail("verification reserve was stolen"), "GET", "videos")
            description = "new"
        item = {
            "id": "video",
            "snippet": {"channelId": "channel", "title": "title", "description": description, "categoryId": "22"},
            "contentDetails": {"duration": "PT10S"},
            "status": {"privacyStatus": "public"},
        }
        return httpx.Response(200, json=item if request.method == "PUT" else {"items": [item]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        writer = YouTubeDescriptionWriter(
            client_config=config, token_store=store, account_alias="poet", http_client=http
        )
        kwargs = {
            "video_id": "video",
            "expected_channel_id": "channel",
            "expected_revision": "reviewed",
            "expected_description": "old",
            "new_description": "new",
        }
        if expected_puts:
            assert writer.replace_description(**kwargs).description == "new"
        else:
            with pytest.raises(YouTubeWriteError, match="allowance exhausted"):
                writer.replace_description(**kwargs)
    assert puts == expected_puts


def test_approved_project_rolls_over_without_daily_operator_action(tmp_path: Path) -> None:
    now = datetime(2026, 11, 25, 7, 59, tzinfo=UTC)
    path = tmp_path / "quota.sqlite3"
    first = ProjectQuotaGuard(path, "lord-god", now=lambda: now, project_number="1067074369047")
    second = ProjectQuotaGuard(path, "poet", now=lambda: now, project_number="1067074369047")
    assert first.budget_status()["approved_grant_active"] is True
    assert first.budget_status()["buckets"]["shared"]["local_remaining"] == 99_000
    first.configure_day(
        day="2026-11-24", allowances={"shared": 1, "search": 0, "uploads": 0}, evidence="tighter console limit"
    )
    with first.reserve(1, require_reviewed=True):
        first(lambda: httpx.Response(200), "GET", "videos")
    with pytest.raises(YouTubeQuotaBlocked, match="allowance exhausted"):
        second.require_reviewed_allowance(1)
    now += timedelta(minutes=1)
    second.require_reviewed_allowance(55)
    with second.reserve(55, require_reviewed=True):
        second(lambda: httpx.Response(200), "PUT", "videos")
        second(lambda: httpx.Response(200), "GET", "videos.list")
    assert first.budget_status()["buckets"]["shared"]["local_remaining"] == 98_949
    assert first.budget_status()["google_remaining"] is None


def test_approved_grant_does_not_override_provider_stop_or_other_projects(tmp_path: Path) -> None:
    now = datetime(2026, 11, 25, 12, tzinfo=UTC)
    guard = ProjectQuotaGuard(tmp_path / "approved.sqlite3", "poet", now=lambda: now, project_number="1067074369047")
    other = ProjectQuotaGuard(tmp_path / "other.sqlite3", "poet", now=lambda: now, project_number="123")
    with pytest.raises(YouTubeQuotaBlocked, match="Reviewed"):
        other.require_reviewed_allowance(1)
    assert guard(lambda: _rejection("quotaExceeded"), "GET", "videos").status_code == 403
    with pytest.raises(YouTubeQuotaBlocked, match="quota blocked"):
        guard.require_reviewed_allowance(1)
    now += timedelta(days=1)
    guard.require_reviewed_allowance(1)
    now = datetime(2027, 5, 24, 12, tzinfo=UTC)
    assert not guard.budget_status()["approved_grant_active"]
    with pytest.raises(YouTubeQuotaBlocked, match="Reviewed"):
        guard.require_reviewed_allowance(1)


def test_approved_grant_bound_to_canonical_oauth_project_and_shared_bucket(tmp_path: Path) -> None:
    guard = ProjectQuotaGuard.for_client(tmp_path, "1067074369047-abc.apps.googleusercontent.com", "milovi")
    assert guard is not None
    guard.now = lambda: datetime(2026, 11, 25, 12, tzinfo=UTC)
    assert guard.budget_status()["approved_grant_active"]
    assert quota_cost("POST", "playlistItems") == ("shared", 50)
    assert quota_cost("GET", "channels.list") == ("shared", 1)
    with guard.reserve(50, require_reviewed=True):
        guard(lambda: httpx.Response(200), "POST", "playlistItems")
    with pytest.raises(YouTubeQuotaBlocked, match="allowance exhausted"):
        with guard.reserve(91, bucket="search"):
            pytest.fail("separate search ceiling must remain enforced")
