from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_multichannel_video import render_video_payload, send_video_once


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content" / "telegram" / "channels" / "milovi-cake.json"
NOW = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
CHAT_ID = -1002215328390
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"


def _profile():
    return load_channel_profile(PROFILE_PATH).model_copy(update={"provider_writes_authorized": True})


def _target(profile) -> GenericTargetProof:
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=BOT_ID,
        bot_username=BOT_USERNAME,
        chat_id=CHAT_ID,
        chat_username="MiloviCake",
        chat_title="Milovi Cake",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=NOW,
    )


def _payload(profile, media: bytes):
    return render_video_payload(
        profile,
        publication_id="milovi-feed-20990101-001",
        caption="Точный проверенный видео-пост",
        media_path=".runtime/test-video.mp4",
        media_sha256="sha256:" + hashlib.sha256(media).hexdigest(),
        media_byte_size=len(media),
        media_filename="milovi-v01.mp4",
    )


def _result(payload) -> dict[str, Any]:
    return {
        "ok": True,
        "result": {
            "message_id": 91,
            "chat": {"id": CHAT_ID, "username": "MiloviCake", "type": "channel"},
            "caption": payload.caption,
            "video": {"file_id": "video-contract-test", "mime_type": "video/mp4"},
        },
    }


def test_video_payload_is_deterministic_and_exact_byte_bound() -> None:
    profile = _profile()
    media = b"fake-mp4-contract-bytes"

    first = _payload(profile, media)
    second = _payload(profile, media)

    assert first == second
    assert first.media_mime_type == "video/mp4"
    assert first.supports_streaming is True
    assert first.media_sha256 == "sha256:" + hashlib.sha256(media).hexdigest()


def test_video_payload_rejects_non_mp4_or_parent_traversal() -> None:
    profile = _profile()
    digest = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="MP4 path"):
        render_video_payload(
            profile,
            publication_id="milovi-feed-20990101-001",
            caption="Точный пост",
            media_path=".runtime/video.webm",
            media_sha256=digest,
            media_byte_size=10,
            media_filename="video.mp4",
        )

    with pytest.raises(ValueError, match="parent traversal"):
        render_video_payload(
            profile,
            publication_id="milovi-feed-20990101-001",
            caption="Точный пост",
            media_path="../video.mp4",
            media_sha256=digest,
            media_byte_size=10,
            media_filename="video.mp4",
        )


def test_send_video_once_uses_one_exact_multipart_sendvideo_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path(".runtime").mkdir()
    media = b"fake-mp4-contract-bytes"
    Path(".runtime/test-video.mp4").write_bytes(media)
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile, media)
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_result(payload), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        receipt = send_video_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert receipt.message_id == 91
    assert receipt.provider_effect == "verified"
    assert len(captured) == 1
    request = captured[0]
    assert request.url.path.endswith("/bottest-token/sendVideo")
    assert request.headers["content-type"].startswith("multipart/form-data;")
    assert b'milovi-v01.mp4' in request.content
    assert media in request.content
    assert payload.caption.encode("utf-8") in request.content
    assert b'name="supports_streaming"' in request.content
    assert b"true" in request.content


def test_send_video_once_rejects_media_drift_before_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path(".runtime").mkdir()
    reviewed = b"reviewed-bytes"
    Path(".runtime/test-video.mp4").write_bytes(b"drifted-bytes")
    profile = _profile()
    target = _target(profile)
    payload = _payload(profile, reviewed)
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="byte-size|SHA-256"):
            send_video_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert called is False
