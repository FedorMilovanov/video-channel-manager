"""Offline sendAudio contract for the guarded generic Telegram publisher."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_audio import (
    GenericAudioPayload,
    render_audio_payload,
    send_audio_once,
)
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof, TelegramApiError
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/milovi-cake.json"
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
CHAT_ID = -1002215328390
CAPTION = '<b>Михаил Лермонтов</b> · <i>3:08</i>\n🎧 <a href="https://thelegendarypoet.ru/">Слушать</a>'


def _profile(authorized: bool = True):
    return load_channel_profile(PROFILE).model_copy(update={"provider_writes_authorized": authorized})


def _target(profile, checked_at=NOW):
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=8716602202,
        bot_username="fixture_test_bot",
        chat_id=CHAT_ID,
        chat_username="MiloviCake",
        chat_title="Milovi Cake",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=checked_at,
    )


def _payload(profile, audio: bytes, *, caption=CAPTION, thumb: bytes | None = None):
    props: dict[str, Any] = {}
    if thumb is not None:
        props = {
            "thumbnail_path": ".runtime/artwork.jpg",
            "thumbnail_sha256": "sha256:" + hashlib.sha256(thumb).hexdigest(),
            "thumbnail_byte_size": len(thumb),
            "thumbnail_filename": "artwork.jpg",
        }
    return render_audio_payload(
        profile,
        publication_id="milovi-test-audio-20261118",
        caption_html=caption,
        media_path=".runtime/test-song.mp3",
        media_sha256="sha256:" + hashlib.sha256(audio).hexdigest(),
        media_byte_size=len(audio),
        media_filename="original-song.mp3",
        title="Когда волнуется желтеющая нива",
        performer="The Legendary Poet",
        duration=188,
        **props,
    )


def _result(payload, **patch):
    base = {
        "message_id": 891,
        "chat": {"id": CHAT_ID, "username": "MiloviCake", "type": "channel"},
        "caption": payload.expected_plain_caption,
        "caption_entities": [x.model_dump(mode="json", exclude_none=True) for x in payload.expected_caption_entities],
        "audio": {
            "file_id": "original-audio-telegram-id",
            "mime_type": "audio/mpeg",
            "title": payload.title,
            "performer": payload.performer,
            "duration": 188,
        },
    }
    base.update(patch)
    return {"ok": True, "result": base}


def _files(tmp_path, monkeypatch, *, thumbnail: bool = True):
    monkeypatch.chdir(tmp_path)
    Path(".runtime").mkdir()
    audio = b"ID3" + b"\x07" * 1500
    thumb = b"\xff\xd8" + b"test-jpeg-bytes" + b"\xff\xd9" if thumbnail else None
    Path(".runtime/test-song.mp3").write_bytes(audio)
    if thumb is not None:
        Path(".runtime/artwork.jpg").write_bytes(thumb)
    return audio, thumb


def test_audio_payload_deterministic_and_release_union(tmp_path, monkeypatch):
    audio, thumb = _files(tmp_path, monkeypatch)
    profile = _profile(False)
    payload = _payload(profile, audio, thumb=thumb)
    assert payload == _payload(profile, audio, thumb=thumb)
    assert payload.media_sha256 == "sha256:" + hashlib.sha256(audio).hexdigest()
    item = GenericReleaseItem(
        sequence=1,
        publication_id=payload.publication_id,
        scheduled_at=NOW,
        source_sha256="sha256:" + "1" * 64,
        payload=payload.model_dump(mode="json"),
    )
    assert isinstance(item.payload, GenericAudioPayload)
    assert item.payload == payload


def test_send_audio_exact_single_multipart_and_html_entities(tmp_path, monkeypatch):
    audio, thumb = _files(tmp_path, monkeypatch)
    profile = _profile()
    payload = _payload(profile, audio, thumb=thumb)
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, request=request, json=_result(payload))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        receipt = send_audio_once(
            profile,
            _target(profile),
            payload,
            token="test-token",
            client=client,
            now=NOW,
        )
    assert receipt.provider_effect == "verified"
    assert receipt.message_id == 891
    assert len(captured) == 1
    assert captured[0].url.path.endswith("/bottest-token/sendAudio")
    body = captured[0].content
    for expected in [
        b"multipart/form-data",
        b"original-song.mp3",
        b"artwork.jpg",
        b"audio/mpeg",
        b"parse_mode",
        b"HTML",
        b"duration",
        b"188",
        CAPTION.encode("utf-8"),
        audio,
        thumb,
    ]:
        if expected == b"multipart/form-data":
            assert expected in captured[0].headers["content-type"].encode()
        else:
            assert expected in body


def test_unauthorized_profile_never_contacts_provider(tmp_path, monkeypatch):
    audio, thumb = _files(tmp_path, monkeypatch)
    profile = _profile(False)
    payload = _payload(profile, audio, thumb=thumb)
    called = []
    with httpx.Client(transport=httpx.MockTransport(lambda req: called.append(req))) as client:
        with pytest.raises(ValueError, match="not authorized"):
            send_audio_once(profile, _target(profile), payload, token="test", client=client, now=NOW)
    assert not called


def test_rejects_stale_target_without_provider_call(tmp_path, monkeypatch):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    with pytest.raises(ValueError, match="stale"):
        send_audio_once(
            profile,
            _target(profile, NOW - timedelta(hours=3)),
            payload,
            token="test",
            now=NOW,
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: {"caption": "подменённые слова"},
        lambda payload: {"chat": {"id": CHAT_ID - 1, "username": "MiloviCake", "type": "channel"}},
        lambda payload: {"caption_entities": []},
        lambda payload: {"audio": {}},
        lambda payload: {"audio": {"file_id": "x", "mime_type": "video/mp4"}},
        lambda payload: {"audio": {"file_id": "x", "mime_type": "audio/mpeg", "title": "Wrong"}},
    ],
)
def test_ambiguous_provider_echo_is_may_exist_no_second_send(tmp_path, monkeypatch, mutate):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, request=request, json=_result(payload, **mutate(payload)))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError) as error:
            send_audio_once(profile, _target(profile), payload, token="test", client=client, now=NOW)
    assert error.value.provider_effect == "may_exist"
    assert len(requests) == 1


def test_changed_media_digest_fails_before_dispatch(tmp_path, monkeypatch):
    audio, thumb = _files(tmp_path, monkeypatch)
    profile = _profile()
    payload = _payload(profile, audio, thumb=thumb)
    Path(".runtime/test-song.mp3").write_bytes(b"ID3bad-media")
    with pytest.raises(ValueError, match="byte-size"):
        send_audio_once(profile, _target(profile), payload, token="test", now=NOW)


def test_changed_thumbnail_digest_fails_before_dispatch(tmp_path, monkeypatch):
    audio, thumb = _files(tmp_path, monkeypatch)
    profile = _profile()
    payload = _payload(profile, audio, thumb=thumb)
    Path(".runtime/artwork.jpg").write_bytes(b"X" * len(thumb))
    with pytest.raises(ValueError, match="thumbnail SHA-256"):
        send_audio_once(profile, _target(profile), payload, token="test", now=NOW)


def test_tampered_caption_invalidates_frozen_payload(tmp_path, monkeypatch):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    mutated = payload.model_dump(mode="json")
    mutated["caption_html"] = "<b>Подмена</b>"
    with pytest.raises(ValueError, match="caption"):
        GenericAudioPayload.model_validate(mutated)


@pytest.mark.parametrize(
    "media_path,media_filename",
    [
        ("../parent.mp3", "valid.mp3"),
        (".runtime/wrong.wav", "valid.mp3"),
        (".runtime/test-song.mp3", "wrong.wav"),
        ("C:/Users/test-song.mp3", "valid.mp3"),
        ("..\\escape.mp3", "valid.mp3"),
        ("C:\\Users\\test-song.mp3", "valid.mp3"),
    ],
)
def test_non_mp3_or_traversal_is_blocked(tmp_path, monkeypatch, media_path, media_filename):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    with pytest.raises(ValueError):
        render_audio_payload(
            profile,
            publication_id="milovi-test-audio-20261118",
            caption_html=CAPTION,
            media_path=media_path,
            media_sha256="sha256:" + hashlib.sha256(audio).hexdigest(),
            media_byte_size=len(audio),
            media_filename=media_filename,
            title="title",
            performer="artist",
            duration=188,
        )


def test_caption_limit_is_measured_after_html_parse(tmp_path, monkeypatch):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    with pytest.raises(ValueError, match="1024"):
        _payload(profile, audio, caption="<b>" + "а" * 1025 + "</b>")


def test_provider_http_failure_never_retries(tmp_path, monkeypatch):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(500, request=request, json={"ok": False, "description": "Internal Server Error"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError):
            send_audio_once(profile, _target(profile), payload, token="test", client=client, now=NOW)
    assert len(requests) == 1
