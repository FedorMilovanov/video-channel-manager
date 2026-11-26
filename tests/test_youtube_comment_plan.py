from __future__ import annotations

from copy import deepcopy

from video_channel_manager.platforms.youtube.comment_plan import (
    build_comment_plan,
    make_comment_operation,
    seal_comment_plan,
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


def test_additional_comment_plan_binds_existing_comment_ids_and_digests() -> None:
    from video_channel_manager.platforms.youtube.comments import comment_text_sha256

    before = {"comment-1": comment_text_sha256("First history")}
    operation = make_comment_operation(
        action="create",
        channel_id="channel-1",
        video_id="video-1",
        video_title="Title",
        comment_text="Independent second history",
        source_ids=["source-2"],
        reviewed_at="2026-11-24T19:00:00+00:00",
        expected_owned_comments=before,
    )
    plan = build_comment_plan(
        account_alias="legendary-poet",
        channel_id="channel-1",
        source_snapshot="snapshot-1",
        source_snapshot_generated_at="2026-11-24T18:59:00+00:00",
        inventory_video_ids=["video-1"],
        operations=[operation],
        mode="reviewed-additional-comment",
    )
    assert not validate_comment_plan(plan)
    changed = deepcopy(plan)
    changed["operations"][0]["expected_owned_comments"]["comment-1"] = comment_text_sha256("Changed")
    errors = validate_comment_plan(changed)
    assert "operations[0].operation_id mismatch" in errors
    assert "plan_sha256 mismatch" in errors
    changed = deepcopy(plan)
    changed["operations"][0]["expected_owned_comments"] = {}
    assert any("expected_owned_comments" in error for error in validate_comment_plan(changed))
    changed = deepcopy(plan)
    changed["mode"] = "reviewed-missing-only"
    assert any("additional create requires" in error for error in validate_comment_plan(changed))


def test_first_comment_requires_explicit_empty_owner_inventory() -> None:
    operation = make_comment_operation(
        action="create",
        channel_id="channel-1",
        video_id="video-1",
        video_title="Title",
        comment_text="First historical comment",
        source_ids=["source-1"],
        reviewed_at="2026-11-26T00:00:00+00:00",
        expected_owned_comments={},
    )
    plan = build_comment_plan(
        account_alias="legendary-poet",
        channel_id="channel-1",
        source_snapshot="snapshot-1",
        source_snapshot_generated_at="2026-11-25T23:59:00+00:00",
        inventory_video_ids=["video-1"],
        operations=[operation],
        mode="reviewed-first-comment",
    )
    assert validate_comment_plan(plan) == []
    for wrong_mode in ("reviewed-additional-comment", "reviewed-missing-only"):
        assert validate_comment_plan(seal_comment_plan({**plan, "mode": wrong_mode}))
    missing = deepcopy(plan)
    del missing["operations"][0]["expected_owned_comments"]
    assert any("explicit empty owner map" in error for error in validate_comment_plan(seal_comment_plan(missing)))
    nonempty = deepcopy(plan)
    nonempty["operations"][0]["expected_owned_comments"] = {"other": "sha256:" + "1" * 64}
    assert any("explicit empty owner map" in error for error in validate_comment_plan(seal_comment_plan(nonempty)))
    empty = deepcopy(plan)
    empty["operations"] = []
    assert validate_comment_plan(seal_comment_plan(empty))



def test_exact_update_mode_binds_target_before_digest_and_complete_owner_map() -> None:
    from video_channel_manager.platforms.youtube.comments import comment_text_sha256

    # A legacy formatting mistake is valid evidence, not valid new copy.
    old_text = "*Source*: https://example.com/"
    before = {"comment-1": comment_text_sha256(old_text), "other": comment_text_sha256("Other comment")}
    operation = make_comment_operation(
        action="update",
        channel_id="channel-1",
        video_id="video-1",
        video_title="Title",
        comment_text="*Source:* https://example.com/",
        source_ids=["source-1"],
        reviewed_at="2026-11-26T00:00:00+00:00",
        expected_comment_id="comment-1",
        expected_comment_text=old_text,
        expected_owned_comments=before,
    )
    plan = build_comment_plan(
        account_alias="legendary-poet",
        channel_id="channel-1",
        source_snapshot="snapshot",
        source_snapshot_generated_at="2026-11-25T23:59:00+00:00",
        inventory_video_ids=["video-1"],
        operations=[operation],
        mode="reviewed-comment-update",
    )
    assert validate_comment_plan(plan) == []
    for mode in ("reviewed-first-comment", "reviewed-additional-comment", "reviewed-create-and-update"):
        assert validate_comment_plan(seal_comment_plan({**plan, "mode": mode}))
    for wrong_map in ({}, {"other": before["other"]}, {"comment-1": "sha256:" + "0" * 64}):
        changed = deepcopy(plan)
        changed["operations"][0]["expected_owned_comments"] = wrong_map
        assert validate_comment_plan(seal_comment_plan(changed))
    changed = deepcopy(plan)
    changed["operations"] = []
    assert validate_comment_plan(seal_comment_plan(changed))
