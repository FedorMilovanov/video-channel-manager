from __future__ import annotations

from copy import deepcopy

from video_channel_manager.platforms.youtube.comment_plan import (
    build_comment_plan,
    make_comment_operation,
    validate_comment_plan,
)


def _plan() -> dict[str, object]:
    operation = make_comment_operation(
        action="create",
        channel_id="channel-1",
        video_id="video-1",
        video_title="Title",
        comment_text="Approved comment",
        source_ids=["source-1"],
        reviewed_at="2026-07-25T12:00:00+00:00",
    )
    return build_comment_plan(
        account_alias="legendary-poet",
        channel_id="channel-1",
        source_snapshot="snapshot-1",
        source_snapshot_generated_at="2026-07-25T11:00:00+00:00",
        inventory_video_ids=["video-1", "video-2"],
        operations=[operation],
        mode="reviewed-missing-only",
    )


def test_comment_plan_self_validates() -> None:
    assert validate_comment_plan(_plan()) == []


def test_comment_plan_rejects_changed_text() -> None:
    plan = deepcopy(_plan())
    operations = plan["operations"]
    assert isinstance(operations, list)
    operation = operations[0]
    assert isinstance(operation, dict)
    operation["comment_text"] = "Tampered text"
    errors = validate_comment_plan(plan)
    assert "operations[0].comment_sha256 mismatch" in errors
    assert "plan_sha256 mismatch" in errors


def test_comment_plan_rejects_duplicate_video_targets() -> None:
    plan = deepcopy(_plan())
    operations = plan["operations"]
    assert isinstance(operations, list)
    operations.append(deepcopy(operations[0]))
    errors = validate_comment_plan(plan)
    assert any(error.startswith("multiple operations target the same video") for error in errors)
    assert "operation_set_sha256 mismatch" in errors
    assert "counts mismatch" in errors
    assert "plan_sha256 mismatch" in errors


def test_update_operation_requires_exact_before_state() -> None:
    operation = make_comment_operation(
        action="update",
        channel_id="channel-1",
        video_id="video-1",
        video_title="Title",
        comment_text="Approved after",
        source_ids=["source-1"],
        reviewed_at="2026-07-25T12:00:00+00:00",
        expected_comment_id="comment-1",
        expected_comment_text="Reviewed before",
    )
    plan = build_comment_plan(
        account_alias="legendary-poet",
        channel_id="channel-1",
        source_snapshot="snapshot-1",
        source_snapshot_generated_at="2026-07-25T11:00:00+00:00",
        inventory_video_ids=["video-1"],
        operations=[operation],
        mode="reviewed-create-and-update",
    )
    assert validate_comment_plan(plan) == []
