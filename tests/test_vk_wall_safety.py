from __future__ import annotations

from datetime import UTC, datetime

import pytest

from video_channel_manager.platforms.vk.wall_safety import (
    DEFAULT_UPLOAD_WALL_POLICY,
    VkUploadWallPolicy,
    VkWallDeltaStatus,
    build_wall_snapshot,
    compare_wall_snapshots,
)


def _post(post_id: int, *, text: str = "Текст", video_id: int = 501) -> dict[str, object]:
    return {
        "owner_id": -235216998,
        "id": post_id,
        "date": 1785794400,
        "text": text,
        "attachments": [
            {
                "type": "video",
                "video": {"owner_id": -235216998, "id": video_id},
            }
        ],
    }


def test_default_upload_wall_policy_is_explicit_and_self_validating() -> None:
    payload = DEFAULT_UPLOAD_WALL_POLICY.as_dict()

    assert payload["wall_mutation_authorized"] is False
    assert payload["wallpost"] is False
    assert payload["auto_publish"] is False
    assert payload["repeat"] is False
    assert DEFAULT_UPLOAD_WALL_POLICY.video_save_params() == {
        "wallpost": False,
        "auto_publish": False,
        "repeat": False,
    }
    assert VkUploadWallPolicy.from_mapping(payload) == DEFAULT_UPLOAD_WALL_POLICY


def test_upload_wall_policy_rejects_authority_truthy_coercion_and_tampering() -> None:
    with pytest.raises(ValueError, match="cannot authorize"):
        VkUploadWallPolicy(wall_mutation_authorized=True)
    with pytest.raises(ValueError, match="exact boolean"):
        VkUploadWallPolicy.from_mapping(
            {
                "schema_name": "video-manager.vk-upload-wall-policy",
                "schema_version": 1,
                "wall_mutation_authorized": 0,
                "wallpost": False,
                "auto_publish": False,
                "repeat": False,
                "policy_sha256": "sha256:wrong",
            }
        )

    tampered = DEFAULT_UPLOAD_WALL_POLICY.as_dict()
    tampered["wallpost"] = True
    with pytest.raises(ValueError, match="self-digest"):
        VkUploadWallPolicy.from_mapping(tampered)


def test_complete_identical_wall_snapshots_are_clean() -> None:
    captured_at = datetime(2026, 8, 4, 2, 0, tzinfo=UTC)
    before = build_wall_snapshot(
        community_id=235216998,
        published_items=[_post(10)],
        postponed_items=[_post(20, text="Отложено")],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=captured_at,
    )
    after = build_wall_snapshot(
        community_id=235216998,
        published_items=[_post(10)],
        postponed_items=[_post(20, text="Отложено")],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=captured_at,
    )

    delta = compare_wall_snapshots(before, after)

    assert delta.status is VkWallDeltaStatus.CLEAN
    assert delta.clean is True
    assert delta.created == ()
    assert delta.removed == ()
    assert delta.changed == ()


def test_wall_delta_classifies_published_and_postponed_changes() -> None:
    captured_at = datetime(2026, 8, 4, 2, 0, tzinfo=UTC)
    before = build_wall_snapshot(
        community_id=235216998,
        published_items=[_post(10)],
        postponed_items=[_post(20, text="Старый текст")],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=captured_at,
    )
    after = build_wall_snapshot(
        community_id=235216998,
        published_items=[_post(11)],
        postponed_items=[_post(20, text="Новый текст")],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=captured_at,
    )

    delta = compare_wall_snapshots(before, after)

    assert delta.status is VkWallDeltaStatus.CHANGED
    assert delta.created == ("published:-235216998_11",)
    assert delta.removed == ("published:-235216998_10",)
    assert delta.changed == ("postponed:-235216998_20",)


def test_incomplete_wall_snapshot_is_unknown_even_without_visible_delta() -> None:
    captured_at = datetime(2026, 8, 4, 2, 0, tzinfo=UTC)
    before = build_wall_snapshot(
        community_id=235216998,
        published_items=[_post(10)],
        postponed_items=[],
        published_pages=1,
        postponed_pages=0,
        complete=False,
        captured_at=captured_at,
    )
    after = build_wall_snapshot(
        community_id=235216998,
        published_items=[_post(10)],
        postponed_items=[],
        published_pages=1,
        postponed_pages=0,
        complete=True,
        captured_at=captured_at,
    )

    delta = compare_wall_snapshots(before, after)

    assert delta.status is VkWallDeltaStatus.UNKNOWN_REQUIRES_RECONCILIATION
    assert delta.reasons == ("before_snapshot_incomplete",)
