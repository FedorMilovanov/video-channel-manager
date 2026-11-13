"""Offline, no-Meta regression tests for the Milovi Cake HTTPS Reel fallback."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from video_channel_manager.instagram.production import InstagramMediaVerificationError

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "prepare_milovi_instagram_https_fallback.py"
)
SPEC = importlib.util.spec_from_file_location("milovi_https_fallback_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

VIDEO = b"fake fixture bytes for pure transport/hash checks"
DAY = "2026-11-14"
YOUTUBE_ID = "fbGZYKS7byM"
HOST = "fedormilovanov.github.io"


@pytest.fixture
def release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "ORIGINAL-MUSIC-REEL.mp4").write_bytes(VIDEO)
    sha = hashlib.sha256(VIDEO).hexdigest()
    key = f"milovi-cake.{DAY}.yt-{YOUTUBE_ID}.original-audio-v1"
    manifest = {
        "publication_key": key,
        "account_id": module.ACCOUNT_ID,
        "media_sha256": f"sha256:{sha}",
        "media_size_bytes": len(VIDEO),
        "caption": "Reviewed original caption",
        "share_to_feed": True,
        "thumb_offset_ms": 1500,
    }
    (folder / "exact-local-publish-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    ack = {
        "publication_key": key,
        "project_key": module.PROJECT,
        "owner_directed_repost": True,
        "caption_editorially_reviewed": True,
    }
    (folder / "OWNER_DIRECTED_RISK_ACCEPTED.json").write_text(
        json.dumps(ack), encoding="utf-8"
    )
    row = {
        "publication_key": key,
        "youtube_id": YOUTUBE_ID,
        "folder": str(folder),
        "media_sha256": sha,
        "proposed_moscow_slot": f"{DAY}T19:00:00",
    }
    index = {
        "project_key": module.PROJECT,
        "target_instagram_id": module.ACCOUNT_ID,
        "meta_app_id": module.APP_ID,
        "rows": [row]
        + [
            {"proposed_moscow_slot": f"2026-11-{n:02d}T19:00:00"}
            for n in range(15, 34)
        ],
    }
    index_path = tmp_path / "frozen.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setattr(
        module, "INDEX_SHA256", hashlib.sha256(index_path.read_bytes()).hexdigest()
    )
    observed_local: list[Path] = []

    def fake_local_validator(path: Path, **kwargs: object) -> None:
        observed_local.append(path)
        assert kwargs["expected_sha256"] == f"sha256:{sha}"
        assert kwargs["expected_size_bytes"] == len(VIDEO)

    monkeypatch.setattr(module, "verify_local_reel", fake_local_validator)
    db = tmp_path / "publications.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE instagram_publications "
            "(publication_key TEXT, account_id TEXT, status TEXT, provider_media_id TEXT)"
        )
    return {
        "index": index_path,
        "db": db,
        "folder": folder,
        "row": row,
        "url": f"https://{HOST}/media/instagram/milovi-cake/{sha}.mp4",
        "calls": observed_local,
    }


def run(
    release: dict[str, object],
    *,
    public_hosting_authorized: bool = True,
    video_url: str | None = None,
    response_bytes: bytes = VIDEO,
) -> tuple[object, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == HOST
        return httpx.Response(
            200,
            request=request,
            content=response_bytes,
            headers={
                "content-type": "video/mp4",
                "content-length": str(len(response_bytes)),
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = module.prepare_verified_manifest(
            index_path=release["index"],
            database_path=release["db"],
            day=DAY,
            video_url=video_url or release["url"],
            allowed_host=HOST,
            public_hosting_authorized=public_hosting_authorized,
            media_client=client,
        )
    return result, requests


def test_valid_media_is_bound_to_distinct_new_key_and_get_only(release: dict[str, object]) -> None:
    manifest, requests = run(release)
    assert manifest.publication_key == f"milovi-cake.{DAY}.yt-{YOUTUBE_ID}.public-https-v1"
    assert manifest.account_id == module.ACCOUNT_ID
    assert manifest.caption == "Reviewed original caption"
    assert manifest.share_to_feed is True
    assert manifest.thumb_offset_ms == 1500
    assert len(requests) == 1 and requests[0].method == "GET"
    assert release["calls"] == [release["folder"] / "ORIGINAL-MUSIC-REEL.mp4"]


def test_public_staging_must_be_separately_authorized(release: dict[str, object]) -> None:
    with pytest.raises(module.FallbackHold, match="Separate owner authorization"):
        run(release, public_hosting_authorized=False)
    assert release["calls"] == []


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://fedormilovanov.github.io/media/instagram/milovi-cake/abc.mp4",
        "https://evil.example/media/instagram/milovi-cake/abc.mp4",
        "https://fedormilovanov.github.io/media/instagram/milovi-cake/abc.mp4",
        "https://fedormilovanov.github.io/media/instagram/milovi-cake/abc.mp4?token=x",
    ],
)
def test_wrong_url_is_refused_without_host_fetch(
    release: dict[str, object], bad_url: str
) -> None:
    with pytest.raises(module.FallbackHold, match="content-addressed"):
        run(release, video_url=bad_url)


def test_remote_bytes_have_to_match_the_frozen_source(release: dict[str, object]) -> None:
    with pytest.raises(InstagramMediaVerificationError, match="size mismatch"):
        run(release, response_bytes=VIDEO[:-1])


def test_existing_attempt_blocks_new_key_even_when_provider_media_id_is_null(
    release: dict[str, object],
) -> None:
    with sqlite3.connect(release["db"]) as conn:
        conn.execute(
            "INSERT INTO instagram_publications VALUES (?, ?, ?, ?)",
            (
                f"milovi-cake.{DAY}.yt-{YOUTUBE_ID}.original-audio-v1",
                module.ACCOUNT_ID,
                "terminal_failure",
                None,
            ),
        )
    with pytest.raises(module.FallbackHold, match="reconcile manually"):
        run(release)


def test_frozen_index_digest_is_mandatory(release: dict[str, object]) -> None:
    release["index"].write_text("{}", encoding="utf-8")
    with pytest.raises(module.FallbackHold, match="index SHA-256 mismatch"):
        run(release)


def test_mutated_local_bytes_are_blocked_before_remote_get(release: dict[str, object]) -> None:
    path = release["folder"] / "ORIGINAL-MUSIC-REEL.mp4"
    path.write_bytes(b"X" + VIDEO[1:])
    with pytest.raises(module.FallbackHold, match="Original source bytes"):
        run(release)


def test_historical_day_is_never_eligible(release: dict[str, object]) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda req: None)) as client:
        with pytest.raises(module.FallbackHold, match="Only unused future"):
            module.prepare_verified_manifest(
                index_path=release["index"],
                database_path=release["db"],
                day="2026-11-13",
                video_url=release["url"],
                allowed_host=HOST,
                public_hosting_authorized=True,
                media_client=client,
            )


def test_underscore_in_youtube_id_is_not_a_sql_like_wildcard(
    release: dict[str, object],
) -> None:
    with sqlite3.connect(release["db"]) as conn:
        conn.execute(
            "INSERT INTO instagram_publications VALUES (?, ?, ?, ?)",
            (
                "milovi-cake.2026-11-16.yt-1XSuzeQD_1g.original-audio-v1",
                module.ACCOUNT_ID,
                "published",
                "12345",
            ),
        )
    module._require_unused_source(release["db"], "1_SuzeQD_1g")
    with pytest.raises(module.FallbackHold, match="reconcile manually"):
        module._require_unused_source(release["db"], "1XSuzeQD_1g")
