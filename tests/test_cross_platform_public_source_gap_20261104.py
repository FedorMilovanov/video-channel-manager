"""Source-led social platform audit, never mistaken for remote absence/proof of posting."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs/audits/2026-11-04-public-youtube-first-page-source-snapshot.json"
REPORT = ROOT / "docs/audits/2026-11-04-cross-platform-youtube-vk-readonly.json"
INSTAGRAM = ROOT / "content/instagram/lord-god-strength-shorts-sermons-intake-20261104.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    # Git's core.autocrlf may translate committed JSON LF to CRLF on Windows.
    # The reviewed evidence digest is defined over canonical Git/LF bytes.
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def test_four_public_surfaces_are_proven_exact_and_bounded() -> None:
    snapshot = _read(SNAPSHOT)
    report = _read(REPORT)
    assert snapshot["schema_name"] == "vcm.public-youtube-html-readonly-snapshot"
    assert snapshot["capture_type"] == "incomplete_public_page_first_batch"
    assert len(snapshot["records"]) == 4
    identities = {
        "lord-god-strength": "UCeSJsC6go2c9pdJCuUI1BYA",
        "legendary-poet": "UC-78ys2S3cQ3lpqgXfo-SvQ",
    }
    assert {(r["project_key"], r["surface"]) for r in snapshot["records"]} == {
        ("lord-god-strength", "videos"),
        ("lord-god-strength", "shorts"),
        ("legendary-poet", "videos"),
        ("legendary-poet", "shorts"),
    }
    expected_lengths = {"videos": 30, "shorts": 48}
    for row in snapshot["records"]:
        assert row["status"] == 200
        assert row["channel_id_in_html"] is True
        assert row["channel_id_expected"] == identities[row["project_key"]]
        assert len(row["items"]) == expected_lengths[row["surface"]]
        assert len({x["video_id"] for x in row["items"]}) == len(row["items"])
        assert row["captured_utc"]
    assert report["source_snapshot_sha256"] == _digest(SNAPSHOT)
    assert report["source_snapshot_path"] == SNAPSHOT.relative_to(ROOT).as_posix()
    assert len(report["source_surfaces"]) == 4
    assert sum(len(r["items"]) for r in report["source_surfaces"]) == 156
    for row in report["source_surfaces"]:
        source = next(
            x for x in snapshot["records"] if (x["project_key"], x["surface"]) == (row["project_key"], row["surface"])
        )
        assert row["youtube_channel_id"] == source["channel_id_expected"]
        assert row["public_first_rendered_page_count"] == len(source["items"])
        assert row["pagination_exhausted"] is False
        assert row["vk_provider_readback_complete"] is False
        assert [x["youtube_id"] for x in row["items"]] == [x["video_id"] for x in source["items"]]
        assert [x["title"] for x in row["items"]] == [x["title"] for x in source["items"]]
        assert all(x["missing_from_vk_confirmed"] is False for x in row["items"])
        assert all(x["new_upload_authorized"] is False for x in row["items"])


def test_exact_vk_states_do_not_create_false_absence_claims() -> None:
    data = _read(REPORT)
    assert data["schema_name"] == "video-manager.cross-platform-public-first-page-readonly-gap-review"
    assert data["schema_version"] == 1
    assert data["evidence_level"] == "read_only_evidence_bundle"
    assert data["package_kind"] == "read_only_evidence_bundle"
    assert data["provider_adapter_connected"] is False
    assert data["provider_writes_authorized"] is False
    assert data["automatic_execution"] is False
    assert data["upload_or_reupload_authorized"] is False
    assert data["missing_from_vk_claims"] == 0
    assert data["vk_legacy_credential_status"] == "quarantined_vk_api_code_9_issue_662"
    assert data["instagram_lord_god_target_status"] == "unbound_professional_account_id"
    assert data["known_legacy_exact_native_vk_verified"] == 8
    assert len(data["verified_native_file_evidence"]) == 8
    assert data["historical_july_mapping_count"] == 111
    assert all(x["state_sha256"].startswith("sha256:") for x in data["verified_native_file_evidence"])
    assert len({x["youtube_id"] for x in data["verified_native_file_evidence"]}) == 8
    assert len({x["state_file_name"] for x in data["verified_native_file_evidence"]}) == 8

    poet_videos = next(
        x for x in data["source_surfaces"] if x["project_key"] == "legendary-poet" and x["surface"] == "videos"
    )
    known = {x["youtube_id"] for x in data["verified_native_file_evidence"]}
    assert {
        x["youtube_id"] for x in poet_videos["items"] if x["local_vk_evidence_class"] == "exact_native_state_verified"
    } == known
    priority = data["fresh_reconcile_priority"]
    assert priority["project_key"] == "legendary-poet"
    assert priority["surface"] == "videos"
    assert priority["source_relative_order_only"] is True
    assert priority["vk_exact_id_readback_required_before_upload"] is True
    assert priority["batch_upload_authorized"] is False
    ids = [x["youtube_id"] for x in poet_videos["items"]]
    assert priority["youtube_ids_ahead_of_latest_locally_verified_in_observed_page"] == ids[:8]
    assert ids[8] == "-Cy-O4rT5xU"
    assert all(x not in known for x in ids[:8])
    all_classes = {item["local_vk_evidence_class"] for source in data["source_surfaces"] for item in source["items"]}
    assert all_classes <= {
        "exact_native_state_verified",
        "historical_july_identity_mapping_not_fresh_vk_proof",
        "vk_presence_not_proven",
    }
    assert "vk_presence_not_proven" in all_classes
    assert len(data["coverage_limitations"]) >= 6
    limitations = " ".join(data["coverage_limitations"]).lower()
    assert "oauth refresh" in limitations
    assert "vk public page" in limitations
    assert "not complete" in limitations
    assert "clips" in limitations
    assert "not a fresh vk provider readback" in limitations


def test_lord_god_reels_are_prioritized_without_account_or_media_fabrication() -> None:
    queue = _read(INSTAGRAM)
    report = _read(REPORT)
    assert queue["schema_name"] == "video-manager.instagram-lord-god-short-sermon-intake-inert"
    assert queue["schema_version"] == 1
    assert queue["project_key"] == "lord-god-strength"
    assert queue["youtube_channel_id"] == "UCeSJsC6go2c9pdJCuUI1BYA"
    assert queue["instagram_professional_account_id"] is None
    assert queue["public_handle_hint_not_identity"]
    assert queue["source_snapshot_sha256"] == _digest(SNAPSHOT)
    assert queue["source_snapshot_path"] == SNAPSHOT.relative_to(ROOT).as_posix()
    assert queue["source_coverage"] == "public_youtube_first_rendered_page_only"
    assert queue["shorts_candidate_count"] == 12
    assert queue["sermon_cut_candidate_count"] == 8
    assert queue["ready_to_publish_count"] == 0
    assert queue["technical_media_verified_count"] == 1
    assert queue["source_only_candidate_count"] == 19
    assert queue["provider_writes_authorized"] is False
    assert queue["automatic_execution"] is False
    assert queue["media_rights_approved"] is False
    assert queue["cut_timecode_fabrication_forbidden"] is True
    assert queue["caption_scripture_quote_until_edition_bound"] is False
    assert queue["publication_release_id"] is None
    assert len(queue["candidates"]) == 20
    assert len({c["candidate_id"] for c in queue["candidates"]}) == 20
    assert len({c["source_video_id"] for c in queue["candidates"]}) == 20

    youtube_sources = {
        (r["surface"], x["youtube_id"]): x
        for r in report["source_surfaces"]
        if r["project_key"] == "lord-god-strength"
        for x in r["items"]
    }
    kinds = Counter()
    for rank, card in enumerate(queue["candidates"], 1):
        assert card["priority_rank"] == rank
        assert card["project_key"] == "lord-god-strength"
        assert card["youtube_channel_id"] == queue["youtube_channel_id"]
        assert (card["source_surface"], card["source_video_id"]) in youtube_sources
        assert card["source_title"] == youtube_sources[(card["source_surface"], card["source_video_id"])]["title"]
        assert card["source_url"].startswith("https://www.youtube.com/")
        assert card["exact_selected_time_range_seconds"] is None
        assert card["transcript_and_attribution_review"] == "pending"
        assert card["reuse_edition_media_rights"] == "pending_independent_review"
        assert card["original_source_master_sha256"] is None
        if card["source_video_id"] == "lTRm2NbnIas":
            assert card["instagram_compatible_render_sha256"] == (
                "sha256:93d6283c954eda608c95bbb26ed5c2f6b80ce3d824a22040bcd9f0587c221d56"
            )
            assert card["local_media_technical_status"] == "passed_meta_v3_no_provider_access"
            assert card["status"] == "technical_render_verified_review_hold"
        else:
            assert card["instagram_compatible_render_sha256"] is None
            assert card["status"] == "source_candidate_not_rendered"
        assert card["caption_review"] == "pending"
        assert card["instagram_professional_account_id"] is None
        assert card["provider_writes_authorized"] is False
        assert card["ready_to_publish"] is False
        assert card["needs_new_owner_source_proof"] is True
        kinds.update([card["source_surface"]])
    assert kinds == {"shorts": 12, "videos": 8}
    assert all(c["reel_treatment"] == "review_original_short_for_vertical_reel" for c in queue["candidates"][:12])
    assert all(
        c["reel_treatment"] == "select_one_semantically_complete_sermon_excerpt" for c in queue["candidates"][12:]
    )


def test_source_snapshot_hash_is_cross_platform_for_lf_and_crlf(tmp_path: Path) -> None:
    source = SNAPSHOT.read_bytes().replace(b"\r\n", b"\n")
    unix = tmp_path / "snapshot-lf.json"
    windows = tmp_path / "snapshot-crlf.json"
    unix.write_bytes(source)
    windows.write_bytes(source.replace(b"\n", b"\r\n"))
    report = _read(REPORT)
    queue = _read(INSTAGRAM)
    assert _digest(unix) == _digest(windows) == report["source_snapshot_sha256"]
    assert _digest(unix) == queue["source_snapshot_sha256"]
