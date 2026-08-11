from __future__ import annotations

from video_channel_manager.platforms.vk.clips_owner_reconciliation import (
    build_owner_clips_wall_reconciliation,
    extract_wall_native_clips,
)

MILOVI_COMMUNITY_ID = 68859909
MILOVI_OWNER_ID = -68859909
KNOWN_SHREK_CLIP = "-68859909_456239130"


def _clip(video_id: int, *, owner_id: int = MILOVI_OWNER_ID, title: str | None = None) -> dict[str, object]:
    return {
        "id": video_id,
        "owner_id": owner_id,
        "type": "short_video",
        "title": title or f"Clip {video_id}",
        "description": "Торт",
        "duration": 30,
        "width": 1080,
        "height": 1920,
    }


def _published_posts(ids: list[int]) -> list[dict[str, object]]:
    posts: list[dict[str, object]] = []
    for index, video_id in enumerate(ids, start=1):
        posts.append(
            {
                "id": 1000 + index,
                "owner_id": MILOVI_OWNER_ID,
                "attachments": [
                    {
                        "type": "video",
                        "video": _clip(video_id),
                    }
                ],
            }
        )
    return posts


def _owner_probe(ids: list[int], *, status: str = "ok", pagination_complete: bool = True) -> dict[str, object]:
    clips = [
        {
            "remote_id": f"{MILOVI_OWNER_ID}_{video_id}",
            "owner_id": MILOVI_OWNER_ID,
            "video_id": video_id,
            "type": "short_video",
            "is_native_clip": True,
            "title": f"Clip {video_id}",
        }
        for video_id in ids
    ]
    return {
        "schema": "vk-owner-clips-experimental-probe-v2",
        "project_key": "milovi-cake",
        "read_only": True,
        "provider_effect": "safe_read_only",
        "community": {
            "community_id": MILOVI_COMMUNITY_ID,
            "owner_id": MILOVI_OWNER_ID,
            "managed_by_token": True,
        },
        "provider_probe": {
            "status": status,
            "provider_reported_total": len(ids) if status == "ok" else None,
            "pagination_complete": pagination_complete,
        },
        "coverage": {
            "clip_count": len(clips),
            "surface_complete_claim": False,
            "required_remote_ids": [KNOWN_SHREK_CLIP],
            "required_remote_ids_found_as_clips": [KNOWN_SHREK_CLIP]
            if KNOWN_SHREK_CLIP in {item["remote_id"] for item in clips}
            else [],
            "required_remote_ids_missing_from_probe": []
            if KNOWN_SHREK_CLIP in {item["remote_id"] for item in clips}
            else [KNOWN_SHREK_CLIP],
        },
        "clips": clips,
    }


def test_reconciliation_proves_all_106_wall_clips_are_covered_without_claiming_complete_surface() -> None:
    wall_ids = [456239130, *range(456240000, 456240105)]
    owner_only_ids = [456250001, 456250002, 456250003, 456250004]

    result = build_owner_clips_wall_reconciliation(
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        published_posts=_published_posts(wall_ids),
        owner_probe=_owner_probe([*wall_ids, *owner_only_ids]),
    )

    assert result["status"] == "wall_coverage_reconciled_experimental"
    assert result["wall_evidence"]["native_clip_count"] == 106
    assert result["owner_probe_evidence"]["native_clip_count"] == 110
    assert result["reconciliation"]["both_count"] == 106
    assert result["reconciliation"]["wall_only_count"] == 0
    assert result["reconciliation"]["owner_only_count"] == 4
    assert result["reconciliation"]["owner_probe_covers_all_wall_native_clips"] is True
    assert result["reconciliation"]["surface_complete_claim"] is False
    assert result["owner_probe_evidence"]["surface_complete_claim"] is False
    assert result["provider_writes"] == 0
    assert result["reconciliation_sha256"].startswith("sha256:")


def test_reconciliation_exposes_wall_proven_clip_missing_from_experimental_owner_probe() -> None:
    wall_ids = [456239130, 456239131, 456239132]

    result = build_owner_clips_wall_reconciliation(
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        published_posts=_published_posts(wall_ids),
        owner_probe=_owner_probe([456239131, 456239132]),
    )

    assert result["status"] == "wall_coverage_gap"
    assert result["reconciliation"]["wall_only_remote_ids"] == [KNOWN_SHREK_CLIP]
    assert result["reconciliation"]["owner_probe_covers_all_wall_native_clips"] is False
    assert result["reconciliation"]["surface_complete_claim"] is False


def test_provider_error_is_preserved_without_promoting_absence_to_surface_claim() -> None:
    result = build_owner_clips_wall_reconciliation(
        project_key="milovi-cake",
        community_id=MILOVI_COMMUNITY_ID,
        owner_id=MILOVI_OWNER_ID,
        published_posts=_published_posts([456239130]),
        owner_probe=_owner_probe([], status="error", pagination_complete=False),
    )

    assert result["status"] == "probe_error"
    assert result["reconciliation"]["wall_only_remote_ids"] == [KNOWN_SHREK_CLIP]
    assert result["reconciliation"]["owner_probe_covers_all_wall_native_clips"] is False
    assert result["reconciliation"]["surface_complete_claim"] is False


def test_wall_extractor_uses_nested_video_type_not_outer_attachment_type() -> None:
    posts = [
        {
            "id": 1,
            "owner_id": MILOVI_OWNER_ID,
            "attachments": [
                {"type": "video", "video": _clip(456239130)},
                {
                    "type": "video",
                    "video": {
                        "id": 456239129,
                        "owner_id": MILOVI_OWNER_ID,
                        "type": "video",
                        "title": "ordinary",
                    },
                },
            ],
            "copy_history": [
                {
                    "attachments": [
                        {
                            "type": "clip",
                            "clip": _clip(456239132),
                        }
                    ]
                }
            ],
        }
    ]

    clips = extract_wall_native_clips(posts, owner_id=MILOVI_OWNER_ID)

    assert [item["remote_id"] for item in clips] == [
        "-68859909_456239130",
        "-68859909_456239132",
    ]
    assert all(item["type"] == "short_video" for item in clips)


def test_wall_extractor_rejects_foreign_native_clip_owner() -> None:
    posts = [
        {
            "id": 1,
            "owner_id": MILOVI_OWNER_ID,
            "attachments": [
                {
                    "type": "video",
                    "video": _clip(456239130, owner_id=-235216998),
                }
            ],
        }
    ]

    try:
        extract_wall_native_clips(posts, owner_id=MILOVI_OWNER_ID)
    except ValueError as exc:
        assert "foreign owner" in str(exc)
    else:
        raise AssertionError("foreign native Clip owner must fail closed")


def test_reconciliation_rejects_cross_project_identity_before_using_evidence() -> None:
    try:
        build_owner_clips_wall_reconciliation(
            project_key="legendary-poet",
            community_id=MILOVI_COMMUNITY_ID,
            owner_id=MILOVI_OWNER_ID,
            published_posts=_published_posts([456239130]),
            owner_probe=_owner_probe([456239130]),
        )
    except ValueError as exc:
        assert "canonical project identity" in str(exc)
    else:
        raise AssertionError("cross-project reconciliation must fail closed")
