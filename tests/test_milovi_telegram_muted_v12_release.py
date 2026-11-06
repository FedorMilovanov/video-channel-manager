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


def test_audio_free_candidate_has_correct_cyrillic_and_is_inert() -> None:
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
    assert check["blockers"] == [
        "release_authorized=false",
        "execution_authorized=false",
        "provider_mutation_allowed=false",
    ]
    with pytest.raises(ValueError, match="not freshly authorized"):
        feed.validate_bundle(ID, require_release_authorized=True)
    with pytest.raises(ValueError, match="not freshly authorized"):
        feed.validate_bundle(ID, require_execution_authorized=True)


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
    assert authority["execution_authorized"] is False


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
