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
from video_channel_manager.telegram_multichannel_video import render_video_payload
from video_channel_manager.telegram_target_binding import load_target_binding


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "telegram" / "milovi-cake"
PROFILE_PATH = ROOT / "content" / "telegram" / "channels" / "milovi-cake.json"
TARGET_PATH = ROOT / "content" / "telegram" / "channels" / "milovi-cake-target-binding.json"
WORKFLOW = ROOT / ".github" / "workflows" / "milovi-telegram-feed-publisher.yml"
RESERVOIR = CONTENT / "accepted-video-reservoir-2026-08.json"
V01_SHA256 = "sha256:34f1040ded2e32b1a901e8663e62fec272e4b5f05a76ef82c04767f89a894df6"
V01_BLOB = "48690c1cbdcd6001e4b234989ac1c708f38ef4fb"
V01_SIZE = 5_142_500


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_video_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path, Path]:
    publication_id = "milovi-feed-20990101-002"
    releases = tmp_path / "releases"
    releases.mkdir()
    monkeypatch.setattr(feed, "RELEASE_ROOT", releases)

    profile = load_channel_profile(PROFILE_PATH)
    target = load_target_binding(TARGET_PATH, profile)
    caption = "3D-торт «Книги»: форма как часть идеи"
    local_media_path = ".runtime/milovi-v01.mp4"
    payload = render_video_payload(
        profile,
        publication_id=publication_id,
        caption=caption,
        media_path=local_media_path,
        media_sha256=V01_SHA256,
        media_byte_size=V01_SIZE,
        media_filename="milovi-v01.mp4",
    )
    item = GenericReleaseItem(
        sequence=1,
        publication_id=publication_id,
        scheduled_at=datetime.fromisoformat("2099-01-01T10:30:00+03:00"),
        source_sha256=V01_SHA256,
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

    candidate_path = tmp_path / "video-candidate.json"
    candidate = {
        "schema_name": "video-channel-manager.milovi-telegram-feed-candidate",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "publication_id": publication_id,
        "operation": "sendVideo",
        "media_id": "v01",
        "caption": caption,
        "publication_authorized": False,
        "execution_authorized": False,
        "provider_mutation_allowed": False,
    }
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    video = {
        "schema_name": "video-channel-manager.milovi-telegram-feed-video",
        "schema_version": 1,
        "project_key": "milovi-cake",
        "publication_id": publication_id,
        "media_id": "v01",
        "candidate_path": str(candidate_path),
        "caption_sha256": _sha256_text(caption),
        "artifact_repository": "FedorMilovanov/video-channel-manager",
        "artifact_ref": "agent/milovi-video-accepted-73c578eff825",
        "artifact_path": "artifacts/milovi-telegram/video/milovi-v01.mp4",
        "artifact_git_blob_sha1": V01_BLOB,
        "artifact_byte_size": V01_SIZE,
        "artifact_sha256": V01_SHA256,
        "evidence_sha256": feed.VIDEO_EVIDENCE_SHA256,
        "local_media_path": local_media_path,
        "filename": "milovi-v01.mp4",
        "provider_write_performed": False,
    }
    (releases / f"{publication_id}-video.json").write_text(
        json.dumps(video, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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


def test_accepted_video_reservoir_is_exact_16_of_16() -> None:
    reservoir = json.loads(RESERVOIR.read_text(encoding="utf-8"))
    artifacts = reservoir["artifacts"]

    assert reservoir["status"] == "accepted_16_of_16_provider_inert"
    assert reservoir["evidence_sha256"] == feed.VIDEO_EVIDENCE_SHA256
    assert reservoir["artifact_ref"] == feed.VIDEO_ARTIFACT_REF
    assert reservoir["accepted_output_count"] == len(artifacts) == 16
    assert [item["media_id"] for item in artifacts] == [f"v{index:02d}" for index in range(1, 17)]
    assert len({item["sha256"] for item in artifacts}) == 16
    assert len({item["git_blob_sha1"] for item in artifacts}) == 16
    assert all(item["video_codec"] == "h264" and item["pixel_format"] == "yuv420p" for item in artifacts)
    assert all(item["audio_codec"] == "aac" and item["audio_sample_rate"] == 48_000 for item in artifacts)
    assert all(item["audio_channels"] == 2 for item in artifacts)
    assert reservoir["provider_access_performed"] is False
    assert reservoir["provider_write_performed"] is False


def test_exact_accepted_video_can_validate_through_permanent_feed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_id, _, releases = _write_video_bundle(tmp_path, monkeypatch)

    result = feed.validate_bundle(publication_id)

    assert result["valid"] is True
    assert result["payload_kind"] == "video"
    assert result["release_authorized"] is False
    assert result["execution_authorized"] is False
    assert result["provider_mutation_allowed"] is False
    assert result["provider_access_performed"] is False
    assert not (releases / f"{publication_id}-media.json").exists()
    assert not (releases / f"{publication_id}-message.json").exists()


def test_video_bundle_fails_closed_on_caption_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_id, candidate_path, _ = _write_video_bundle(tmp_path, monkeypatch)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["caption"] = "Подменённая подпись"
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="caption digest differs"):
        feed.validate_bundle(publication_id)


def test_video_bundle_rejects_ambiguous_message_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_id, _, releases = _write_video_bundle(tmp_path, monkeypatch)
    (releases / f"{publication_id}-message.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not carry a message binding"):
        feed.validate_bundle(publication_id)


def test_video_materialization_rejects_nonaccepted_bytes_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_id, _, _ = _write_video_bundle(tmp_path, monkeypatch)
    wrong_source = tmp_path / "wrong.mp4"
    wrong_source.write_bytes(b"not-the-accepted-video")
    output = tmp_path / ".runtime" / "milovi-v01.mp4"

    with pytest.raises(ValueError, match="accepted video bytes differ"):
        feed.materialize_video(publication_id, source_path=wrong_source, output_path=output)

    assert not output.exists()


def test_permanent_writer_keeps_one_send_and_payload_aware_video_materialization() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "photo|message|video" in text
    assert "steps.gate.outputs.payload_kind == 'video'" in text
    assert "milovi_telegram_feed materialize-video" in text
    assert "agent/milovi-video-accepted-73c578eff825" not in text
    assert text.count("telegram_multichannel_cli send-once") == 1
    assert "schedule:" not in text
    assert "cron:" not in text
