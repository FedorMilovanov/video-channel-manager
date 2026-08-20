from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

import video_channel_manager.milovi_telegram_feed as feed
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import (
    GenericReleaseItem,
    GenericReleaseQueue,
    save_release,
)
from video_channel_manager.telegram_multichannel_transport import render_message_payload
from video_channel_manager.telegram_target_binding import load_target_binding


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "telegram" / "milovi-cake"
PROFILE_PATH = ROOT / "content" / "telegram" / "channels" / "milovi-cake.json"
TARGET_PATH = ROOT / "content" / "telegram" / "channels" / "milovi-cake-target-binding.json"
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-feed-publisher.yml"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_message_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, text: str) -> tuple[str, Path, Path]:
    publication_id = "milovi-feed-20990101-001"
    releases = tmp_path / "releases"
    releases.mkdir()
    monkeypatch.setattr(feed, "RELEASE_ROOT", releases)

    profile = load_channel_profile(PROFILE_PATH)
    target = load_target_binding(TARGET_PATH, profile)
    payload = render_message_payload(profile, publication_id=publication_id, html_text=text)
    text_sha256 = _sha256_text(text)
    item = GenericReleaseItem(
        sequence=1,
        publication_id=publication_id,
        scheduled_at=datetime.fromisoformat("2099-01-01T10:30:00+03:00"),
        source_sha256=text_sha256,
        payload=payload,
    )
    release = GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=publication_id,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        timezone=profile.timezone,
        daily_verified_limit=profile.daily_verified_limit,
        target_binding_sha256=target.digest,
        chat_id=target.chat_id,
        bot_id=target.bot_id,
        bot_username=target.bot_username,
        release_authorized=False,
        reviewed_candidate_sha256=None,
        reviewed_by=None,
        reviewed_at=None,
        items=(item,),
    )
    save_release(releases / f"{publication_id}-runtime.json", release)

    candidate_path = tmp_path / "candidate.json"
    candidate = {
        "schema_name": "video-channel-manager.milovi-telegram-feed-candidate",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "publication_id": publication_id,
        "operation": "sendMessage",
        "caption": text,
        "publication_authorized": False,
        "execution_authorized": False,
        "provider_mutation_allowed": False,
    }
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    message_path = releases / f"{publication_id}-message.json"
    message = {
        "schema_name": "video-channel-manager.milovi-telegram-feed-message",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "publication_id": publication_id,
        "candidate_path": str(candidate_path),
        "text_field": "caption",
        "text_sha256": text_sha256,
        "provider_write_performed": False,
    }
    message_path.write_text(json.dumps(message, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    authority = {
        "schema_name": "video-channel-manager.milovi-telegram-execution-authority",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "publication_id": publication_id,
        "release_id": publication_id,
        "release_candidate_sha256": release.candidate_digest(),
        "release_digest": None,
        "provider_payload_sha256": payload.provider_payload_sha256,
        "execution_authorized": False,
        "provider_mutation_allowed": False,
        "authorized_by": None,
        "authorized_at": None,
        "authority_source": "fresh_exact_human_authorization_only",
        "historical_authorization_inherits": False,
        "automation_is_execution_authority": False,
        "max_provider_attempts": 1,
        "blind_mutation_retries": 0,
    }
    (releases / f"{publication_id}-execution-authority.json").write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return publication_id, candidate_path, releases


def test_existing_photo_bundle_still_uses_exact_photo_path() -> None:
    result = feed.validate_bundle("milovi-feed-20260820-001")

    assert result["valid"] is True
    assert result["payload_kind"] == "photo"
    assert result["provider_access_performed"] is False


def test_marathon_school_copy_validates_as_exact_permanent_message_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marathon = json.loads((CONTENT / "marathon-wave-2026-08.json").read_text(encoding="utf-8"))
    frozen = json.loads((CONTENT / "follow-on-wave-candidates-2026-08.json").read_text(encoding="utf-8"))
    school = next(item for item in marathon["items"] if item["position"] == 3)
    source = frozen["items"][school["legacy_position"] - 1]
    publication_id, _, releases = _write_message_bundle(tmp_path, monkeypatch, text=source["caption"])

    result = feed.validate_bundle(publication_id)

    assert result["valid"] is True
    assert result["payload_kind"] == "message"
    assert result["release_authorized"] is False
    assert result["execution_authorized"] is False
    assert result["provider_mutation_allowed"] is False
    assert result["provider_access_performed"] is False
    assert not (releases / f"{publication_id}-media.json").exists()


def test_message_bundle_fails_closed_on_candidate_text_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_id, candidate_path, _ = _write_message_bundle(
        tmp_path,
        monkeypatch,
        text="Исходный проверенный текст",
    )
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["caption"] = "Изменённый после freeze текст"
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="text digest differs"):
        feed.validate_bundle(publication_id)


def test_message_bundle_rejects_ambiguous_media_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_id, _, releases = _write_message_bundle(
        tmp_path,
        monkeypatch,
        text="Точный текст без медиа",
    )
    (releases / f"{publication_id}-media.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not carry a media binding"):
        feed.validate_bundle(publication_id)


def test_permanent_writer_materializes_media_only_for_photo_payloads() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'echo "payload_kind=$payload_kind" >> "$GITHUB_OUTPUT"' in text
    assert "if: inputs.operation == 'publish' && steps.gate.outputs.payload_kind == 'photo'" in text
    assert text.count("telegram_multichannel_cli send-once") == 1
    assert "schedule:" not in text
    assert "cron:" not in text
