from __future__ import annotations

import json
from pathlib import Path

import pytest

import video_channel_manager.milovi_telegram_feed as feed
from video_channel_manager.telegram_multichannel_release import load_release

ID = "milovi-feed-20261107-002"
CONTENT = Path("content/telegram/milovi-cake")
LEGACY_RESERVOIR = CONTENT / "accepted-video-reservoir-2026-08.json"
VARIANT_REGISTRY = CONTENT / "accepted-video-variants-2026-11.json"


def _candidate() -> dict[str, object]:
    return json.loads((CONTENT / "november-muted-video-candidate-20261107.json").read_text(encoding="utf-8"))


def test_audio_free_candidate_is_inert_but_exact_owner_release_is_authorized() -> None:
    candidate = _candidate()
    caption = str(candidate["caption"])
    assert len(caption) > 140
    assert sum(0x0400 <= ord(character) <= 0x052F for character in caption) > 50
    assert "?" not in caption
    assert candidate["operation"] == "sendVideo"
    assert candidate["media_id"] == "v12-muted"
    assert candidate["audio_removed"] is True
    assert candidate["publication_authorized"] is False
    assert candidate["execution_authorized"] is False
    assert candidate["provider_mutation_allowed"] is False

    check = feed.validate_bundle(ID)
    assert check["valid"] is True
    assert check["payload_kind"] == "video"
    assert check["blockers"] == []
    assert check["release_authorized"] is True
    assert check["execution_authorized"] is True
    assert check["provider_mutation_allowed"] is True
    assert check["provider_access_performed"] is False
    assert feed.validate_bundle(ID, require_release_authorized=True)["valid"] is True
    assert feed.validate_bundle(ID, require_execution_authorized=True)["valid"] is True


def test_variant_evidence_is_independent_from_legacy_16() -> None:
    old = json.loads(LEGACY_RESERVOIR.read_text(encoding="utf-8"))
    new = json.loads(VARIANT_REGISTRY.read_text(encoding="utf-8"))
    v12 = next(item for item in old["artifacts"] if item["media_id"] == "v12")
    variant = new["variants"]["v12-muted"]

    assert old["accepted_output_count"] == len(old["artifacts"]) == 16
    assert v12["sha256"] == "sha256:8ebdd2f5b9747399acf6559f1642327ac736ff585007c6c5d54102f90ef3997c"
    assert variant["source_sha256"] == v12["sha256"]
    assert variant["artifact_commit"] == "686223b41c01ce365853f2e2bf22c20240a1df01"
    assert variant["audio_streams"] == 0
    assert variant["frames"] == 299
    assert variant["source_video_stream_sha256"] == variant["muted_video_stream_sha256"]

    video = json.loads((CONTENT / "releases" / f"{ID}-video.json").read_text(encoding="utf-8"))
    for bind_field, registry_field in [
        ("artifact_ref", "artifact_ref"),
        ("artifact_commit", "artifact_commit"),
        ("artifact_git_blob_sha1", "git_blob_sha1"),
        ("artifact_sha256", "sha256"),
        ("artifact_byte_size", "byte_size"),
        ("provenance_sha256", "provenance_sha256"),
    ]:
        assert video[bind_field] == variant[registry_field]
    assert video["filename"] == "milovi-v12-muted.mp4"

    release = load_release(CONTENT / "releases" / f"{ID}-runtime.json")
    authority = json.loads((CONTENT / "releases" / f"{ID}-execution-authority.json").read_text(encoding="utf-8"))
    assert release.items[0].payload.media_sha256 == variant["sha256"]
    assert release.items[0].payload.media_byte_size == variant["byte_size"]
    assert authority["release_candidate_sha256"] == release.candidate_digest()
    assert release.release_authorized is True
    assert release.reviewed_publication_id == ID
    assert authority["execution_authorized"] is True
    assert authority["provider_mutation_allowed"] is True
    assert authority["authorized_publication_id"] == ID
    assert authority["release_digest"] == release.digest
    assert release.items[0].scheduled_at.isoformat() == "2026-11-07T11:00:00+03:00"


@pytest.mark.parametrize("change", ["corrupt_caption", "remove_audio_proof", "swap_media_hash"])
def test_muted_video_fails_closed_on_binding_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    original = CONTENT / "november-muted-video-candidate-20261107.json"
    changed = json.loads(original.read_text(encoding="utf-8"))
    if change == "corrupt_caption":
        changed["caption"] += "extra"
    elif change == "remove_audio_proof":
        changed["audio_removed"] = False
    else:
        changed["accepted_video"]["artifact_sha256"] = "sha256:" + "0" * 64
    candidate_copy = tmp_path / "candidate.json"
    candidate_copy.write_text(json.dumps(changed, ensure_ascii=True), encoding="utf-8")

    old_video_path = CONTENT / "releases" / f"{ID}-video.json"
    video = feed._load_video(old_video_path)
    mocked_video = video.model_copy(update={"candidate_path": str(candidate_copy)})
    old_loader = feed._load_video
    monkeypatch.setattr(feed, "_load_video", lambda p: mocked_video if p == old_video_path else old_loader(p))
    with pytest.raises(ValueError, match="caption digest differs|lacks exact audio-free source binding"):
        feed.validate_bundle(ID)


def test_video_materialization_does_not_accept_unreviewed_bytes(tmp_path: Path) -> None:
    wrong = tmp_path / "not-the-accepted-muted-artifact.mp4"
    wrong.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="accepted video bytes differ"):
        feed.materialize_video(ID, source_path=wrong)


def test_owner_rights_attestation_is_exact_to_muted_video_and_caption() -> None:
    registry = json.loads(VARIANT_REGISTRY.read_text(encoding="utf-8"))["variants"]["v12-muted"]
    assert registry["content_approved"] is True
    assert registry["rights_verified"] is True
    owner = json.loads(Path(registry["rights_evidence_path"]).read_text(encoding="utf-8"))
    candidate = _candidate()
    assert owner["publication_id"] == ID
    assert owner["video_visual_rights_confirmed_by_owner"] is True
    assert owner["audio_rights_claimed"] is False
    assert owner["provider_media_audio_streams"] == 0
    assert owner["exact_video_sha256"] == registry["sha256"]
    assert owner["exact_caption_sha256"] == candidate["caption_sha256"]
    assert owner["exact_release_slot"] == "2026-11-07T11:00:00+03:00"


@pytest.mark.parametrize("missing_gate", ["content_approved", "rights_verified"])
def test_owner_rights_cannot_be_bypassed_when_missing(
    missing_gate: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = json.loads(VARIANT_REGISTRY.read_text(encoding="utf-8"))
    registry["variants"]["v12-muted"][missing_gate] = False
    test_registry = tmp_path / "unapproved-variant-registry.json"
    test_registry.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(feed, "MUTED_VIDEO_VARIANTS_PATH", test_registry)
    with pytest.raises(ValueError, match="lacks exact content and visual-rights approval"):
        feed.validate_bundle(ID, require_execution_authorized=True)
