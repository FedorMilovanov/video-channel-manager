"""Prove one local Instagram encoding is technical-only, not authorized publication."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "docs/audits/2026-11-04-lord-god-piper-first-reel-meta-v3-technical-evidence.json"
QUEUE = ROOT / "content/instagram/lord-god-strength-shorts-sermons-intake-20261104.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exact_source_and_render_proof_is_bound_to_one_candidate() -> None:
    proof = _load(PROOF)
    queue = _load(QUEUE)
    assert proof["schema_name"] == "video-manager.instagram-lord-god-first-reel-meta-v3-qc-nonpublishing"
    assert proof["schema_version"] == 1
    assert proof["project_key"] == queue["project_key"] == "lord-god-strength"
    assert proof["youtube_channel_id"] == queue["youtube_channel_id"] == "UCeSJsC6go2c9pdJCuUI1BYA"
    assert proof["source_video_id"] == "lTRm2NbnIas"
    card = next(x for x in queue["candidates"] if x["source_video_id"] == proof["source_video_id"])
    assert card["source_url"] == proof["source_url"] == "https://www.youtube.com/shorts/lTRm2NbnIas"
    assert card["source_title"] == proof["source_title"]
    assert proof["source_intake_snapshot_sha256"] == queue["source_snapshot_sha256"]
    assert card["source_surface"] == "shorts"
    assert card["local_media_technical_proof_path"] == PROOF.relative_to(ROOT).as_posix()
    assert card["local_media_technical_status"] == "passed_meta_v3_no_provider_access"
    assert card["local_media_source_candidate_sha256"] == proof["source_local_sha256"]
    assert card["instagram_compatible_render_sha256"] == proof["render_sha256"]
    assert card["local_media_render_basename"] == proof["render_basename"]
    assert card["local_media_render_size_bytes"] == proof["render_size_bytes"]
    assert proof["render_basename"].endswith(".mp4")
    assert "\\" not in proof["render_basename"]
    assert "/" not in proof["render_basename"]
    assert proof["render_local_outbox_receipt_basename"].endswith(".json")
    assert proof["physical_media_stored_in_git"] is False
    assert proof["render_size_bytes"] == 103472054
    assert proof["render_sha256"] == ("sha256:93d6283c954eda608c95bbb26ed5c2f6b80ce3d824a22040bcd9f0587c221d56")
    assert proof["source_local_sha256"] == ("sha256:13359972f1a4e981563bf788ba2d81169d6a383527824d0913ab1cbab0b20e55")
    assert proof["source_local_size_bytes"] == 52092242
    assert "unverified" in proof["source_local_file_provenance"]


def test_meta_v3_media_proof_has_complete_frame_and_audio_identity() -> None:
    p = _load(PROOF)
    assert p["technical_review"] == "passed_existing_instagram_production_verify_local_reel"
    assert p["media_technical_ruleset"] == "meta-instagram-reels-2026-09-v3"
    v = p["technical_video"]
    assert v["codec"] == "h264"
    assert (v["width"], v["height"]) == (1080, 1920)
    assert v["pixel_format"] == "yuv420p"
    assert v["field_order"] == "progressive"
    assert v["frame_rate_fps"] == 30
    assert v["source_frame_count"] == v["output_frame_count"] == 4320
    assert v["closed_gop_verified"] is True
    assert v["intra_frame_count"] == v["idr_frame_count"] == 72
    assert p["source_clip_full_duration_seconds"] == 144
    audio = p["technical_audio"]
    assert audio["codec"] == "aac"
    assert audio["sample_rate_hz"] == 44100
    assert audio["copied_compressed_stream_without_reencoding"] is True
    assert audio["source_compressed_stream_sha256"] == audio["output_compressed_stream_sha256"]
    assert audio["source_compressed_stream_sha256"].startswith("fd38de99")
    container = p["container"]
    assert container["moov_before_mdat"] is True
    assert container["edit_list_count"] == 0
    assert container["stream_copy_for_audio"] is True
    assert container["video_encoder"] == "h264_nvenc"
    assert p["advisories"] == ["audio_bitrate_not_recommended_128_kbps"]


def test_technical_acceptance_cannot_be_construed_as_provider_release() -> None:
    proof = _load(PROOF)
    queue = _load(QUEUE)
    card = next(x for x in queue["candidates"] if x["source_video_id"] == "lTRm2NbnIas")
    assert queue["ready_to_publish_count"] == 0
    assert queue["technical_media_verified_count"] == 1
    assert queue["source_only_candidate_count"] == 19
    assert queue["instagram_professional_account_id"] is None
    assert queue["media_rights_approved"] is False
    assert queue["provider_writes_authorized"] is False
    assert queue["automatic_execution"] is False
    assert queue["publication_release_id"] is None
    assert card["status"] == "technical_render_verified_review_hold"
    assert card["original_source_master_sha256"] is None
    assert card["instagram_professional_account_id"] is None
    assert card["reuse_edition_media_rights"] == "pending_independent_review"
    assert card["transcript_and_attribution_review"] == "pending"
    assert card["caption_review"] == "pending"
    assert card["needs_new_owner_source_proof"] is True
    assert card["ready_to_publish"] is False
    assert card["provider_writes_authorized"] is False
    assert proof["editorial_visual_review"] == "pending"
    assert proof["translation_and_speaker_attribution_review"] == "pending"
    assert proof["reuse_rights_status"] == "pending_independent_review"
    assert proof["instagram_professional_account_id"] is None
    assert proof["caption_approved"] is False
    assert proof["ready_to_publish"] is False
    assert proof["provider_writes_authorized"] is False
    assert proof["publication_release_id"] is None
    assert len([x for x in queue["candidates"] if x["instagram_compatible_render_sha256"]]) == 1
