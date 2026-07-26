from __future__ import annotations

import pytest

from scripts.apply_youtube_comment_plan import _classify_operation
from scripts.refresh_youtube_comments import (
    actionable_tail_from_audit,
    plan_mode_arguments,
    preflight_summary_from_report,
)
from video_channel_manager.platforms.youtube.comments import TopLevelCommentSnapshot, VideoIdentity


def _plan() -> dict[str, object]:
    return {
        "channel_id": "channel-1",
        "source_snapshot": "snapshot-1",
        "plan_sha256": "sha256:plan-1",
    }


def test_preflight_summary_uses_machine_readable_report() -> None:
    report = {
        "schema_name": "video-manager.youtube-comment-preflight",
        "schema_version": 1,
        "channel_id": "channel-1",
        "source_snapshot": "snapshot-1",
        "plan_sha256": "sha256:plan-1",
        "counts": {
            "planned": 15,
            "ready": 12,
            "already_applied": 3,
            "blockers": 0,
        },
    }
    assert preflight_summary_from_report(report, plan=_plan(), operation_count=15) == {
        "planned": 15,
        "ready": 12,
        "already": 3,
        "blockers": 0,
    }


def test_preflight_summary_rejects_incomplete_or_wrong_report() -> None:
    with pytest.raises(ValueError, match="counts object"):
        preflight_summary_from_report(
            {
                "schema_name": "video-manager.youtube-comment-preflight",
                "schema_version": 1,
                "channel_id": "channel-1",
                "source_snapshot": "snapshot-1",
                "plan_sha256": "sha256:plan-1",
            },
            plan=_plan(),
            operation_count=1,
        )
    with pytest.raises(ValueError, match="plan_sha256"):
        preflight_summary_from_report(
            {
                "schema_name": "video-manager.youtube-comment-preflight",
                "schema_version": 1,
                "channel_id": "channel-1",
                "source_snapshot": "snapshot-1",
                "plan_sha256": "sha256:wrong",
                "counts": {"planned": 1, "ready": 1, "already_applied": 0, "blockers": 0},
            },
            plan=_plan(),
            operation_count=1,
        )


def test_actionable_tail_counts_only_missing_and_foreign_only() -> None:
    audit = {
        "counts": {
            "missing": 3,
            "foreign_only": 4,
            "owned_present": 100,
            "comments_disabled": 2,
            "error": 1,
        }
    }
    assert actionable_tail_from_audit(audit) == 7


def test_actionable_tail_requires_machine_readable_counts() -> None:
    with pytest.raises(ValueError, match="counts object"):
        actionable_tail_from_audit({})


def test_plan_mode_arguments_are_fail_closed() -> None:
    assert plan_mode_arguments(create_missing=False, creates_only=False) == [
        "--include-updates",
        "--updates-only",
    ]
    assert plan_mode_arguments(create_missing=True, creates_only=False) == ["--include-updates"]
    assert plan_mode_arguments(create_missing=True, creates_only=True) == []


def test_update_preflight_uses_exact_comment_from_target_video_threads() -> None:
    snapshot = TopLevelCommentSnapshot(
        thread_id="thread-1",
        comment_id="comment-1",
        video_id="video-1",
        channel_id="channel-1",
        author_channel_id="channel-1",
        author_display_name="The Legendary Poet",
        text="Reviewed before",
        published_at=None,
        updated_at=None,
        moderation_status="published",
        raw={},
    )

    class FakeWriter:
        def read_video_identity(self, video_id: str) -> VideoIdentity:
            assert video_id == "video-1"
            return VideoIdentity(
                video_id="video-1",
                channel_id="channel-1",
                title="Title",
                privacy_status="public",
            )

        def list_top_level_comments(self, video_id: str) -> list[TopLevelCommentSnapshot]:
            assert video_id == "video-1"
            return [snapshot]

        def read_comment(self, comment_id: str) -> TopLevelCommentSnapshot:
            raise AssertionError(f"Direct comments.list lookup must not be used for update preflight: {comment_id}")

    operation = {
        "channel_id": "channel-1",
        "video_id": "video-1",
        "action": "update",
        "comment_text": "Approved after",
        "expected_comment_id": "comment-1",
        "expected_comment_text": "Reviewed before",
    }
    assert _classify_operation(FakeWriter(), operation) == ("ready", "comment-1")  # type: ignore[arg-type]
