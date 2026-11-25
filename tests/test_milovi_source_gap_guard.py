"""Milovi owner source gap review is independent of upload and never writes providers."""

from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.platforms.vk.milovi_final_review_queue import (
    ACCEPTED_GAP_ZIP_SHA256,
    ACCEPTED_SEQUENCE_ZIP_SHA256,
)
from video_channel_manager.platforms.vk.milovi_source_gap_guard import (
    MiloviReviewEvidenceError,
    build_source_review,
)


def fixture() -> dict:
    records = [
        ("Vin9ATN9xuA", "VERIFIED_OLDER_60", 456239266, "private"),
        ("CQ29P1F8Hfo", "NOT_YET_PROVEN_PRESENT_REVIEW_UPLOAD", None, "public"),
        ("q4ZYIBOG8Ow", "PROBABLE_PRESENT_DO_NOT_UPLOAD", 456239191, "public"),
        ("SiluLt5Bz1c", "WEAK_VIDEO_MATCH_INSPECT_EDIT", 456239096, "public"),
        ("ypUBcdJyepc", "NOT_YET_PROVEN_PRESENT_REVIEW_UPLOAD", None, "public"),
        ("2yhQ4nMWm3I", "WEAK_VIDEO_MATCH_INSPECT_EDIT", 456239173, "public"),
        ("OVchKZZqULo", "VERIFIED_OLDER_60", 456239173, "public"),
    ]
    owner = {
        "generated_at": "2026-11-18T19:00:00Z",
        "channel": {"ref": {"remote_id": "UCMDnxfGZiBqcDzgUV1zjFpw"}},
        "videos": [
            {
                "ref": {"channel_id": "UCMDnxfGZiBqcDzgUV1zjFpw", "remote_id": yid},
                "privacy_status": privacy,
            }
            for yid, _, _, privacy in records
        ],
    }
    crosswalk = {
        "youtube_total": len(records),
        "items": [{"youtube_id": yid, "scope": scope, "vk_id": vkid} for yid, scope, vkid, _ in records],
    }
    manual = {
        "project_key": "milovi-cake",
        "youtube_channel_id": "UCMDnxfGZiBqcDzgUV1zjFpw",
        "owner_id": -68859909,
        "input_evidence": {
            "gap_zip_sha256": ACCEPTED_GAP_ZIP_SHA256,
            "sequence_zip_sha256": ACCEPTED_SEQUENCE_ZIP_SHA256,
        },
        "reviewed_sequence_pairs": [
            {
                "youtube_id": "CQ29P1F8Hfo",
                "vk_remote_id": "-68859909_456239100",
                "manual_decision": "EXISTING_NATIVE_REPRESENTATION_OBSERVED",
                "manual_confidence": "high",
                "upload_authorized": False,
            }
        ],
    }
    visual = {
        "items": [
            {
                "youtube_id": "q4ZYIBOG8Ow",
                "vk_clip_id": 456239191,
                "visual_verdict": "MATCHING_SAME_VIDEO_CONTENT_AT_SIX_TIME_ALIGNED_MOMENTS",
            },
            {
                "youtube_id": "Vin9ATN9xuA",
                "vk_clip_id": 456239266,
                "visual_verdict": "MATCHING_SAME_VIDEO_CONTENT_AT_SIX_TIME_ALIGNED_MOMENTS",
            },
        ]
    }
    wall = {
        "community_id": 68859909,
        "owner_id": -68859909,
        "public_wall_complete": True,
        "captured_at_utc": "2026-11-18T19:05:00Z",
        "all_video_to_post_ids": {
            "-68859909_456239100": [317],
            "-68859909_456239191": [440],
            "-68859909_456239096": [311],
            "-68859909_456239082": [300],
        },
        "duplicate_video_attachments_across_posts": {},
    }
    additional = {
        "newly_high_confidence_present_short": {
            "youtube_id": "SiluLt5Bz1c",
            "vk_best_match": 456239096,
            "vk_near_identical_existing_variant": 456239082,
            "vk_1hz_same_position_dhash_distance_at_most_8_count": 21,
            "frame_pairs": 30,
        }
    }
    return {
        "youtube_owner": owner,
        "crosswalk": crosswalk,
        "rights_terminal": {
            "owner_id": -68859909,
            "all_removed_ids_authoritatively_absent": True,
            "removed_native_ids": [456239074, 456239266],
            "removed_wall_posts": [290, 536],
        },
        "accepted_manual": manual,
        "independent_visual": visual,
        "public_wall": wall,
        "additional_visual": additional,
    }


def by_id(result: dict, source_id: str) -> dict:
    return next(x for x in result["sources"] if x["youtube_id"] == source_id)


def test_retirement_weak_collision_manual_sixframe_and_extra_visual() -> None:
    report = build_source_review(**fixture())
    assert report["category_counts"] == {
        "HISTORICAL_VK_PRESENCE_PROTECT": 1,
        "MANUAL_VK_PRESENCE_PROTECT": 1,
        "RETIRED_RIGHTS_NEVER_RESTORE": 1,
        "REVIEW_ONLY_NO_VK_OWNER_ABSENCE": 2,
        "SIXFRAME_VK_PRESENCE_PROTECT": 1,
        "TIMED_VK_PRESENCE_PROTECT": 1,
    }
    assert by_id(report, "Vin9ATN9xuA")["state"] == "RETIRED_RIGHTS_NEVER_RESTORE"
    assert by_id(report, "CQ29P1F8Hfo")["verified_vk_video_id_if_known"] == 456239100
    assert by_id(report, "q4ZYIBOG8Ow")["verified_vk_video_id_if_known"] == 456239191
    assert by_id(report, "SiluLt5Bz1c")["verified_vk_video_id_if_known"] == 456239096
    assert by_id(report, "2yhQ4nMWm3I")["state"] == "REVIEW_ONLY_NO_VK_OWNER_ABSENCE"
    assert by_id(report, "2yhQ4nMWm3I")["verified_vk_video_id_if_known"] is None
    assert by_id(report, "OVchKZZqULo")["state"] == "HISTORICAL_VK_PRESENCE_PROTECT"
    assert not report["upload_authorized"]
    assert not report["postponed_create_authorized"]
    assert not report["verified_missing_source_ids"]
    assert report["provider_writes"] == 0
    assert all(not row["upload_authorized"] for row in report["sources"])


@pytest.mark.parametrize("wrong_field", ("community_id", "owner_id", "public_wall_complete"))
def test_wrong_or_partial_vk_wall_fails_closed(wrong_field: str) -> None:
    inputs = fixture()
    values = {"community_id": 60805374, "owner_id": -60805374, "public_wall_complete": False}
    inputs["public_wall"][wrong_field] = values[wrong_field]
    with pytest.raises(MiloviReviewEvidenceError, match="VK wall"):
        build_source_review(**inputs)


def test_missing_manual_exact_id_on_current_public_wall_fails_closed() -> None:
    inputs = fixture()
    del inputs["public_wall"]["all_video_to_post_ids"]["-68859909_456239100"]
    with pytest.raises(MiloviReviewEvidenceError, match="Manual match"):
        build_source_review(**inputs)


def test_missing_extra_duplicate_fingerprint_or_vk_id_fails_closed() -> None:
    inputs = fixture()
    inputs["additional_visual"]["newly_high_confidence_present_short"]["frame_pairs"] = 29
    with pytest.raises(MiloviReviewEvidenceError, match="Extra timed-video proof"):
        build_source_review(**inputs)


def test_six_frame_evidence_on_retired_video_is_not_resurrected() -> None:
    inputs = fixture()
    report = build_source_review(**inputs)
    assert by_id(report, "Vin9ATN9xuA")["verified_vk_video_id_if_known"] is None


def test_absence_of_rights_deletion_receipt_cannot_be_overridden() -> None:
    inputs = fixture()
    inputs["rights_terminal"]["all_removed_ids_authoritatively_absent"] = False
    with pytest.raises(MiloviReviewEvidenceError, match="rights deletion"):
        build_source_review(**inputs)


def test_owner_mismatch_and_partial_catalog_fail_closed() -> None:
    inputs = fixture()
    inputs["youtube_owner"]["videos"][0]["ref"]["channel_id"] = "UCeSJsC6go2c9pdJCuUI1BYA"
    with pytest.raises(MiloviReviewEvidenceError, match="YouTube owner"):
        build_source_review(**inputs)
    inputs = fixture()
    inputs["youtube_owner"]["videos"].pop()
    with pytest.raises(MiloviReviewEvidenceError, match="absent from current owner API"):
        build_source_review(**inputs)


def test_fake_accepted_zip_digest_fails_closed() -> None:
    inputs = fixture()
    inputs["accepted_manual"]["input_evidence"]["gap_zip_sha256"] = "0" * 64
    with pytest.raises(MiloviReviewEvidenceError, match="accepted ZIP"):
        build_source_review(**inputs)


def test_invented_manual_vk_source_does_not_prove_absence() -> None:
    inputs = fixture()
    original = deepcopy(inputs)
    original["accepted_manual"]["reviewed_sequence_pairs"][0]["vk_remote_id"] = "-60805374_456239100"
    with pytest.raises(MiloviReviewEvidenceError, match="Manual pair"):
        build_source_review(**original)
