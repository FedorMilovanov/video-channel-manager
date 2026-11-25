"""Offline sendAudio contract for the guarded generic Telegram publisher."""

from __future__ import annotations

import hashlib
import subprocess
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
from video_channel_manager.telegram_multichannel_cli import _require_current_audio_state, _send_persisted_once
from video_channel_manager.telegram_multichannel_outcome import GenericProviderOutcome
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof, TelegramApiError
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue, save_release
from video_channel_manager.telegram_multichannel_state import (
    audit_audio_history,
    initialize_ledger,
    prepare_next,
    require_audio_channel_admission,
    save_ledger,
)

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


def test_send_audio_once_read_timeout_is_one_ambiguous_attempt(tmp_path, monkeypatch):
    """After a request is dispatched, a lost response is may_exist and never replayed."""
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    dispatched = []

    def handler(request):
        dispatched.append(request)
        raise httpx.ReadTimeout("lost sendAudio provider response", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramApiError) as error:
            send_audio_once(profile, _target(profile), payload, token="test", client=client, now=NOW)
    assert error.value.provider_effect == "may_exist"
    assert error.value.retryable is False
    assert len(dispatched) == 1


def _history_release(profile, payload, release_id):
    candidate = GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=release_id,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        timezone=profile.timezone,
        daily_verified_limit=profile.daily_verified_limit,
        target_binding_sha256="sha256:" + "2" * 64,
        chat_id=CHAT_ID,
        bot_id=8716602202,
        bot_username="fixture_test_bot",
        items=(
            GenericReleaseItem(
                sequence=1,
                publication_id=payload.publication_id,
                scheduled_at=NOW,
                source_sha256="sha256:" + "1" * 64,
                payload=payload,
            ),
        ),
    )
    return GenericReleaseQueue.model_validate(
        {
            **candidate.model_dump(),
            "release_authorized": True,
            "reviewed_candidate_sha256": candidate.candidate_digest(),
            "reviewed_by": "offline fixture",
            "reviewed_at": NOW,
        }
    )


def test_audio_history_matches_bytes_despite_different_release_and_caption(tmp_path, monkeypatch):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    original = _payload(profile, audio)
    revised = _payload(profile, audio, caption="<b>Другая подпись</b>")
    historical = _history_release(profile, original, "milovi-old-audio")
    candidate = _history_release(profile, revised, "milovi-new-audio")
    ledger = initialize_ledger(historical)
    assert original.provider_payload_sha256 != revised.provider_payload_sha256
    assert audit_audio_history(candidate, revised.publication_id, ((historical, ledger),)) == ()
    prepared = prepare_next(
        profile,
        historical,
        ledger,
        run_id="123",
        run_attempt="1",
        github_sha="1" * 40,
        github_workflow_sha="2" * 40,
        mode="manual",
        target=_target(profile),
        expected_publication_id=original.publication_id,
        now=NOW,
    )
    assert prepared.envelope is not None
    matches = audit_audio_history(candidate, revised.publication_id, ((historical, ledger),))
    assert len(matches) == 1
    assert matches[0].release_id == historical.release_id
    assert matches[0].provider_effect == "may_exist"
    assert matches[0].media_sha256 == revised.media_sha256
    different = _history_release(profile, _payload(profile, audio + b"x"), "milovi-different-audio")
    assert audit_audio_history(different, revised.publication_id, ((historical, ledger),)) == ()


def test_audio_history_rejects_wrong_ledger_channel_and_repeated_release(tmp_path, monkeypatch):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    historical = _history_release(profile, payload, "milovi-old-audio")
    candidate = _history_release(profile, payload, "milovi-new-audio")
    ledger = initialize_ledger(historical)
    with pytest.raises(ValueError, match="ledger identity differs"):
        audit_audio_history(candidate, payload.publication_id, ((historical, initialize_ledger(candidate)),))
    foreign = candidate.model_copy(update={"chat_id": -1001234567890})
    with pytest.raises(ValueError, match="exact candidate channel"):
        audit_audio_history(foreign, payload.publication_id, ((historical, ledger),))
    with pytest.raises(ValueError, match="repeated release identity"):
        audit_audio_history(candidate, payload.publication_id, ((historical, ledger), (historical, ledger)))


def _save_audio_state(root, release, ledger):
    directory = root / release.release_id
    directory.mkdir(parents=True)
    save_release(directory / "release.json", release)
    ledger_path = directory / "ledger.json"
    save_ledger(ledger_path, ledger)
    return ledger_path


@pytest.mark.parametrize("same_audio", [True, False])
def test_canonical_audio_history_blocks_other_unresolved_release(tmp_path, monkeypatch, same_audio):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    original = _payload(profile, audio)
    revised = _payload(profile, audio if same_audio else audio + b"x")
    historical = _history_release(profile, original, "milovi-old-audio")
    candidate = _history_release(profile, revised, "milovi-new-audio")
    root = tmp_path / profile.project_key / "audio-releases"
    old_ledger = initialize_ledger(historical)
    new_ledger = initialize_ledger(candidate)
    old_path = _save_audio_state(root, historical, old_ledger)
    new_path = _save_audio_state(root, candidate, new_ledger)
    require_audio_channel_admission(candidate, new_path, revised.publication_id, now=NOW)

    prepared = prepare_next(
        profile,
        historical,
        old_ledger,
        run_id="123",
        run_attempt="1",
        github_sha="1" * 40,
        github_workflow_sha="2" * 40,
        mode="manual",
        target=_target(profile),
        expected_publication_id=original.publication_id,
        now=NOW,
    )
    assert prepared.envelope is not None
    save_ledger(old_path, old_ledger)
    require_audio_channel_admission(
        historical,
        old_path,
        original.publication_id,
        current_intent_id=prepared.envelope.intent_id,
        now=NOW,
    )
    with pytest.raises(ValueError, match="already published|unresolved channel"):
        require_audio_channel_admission(candidate, new_path, revised.publication_id, now=NOW)


def test_audio_admission_rejects_incomplete_state_checkout(tmp_path, monkeypatch):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    release = _history_release(profile, payload, "milovi-new-audio")
    root = tmp_path / profile.project_key / "audio-releases"
    ledger_path = _save_audio_state(root, release, initialize_ledger(release))
    (root / "missing-release").mkdir()
    with pytest.raises(ValueError, match="invalid Telegram release"):
        require_audio_channel_admission(release, ledger_path, payload.publication_id, now=NOW)
    with pytest.raises(ValueError, match="canonical channel"):
        require_audio_channel_admission(release, tmp_path / "ledger.json", payload.publication_id, now=NOW)


def _git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.parametrize("race_after_check", [False, True])
def test_remote_audio_claim_allows_only_one_sender(tmp_path, monkeypatch, race_after_check):
    audio, _ = _files(tmp_path, monkeypatch, thumbnail=False)
    profile = _profile()
    payload = _payload(profile, audio)
    release = _history_release(profile, payload, "milovi-new-audio")
    ledger = initialize_ledger(release)
    prepared = prepare_next(
        profile,
        release,
        ledger,
        run_id="123",
        run_attempt="1",
        github_sha="1" * 40,
        github_workflow_sha="2" * 40,
        mode="manual",
        target=_target(profile),
        expected_publication_id=payload.publication_id,
        now=NOW,
    )
    assert prepared.envelope is not None
    envelope = prepared.envelope
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare")
    first = tmp_path / "first"
    first.mkdir()
    _git(first, "init", "-b", profile.state_branch)
    _git(first, "config", "core.autocrlf", "false")
    _git(first, "config", "user.name", "test")
    _git(first, "config", "user.email", "test@example.invalid")
    path = _save_audio_state(first / "content/telegram" / profile.project_key / "audio-releases", release, ledger)
    relative = path.relative_to(first)
    _git(first, "add", ".")
    _git(first, "commit", "-m", "persist exact intent")
    _git(first, "remote", "add", "origin", str(remote))
    _git(first, "push", "origin", f"HEAD:refs/heads/{profile.state_branch}")
    second = tmp_path / "second"
    _git(tmp_path, "clone", "-b", profile.state_branch, str(remote), str(second))
    calls = []

    def send(*args):
        calls.append(args)
        return GenericProviderOutcome(
            schema_name="video-channel-manager.telegram-generic-provider-outcome",
            schema_version=1,
            publication_id=envelope.publication_id,
            provider_payload_sha256=envelope.provider_payload_sha256,
            intent_id=envelope.intent_id,
            provider_effect="may_exist",
            error="offline ambiguous effect",
        )

    # Use an isolated local bare Git repository, never a live provider.
    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli._require_state_origin", lambda root: None)
    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli._send_exact_payload", send)

    def winner():
        return _send_persisted_once(profile, release, path, envelope, tmp_path / "first-outcome.json")

    if race_after_check:

        def race(profile_arg, ledger_arg):
            root = _require_current_audio_state(profile_arg, ledger_arg)
            if root == second:
                assert winner().provider_effect == "may_exist"
            return root

        monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli._require_current_audio_state", race)
    else:
        assert winner().provider_effect == "may_exist"

    with pytest.raises(ValueError, match="not the exact current remote state|Git push failed"):
        _send_persisted_once(profile, release, second / relative, envelope, tmp_path / "second-outcome.json")
    assert len(calls) == 1
    assert not (tmp_path / "second-outcome.json").exists()

    fresh = tmp_path / "fresh"
    _git(tmp_path, "clone", "-b", profile.state_branch, str(remote), str(fresh))
    with pytest.raises(ValueError, match="intent already claimed"):
        _send_persisted_once(profile, release, fresh / relative, envelope, tmp_path / "fresh-outcome.json")
    assert len(calls) == 1
