from __future__ import annotations

import json
import zipfile
from pathlib import Path

from video_channel_manager.platforms.vk import milovi_gap_thumbnail_evidence as gap
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as seq


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _build_thumbnail_evidence_input(tmp_path: Path) -> Path:
    candidates = [
        {
            **row,
            "youtube_url": f"https://www.youtube.com/watch?v={row['youtube_id']}",
            "transfer_gate": "MEDIA_RECONCILIATION_REQUIRED",
            "support_label": "NO_STRONG_MATCH_OBSERVED",
            "top_vk_candidates": [],
            "youtube_thumbnail_downloads": [],
            "same_media_claim": False,
            "missing_native_clip_claim": False,
            "upload_authorized": False,
        }
        for row in gap._GAP_CANDIDATES
    ]
    result = {
        "schema": gap.OUTPUT_SCHEMA,
        "project_key": gap.MILOVI_PROJECT_KEY,
        "youtube_channel_id": gap.MILOVI_YOUTUBE_CHANNEL_ID,
        "community_id": gap.MILOVI_COMMUNITY_ID,
        "owner_id": gap.MILOVI_OWNER_ID,
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "input_evidence": {
            "exact_public_ui_clip_count": 106,
            "exact_wall_native_clip_count": 106,
            "exact_ui_wall_intersection_count": 106,
            "ui_only_count": 0,
            "wall_only_count": 0,
            "surface_complete_claim": False,
        },
        "candidates": candidates,
        "safety": {"upload_authorized": False},
    }
    result_bytes = _json_bytes(result)
    manifest = {
        "schema": seq.INPUT_MANIFEST_SCHEMA,
        "result_sha256": seq._sha256_bytes(result_bytes),
        "project_key": gap.MILOVI_PROJECT_KEY,
        "provider_writes": 0,
        "mutation_authority": False,
    }

    path = tmp_path / "thumbnail-evidence.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("00-manifest.json", _json_bytes(manifest))
        archive.writestr("01-gap-thumbnail-reconciliation.json", result_bytes)
        for _youtube_id, remote_id, _role, _prior in seq._REVIEWED_PAIRS:
            video_id = remote_id.rsplit("_", 1)[1]
            archive.writestr(f"media/vk/neg68859909_{video_id}.jpg", b"test")
    return path


def _frames(
    hashes: list[tuple[str, str]],
    *,
    prefix: str = "frame",
) -> list[dict[str, str]]:
    return [
        {
            "sha256": f"{prefix}-{index}",
            "dhash": dhash,
            "phash": phash,
        }
        for index, (dhash, phash) in enumerate(hashes)
    ]


def test_reviewed_pair_manifest_is_bounded_and_confectionery_only() -> None:
    pairs = seq._REVIEWED_PAIRS
    pair_keys = [(row[0], row[1]) for row in pairs]

    assert len(pairs) == 8
    assert len(pair_keys) == len(set(pair_keys))
    assert sum(row[2].startswith("suspected") for row in pairs) == 5
    assert sum(row[2] == "negative_control" for row in pairs) == 2
    assert sum(row[2] == "reference_pair" for row in pairs) == 1
    assert ("FQGxV4DRPQw", "-68859909_456239159") in pair_keys
    assert ("p3xZaajOMvc", "-68859909_456239130") in pair_keys


def test_input_contract_revalidates_exact_read_only_milovi_evidence(tmp_path: Path) -> None:
    path = _build_thumbnail_evidence_input(tmp_path)

    manifest, result, hashes = seq._read_input(path)

    assert manifest["schema"] == seq.INPUT_MANIFEST_SCHEMA
    assert result["project_key"] == gap.MILOVI_PROJECT_KEY
    assert len(hashes["input_zip_sha256"]) == 64
    assert len(hashes["input_result_sha256"]) == 64


def test_url_identity_accepts_only_exact_media_identity() -> None:
    assert seq._identity_url_matches(
        platform="youtube",
        expected_id="abc123",
        raw_url="https://www.youtube.com/shorts/abc123",
    )
    assert seq._identity_url_matches(
        platform="youtube",
        expected_id="abc123",
        raw_url="https://www.youtube.com/watch?v=abc123",
    )
    assert not seq._identity_url_matches(
        platform="youtube",
        expected_id="abc123",
        raw_url="https://www.youtube.com/shorts/other",
    )
    assert seq._identity_url_matches(
        platform="vk",
        expected_id="-68859909_456239159",
        raw_url="https://vk.com/clip-68859909_456239159",
    )
    assert seq._identity_url_matches(
        platform="vk",
        expected_id="-68859909_456239159",
        raw_url="https://vkvideo.ru/video-68859909_456239159",
    )
    assert not seq._identity_url_matches(
        platform="vk",
        expected_id="-68859909_456239159",
        raw_url="https://vk.com/clip-235216998_456239159",
    )


def test_sequence_metrics_find_ordered_low_distance_alignment() -> None:
    values = [
        ("0000000000000000", "0000000000000000"),
        ("0000000000000001", "0000000000000001"),
        ("0000000000000003", "0000000000000003"),
        ("0000000000000007", "0000000000000007"),
        ("000000000000000f", "000000000000000f"),
        ("000000000000001f", "000000000000001f"),
        ("000000000000003f", "000000000000003f"),
        ("000000000000007f", "000000000000007f"),
    ]
    left = _frames(values)
    right = _frames(values)

    metrics = seq._sequence_metrics(left, right)
    evidence = seq._evidence_class(
        metrics,
        youtube_duration_s=20.0,
        vk_duration_s=19.5,
    )

    assert metrics["support_coverage"] == 1.0
    assert metrics["strong_match_count"] == len(values)
    assert evidence == "STRONG_SAME_EDIT_SEQUENCE_SUPPORT"


def test_sequence_metrics_can_support_distinct_sequence_without_absence_claim() -> None:
    left = _frames(
        [
            ("0000000000000000", "0000000000000000"),
            ("0000000000000000", "0000000000000000"),
            ("0000000000000000", "0000000000000000"),
            ("0000000000000000", "0000000000000000"),
        ]
    )
    right = _frames(
        [
            ("ffffffffffffffff", "ffffffffffffffff"),
            ("ffffffffffffffff", "ffffffffffffffff"),
            ("ffffffffffffffff", "ffffffffffffffff"),
            ("ffffffffffffffff", "ffffffffffffffff"),
        ],
        prefix="other",
    )

    metrics = seq._sequence_metrics(left, right)
    evidence = seq._evidence_class(
        metrics,
        youtube_duration_s=18.0,
        vk_duration_s=18.0,
    )

    assert metrics["loose_coverage"] == 0.0
    assert evidence == "DISTINCT_SEQUENCE_SUPPORT"
    assert (
        seq._operational_disposition(evidence)
        == "NO_ABSENCE_CLAIM_DISTINCT_FROM_THIS_VK_CLIP"
    )


def test_browser_sequence_module_contains_no_mutation_actions() -> None:
    source = Path(seq.__file__).read_text(encoding="utf-8")

    assert '"provider_writes": 0' in source
    assert '"provider_mutation_authorized": False' in source
    assert '"upload_authorized": False' in source
    assert '"delete_authorized": False' in source
    assert '"hide_authorized": False' in source
    assert '"wall_post_authorized": False' in source
    assert '"schedule_authorized": False' in source
    assert '"transfer_queue_created": False' in source
    assert ".click(" not in source
    assert ".fill(" not in source
    assert ".press(" not in source
    assert "set_input_files" not in source
    assert "video.save" not in source
    assert "wall.post" not in source
