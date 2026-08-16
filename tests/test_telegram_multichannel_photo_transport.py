from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import (
    GenericTargetProof,
    TelegramApiError,
    preflight_channel,
    render_photo_payload,
    send_photo_once,
)

ROOT = Path(__file__).resolve().parents[1]
SVODKA_PROFILE = ROOT / "content/telegram/channels/svodka.json"
CHAT_ID = -1003527567039
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
NOW = datetime(2026, 8, 16, 16, 0, tzinfo=UTC)


def _profile():
    return load_channel_profile(SVODKA_PROFILE).model_copy(update={"provider_writes_authorized": True})


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
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=NOW,
    )


def _photo_payload(profile, media_path: Path, media: bytes):
    return render_photo_payload(
        profile,
        publication_id="svodka-photo-contract-test",
        caption="Точный caption для photo transport.",
        media_path=str(media_path),
        media_sha256="sha256:" + hashlib.sha256(media).hexdigest(),
        media_byte_size=len(media),
        media_filename="proof.jpg",
    )


def _photo_result(
    payload,
    *,
    caption: str | None = None,
    photo: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": {
            "message_id": 91,
            "chat": {"id": CHAT_ID, "username": "deep_info_life", "type": "channel"},
            "caption": payload.caption if caption is None else caption,
            "photo": (
                [{"file_id": "exact-provider-photo", "width": 100, "height": 100}]
                if photo is None
                else photo
            ),
        },
    }


def _write_relative_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    media: bytes,
) -> Path:
    monkeypatch.chdir(tmp_path)
    media_path = Path("proof.jpg")
    media_path.write_bytes(media)
    return media_path


def test_render_photo_payload_binds_exact_media_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    media = b"exact-jpeg-bytes-for-contract"
    media_path = _write_relative_media(tmp_path, monkeypatch, media)
    payload = _photo_payload(profile, media_path, media)

    changed = render_photo_payload(
        profile,
        publication_id=payload.publication_id,
        caption=payload.caption + "x",
        media_path=str(media_path),
        media_sha256=payload.media_sha256,
        media_byte_size=payload.media_byte_size,
        media_filename=payload.media_filename,
    )
    assert payload.provider_payload_sha256 != changed.provider_payload_sha256
    assert payload.media_sha256.endswith(hashlib.sha256(media).hexdigest())


def test_send_photo_once_uses_single_multipart_mutation_with_exact_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    target = _target(profile)
    media = b"exact-jpeg-bytes-for-send"
    media_path = _write_relative_media(tmp_path, monkeypatch, media)
    payload = _photo_payload(profile, media_path, media)
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        body = request.content
        assert b'name="chat_id"' in body
        assert str(CHAT_ID).encode() in body
        assert b'name="caption"' in body
        assert payload.caption.encode("utf-8") in body
        assert b'filename="proof.jpg"' in body
        assert media in body
        return httpx.Response(200, json=_photo_result(payload), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        receipt = send_photo_once(profile, target, payload, token="test-token", client=client, now=NOW)

    assert len(captured) == 1
    assert captured[0].url.path.endswith("/bottest-token/sendPhoto")
    assert receipt.message_id == 91
    assert receipt.provider_effect == "verified"


def test_send_photo_once_rejects_local_media_drift_before_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    target = _target(profile)
    reviewed = b"reviewed-media"
    media_path = _write_relative_media(tmp_path, monkeypatch, reviewed)
    payload = _photo_payload(profile, media_path, reviewed)
    media_path.write_bytes(b"mutated-media")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"ok": False}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="byte-size|SHA-256"):
            send_photo_once(profile, target, payload, token="test-token", client=client, now=NOW)
    assert calls == 0


def test_send_photo_once_marks_returned_caption_drift_as_ambiguous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    target = _target(profile)
    media = b"media"
    media_path = _write_relative_media(tmp_path, monkeypatch, media)
    payload = _photo_payload(profile, media_path, media)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_photo_result(payload, caption="wrong"), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError, match="caption") as exc_info:
            send_photo_once(profile, target, payload, token="test-token", client=client, now=NOW)
    assert exc_info.value.provider_effect == "may_exist"


def test_send_photo_once_marks_missing_photo_echo_as_ambiguous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    target = _target(profile)
    media = b"media"
    media_path = _write_relative_media(tmp_path, monkeypatch, media)
    payload = _photo_payload(profile, media_path, media)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_photo_result(payload, photo=[]), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError, match="without photo data") as exc_info:
            send_photo_once(profile, target, payload, token="test-token", client=client, now=NOW)
    assert exc_info.value.provider_effect == "may_exist"


def test_send_photo_once_does_not_retry_telegram_5xx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    target = _target(profile)
    media = b"media"
    media_path = _write_relative_media(tmp_path, monkeypatch, media)
    payload = _photo_payload(profile, media_path, media)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            503,
            json={"ok": False, "error_code": 503, "description": "upstream"},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError) as exc_info:
            send_photo_once(profile, target, payload, token="test-token", client=client, now=NOW)
    assert calls == 1
    assert exc_info.value.provider_effect == "may_exist"
    assert exc_info.value.retryable is False


def test_preflight_uses_exact_get_chat_member_for_configured_bot() -> None:
    profile = _profile()
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        methods.append(method)
        payload = json.loads(request.content.decode("utf-8"))
        if method == "getMe":
            body = {"ok": True, "result": {"id": BOT_ID, "is_bot": True, "username": BOT_USERNAME}}
        elif method == "getChat":
            assert payload["chat_id"] in {CHAT_ID, "@deep_info_life"}
            body = {
                "ok": True,
                "result": {
                    "id": CHAT_ID,
                    "username": "deep_info_life",
                    "title": "СВОДКА",
                    "type": "channel",
                },
            }
        elif method == "getChatMember":
            assert payload == {"chat_id": CHAT_ID, "user_id": BOT_ID}
            body = {
                "ok": True,
                "result": {
                    "status": "administrator",
                    "user": {"id": BOT_ID, "is_bot": True, "username": BOT_USERNAME},
                    "can_post_messages": True,
                },
            }
        else:
            raise AssertionError(f"unexpected Telegram method: {method}")
        return httpx.Response(200, json=body, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        proof = preflight_channel(
            profile,
            token="test-token",
            expected_chat_id=CHAT_ID,
            expected_bot_id=BOT_ID,
            expected_bot_username=BOT_USERNAME,
            client=client,
            now=NOW,
        )

    assert methods == ["getMe", "getChat", "getChat", "getChatMember"]
    assert proof.bot_id == BOT_ID
    assert proof.member_status == "administrator"
    assert proof.can_post_messages is True


def test_preflight_rejects_get_chat_member_identity_drift() -> None:
    profile = _profile()

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getMe":
            body = {"ok": True, "result": {"id": BOT_ID, "is_bot": True, "username": BOT_USERNAME}}
        elif method == "getChat":
            body = {
                "ok": True,
                "result": {
                    "id": CHAT_ID,
                    "username": "deep_info_life",
                    "title": "СВОДКА",
                    "type": "channel",
                },
            }
        else:
            body = {
                "ok": True,
                "result": {
                    "status": "administrator",
                    "user": {"id": BOT_ID + 1, "is_bot": True, "username": BOT_USERNAME},
                    "can_post_messages": True,
                },
            }
        return httpx.Response(200, json=body, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError, match="different bot") as exc_info:
            preflight_channel(
                profile,
                token="test-token",
                expected_chat_id=CHAT_ID,
                expected_bot_id=BOT_ID,
                expected_bot_username=BOT_USERNAME,
                client=client,
                now=NOW,
            )
    assert exc_info.value.provider_effect == "not_dispatched"
