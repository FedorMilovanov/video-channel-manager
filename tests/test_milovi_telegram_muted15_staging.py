from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.milovi_telegram_feed import (
    MUTED_VIDEO_VARIANTS_PATH,
    MiloviFeedAdditionalMutedVideoBinding,
    _load_video,
    materialize_video,
    validate_bundle,
)
from video_channel_manager.telegram_multichannel_release import load_release

ROOT = Path("content/telegram/milovi-cake")
PLAN = ROOT / "november-muted15-editorial-plan-20261106.json"
SHA_PREFIX = "sha256:"


def test_fifteen_muted_edits_are_exact_and_owner_approved() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    variants = json.loads(MUTED_VIDEO_VARIANTS_PATH.read_text(encoding="utf-8"))["variants"]
    assert plan["files_count"] == len(plan["items"]) == 15
    assert len(variants) == 16
    assert plan["artifact_commit"] == "9331af0c6015404bfda0cd2c6392066b78dc68b3"
    assert plan["release_authorized"] is True
    assert plan["schedule_activated"] is False
    assert plan["owner_publication_approved"] is True
    assert plan["execution_authorized"] is True
    ids, hashes, dates = set(), set(), set()
    for row in plan["items"]:
        pid, media_id = row["publication_id"], row["media_id"]
        ids.add(pid)
        hashes.add(row["sha256"])
        dates.add(row["scheduled_at_proposal"])
        assert media_id != "v12-muted"
        accepted = variants[media_id]
        assert accepted["artifact_commit"] == plan["artifact_commit"]
        assert accepted["artifact_ref"] == plan["artifact_ref"]
        assert accepted["sha256"] == row["sha256"]
        assert accepted["audio_streams"] == 0
        assert accepted["source_video_stream_sha256"] == accepted["muted_video_stream_sha256"]
        assert accepted["content_approved"] is True
        assert accepted["rights_verified"] is True
        assert Path(accepted["rights_evidence_path"]).is_file()
        assert accepted["historical_duplicates_reconciled"] is False
        candidate = json.loads(Path(row["candidate_path"]).read_text(encoding="utf-8"))
        caption = candidate["caption"]
        assert caption.count("?") == 0
        assert sum(0x0400 <= ord(ch) <= 0x052F for ch in caption) > 30
        assert candidate["caption_sha256"] == row["caption_sha256"]
        assert candidate["publication_authorized"] is False
        assert candidate["provider_mutation_allowed"] is False
        assert candidate["accepted_video"]["artifact_sha256"] == accepted["sha256"]
        assert candidate["accepted_video"]["artifact_commit"] == accepted["artifact_commit"]
        video = _load_video(ROOT / "releases" / f"{pid}-video.json")
        assert isinstance(video, MiloviFeedAdditionalMutedVideoBinding)
        assert video.media_id == media_id
        assert video.artifact_git_blob_sha1 == accepted["git_blob_sha1"]
        release = load_release(ROOT / "releases" / f"{pid}-runtime.json")
        auth = json.loads((ROOT / "releases" / f"{pid}-execution-authority.json").read_text(encoding="utf-8"))
        assert release.release_authorized is True
        assert release.reviewed_publication_id == pid
        assert release.items[0].payload.media_sha256 == accepted["sha256"]
        assert auth["execution_authorized"] is True
        assert auth["release_digest"] == release.digest
        assert auth["provider_mutation_allowed"] is True
        result = validate_bundle(pid)
        assert result["valid"] and result["payload_kind"] == "video"
        assert result["provider_access_performed"] is False
        assert result["blockers"] == []
        assert result["execution_authorized"] is True
        assert result["provider_mutation_allowed"] is True
        assert validate_bundle(pid, require_execution_authorized=True)["valid"] is True
    assert len(ids) == len(hashes) == len(dates) == 15
    assert min(dates).startswith("2026-11-08T19:00")
    assert max(dates).startswith("2026-11-22T19:00")


def test_one_new_video_refuses_tampered_source_bytes(tmp_path: Path) -> None:
    pid = "milovi-feed-20261108-001"
    tampered = tmp_path / "fake-source.mp4"
    tampered.write_bytes(b"not an accepted media artifact")
    with pytest.raises(ValueError, match="accepted video bytes differ"):
        materialize_video(pid, source_path=tampered)


def test_existing_v12_is_not_overwritten_by_fifteen_new_variants() -> None:
    variants = json.loads(MUTED_VIDEO_VARIANTS_PATH.read_text(encoding="utf-8"))["variants"]
    original = variants["v12-muted"]
    assert original["rights_verified"] is True
    assert original["content_approved"] is True
    assert original["artifact_commit"] == "686223b41c01ce365853f2e2bf22c20240a1df01"
    assert original["sha256"] == ("sha256:3b680fe94b5007daea9860eeaf16159abf17712887fa3b1714511b48b84143d7")
    signed = validate_bundle("milovi-feed-20261107-002", require_execution_authorized=True)
    assert signed["valid"]
    assert signed["provider_mutation_allowed"] is True


def test_fifteen_release_owner_attestation_exact_scope() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    proof_path = Path(plan["rights_provenance_source"])
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["schema_name"] == "video-channel-manager.milovi-muted15-exact-owner-publication-authorization"
    assert proof["owner_publication_approval_recorded"] is True
    assert proof["user_released_video_without_audio"] is True
    assert proof["single_writer_only"] is True
    assert proof["unlimited_bulk_send_approved"] is False
    assert proof["provider_writes_already_performed"] is False


@pytest.mark.parametrize("missing", ["rights_verified", "content_approved"])
def test_fifteen_exact_variant_rights_gate_cannot_be_omitted(
    missing: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import video_channel_manager.milovi_telegram_feed as feed

    registry = json.loads(MUTED_VIDEO_VARIANTS_PATH.read_text(encoding="utf-8"))
    registry["variants"]["v01-muted"][missing] = False
    path = tmp_path / "missing-rights.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(feed, "MUTED_VIDEO_VARIANTS_PATH", path)
    with pytest.raises(ValueError, match="lacks exact content and visual-rights approval"):
        feed.validate_bundle("milovi-feed-20261108-001", require_execution_authorized=True)
