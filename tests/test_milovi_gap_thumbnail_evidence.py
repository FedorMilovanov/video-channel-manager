from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from video_channel_manager.platforms.vk import milovi_gap_thumbnail_evidence as gap


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _build_exact_input(tmp_path: Path) -> Path:
    clip_ids = list(range(456239001, 456239107))
    shrek_id = 456239130
    clip_ids[-1] = shrek_id
    remote_ids = [f"{gap.MILOVI_OWNER_ID}_{video_id}" for video_id in clip_ids]

    posts = [
        {
            "id": index + 1,
            "attachments": [
                {
                    "type": "video",
                    "video": {
                        "type": "short_video",
                        "owner_id": gap.MILOVI_OWNER_ID,
                        "id": video_id,
                        "duration": 30,
                        "date": 1_700_000_000 + index,
                        "description": f"Торт evidence {index}",
                    },
                }
            ],
        }
        for index, video_id in enumerate(clip_ids)
    ]
    posts_bytes = _json_bytes(posts)

    nested_buffer = io.BytesIO()
    with zipfile.ZipFile(nested_buffer, "w", compression=zipfile.ZIP_DEFLATED) as nested:
        nested.writestr("wall/vk-wall-content-audit-test/01-published-wall-posts.json", posts_bytes)
    wall_bytes = nested_buffer.getvalue()

    ui = {
        "schema": gap.UI_SCHEMA,
        "project_key": gap.MILOVI_PROJECT_KEY,
        "community_id": gap.MILOVI_COMMUNITY_ID,
        "owner_id": gap.MILOVI_OWNER_ID,
        "read_only": True,
        "provider_writes": 0,
        "provider_mutation_authorized": False,
        "browser_probe": {"status": "ok_bounded_ui_observation"},
        "coverage": {
            "clip_count": gap.EXPECTED_CLIP_COUNT,
            "bounded_ui_end_observed": True,
            "surface_complete_claim": False,
            "required_remote_ids_found": [gap.KNOWN_SHREK_CLIP],
        },
        "clips": [{"remote_id": remote_id} for remote_id in remote_ids],
    }
    ui_bytes = _json_bytes(ui)
    manifest = {
        "schema": gap.INPUT_SCHEMA,
        "target": {
            "project_key": gap.MILOVI_PROJECT_KEY,
            "community_id": gap.MILOVI_COMMUNITY_ID,
            "owner_id": gap.MILOVI_OWNER_ID,
        },
        "ui_inventory": {"sha256": gap._sha256_bytes(ui_bytes)},
        "wall_evidence": {"sha256": gap._sha256_bytes(wall_bytes)},
    }

    path = tmp_path / "input.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("00-manifest.json", _json_bytes(manifest))
        outer.writestr("01-vk-clips-ui-inventory.json", ui_bytes)
        outer.writestr("02-wall-evidence-handoff.zip", wall_bytes)
    return path


def test_gap_candidate_manifest_is_exact_scope_and_unique() -> None:
    rows = gap._GAP_CANDIDATES
    ids = [str(row["youtube_id"]) for row in rows]

    assert len(rows) == 25
    assert len(ids) == len(set(ids))
    assert {str(row["scope"]) for row in rows} == {"CAKE", "DESSERT"}
    assert "FQGxV4DRPQw" in ids
    assert "R0KjJvbxS8s" in ids


def test_transfer_gates_keep_ip_visual_and_trademark_reviews_blocking() -> None:
    assert gap._transfer_gate("IP_HOLD_HIDE") == "IP_HOLD_DO_NOT_TRANSFER"
    assert gap._transfer_gate("VISUAL_REVIEW") == "VISUAL_REVIEW_REQUIRED"
    assert gap._transfer_gate("TRADEMARK_REVIEW") == "TRADEMARK_REVIEW_REQUIRED"
    assert gap._transfer_gate("LOW") == "MEDIA_RECONCILIATION_REQUIRED"


def test_image_url_allowlist_is_exact_and_https_only() -> None:
    assert gap._allowed_image_url("https://i.ytimg.com/vi/abc/0.jpg")
    assert gap._allowed_image_url("https://iv.okcdn.ru/getVideoPreview?id=1")
    assert gap._allowed_image_url("https://sun1.userapi.com/example.jpg")
    assert not gap._allowed_image_url("http://i.ytimg.com/vi/abc/0.jpg")
    assert not gap._allowed_image_url("https://i.ytimg.com.evil.example/vi/abc/0.jpg")
    assert not gap._allowed_image_url("https://example.com/image.jpg")


def test_exact_reconciliation_input_requires_same_106_ui_and_wall_ids(tmp_path: Path) -> None:
    path = _build_exact_input(tmp_path)
    wall_clips, hashes = gap._read_input(path)

    assert len(wall_clips) == 106
    assert gap.KNOWN_SHREK_CLIP in wall_clips
    assert len(hashes["outer_input_sha256"]) == 64
    assert len(hashes["ui_inventory_sha256"]) == 64
    assert len(hashes["wall_handoff_sha256"]) == 64


def test_metadata_ranking_prefers_semantic_duration_and_date_support() -> None:
    candidate = {
        "title": "3D Торт Свинка",
        "duration_s": 20,
        "published": "2024-10-29",
    }
    exact_date = int(datetime(2024, 10, 30, tzinfo=UTC).timestamp())
    wall_clips = {
        "-68859909_456239159": {
            "description": "3D Торт Свинка от Milovi Cake",
            "duration": 19,
            "date": exact_date,
        },
        "-68859909_456239999": {
            "description": "Торт на день рождения",
            "duration": 55,
            "date": exact_date - 200 * 86_400,
        },
    }

    ranked = gap._rank(candidate, [], wall_clips, {})

    assert ranked[0]["remote_id"] == "-68859909_456239159"
    assert ranked[0]["metadata_score"] > ranked[1]["metadata_score"]


def test_result_contract_never_promotes_support_to_mutation_authority() -> None:
    source = Path(gap.__file__).read_text(encoding="utf-8")

    assert '"provider_writes": 0' in source
    assert '"same_media_claim": False' in source
    assert '"missing_native_clip_claim": False' in source
    assert '"upload_authorized": False' in source
    assert '"delete_authorized": False' in source
    assert '"hide_authorized": False' in source
    assert '"wall_post_authorized": False' in source
    assert '"schedule_authorized": False' in source
    assert "video.save" not in source
    assert "wall.post" not in source
