from __future__ import annotations

import pytest

from scripts.recover_youtube_comment_wave import strict_coverage_summary, validate_recovery_journal


def _plan() -> dict[str, object]:
    return {
        "schema_name": "video-manager.youtube-comment-plan",
        "schema_version": 1,
        "plan_sha256": "sha256:plan-1",
        "channel_id": "channel-1",
        "source_snapshot": "snapshot-1",
        "operations": [
            {
                "operation_id": "operation-1",
                "video_id": "video-1",
                "action": "create",
            },
            {
                "operation_id": "operation-2",
                "video_id": "video-2",
                "action": "create",
            },
        ],
    }


def _journal(*, status: str = "verification_pending") -> dict[str, object]:
    return {
        "schema_name": "video-manager.youtube-comment-apply-journal",
        "schema_version": 1,
        "plan_sha256": "sha256:plan-1",
        "channel_id": "channel-1",
        "source_snapshot": "snapshot-1",
        "status": status,
        "attempts": {
            "operation-1": {
                "status": "completed",
                "video_id": "video-1",
                "action": "create",
            },
            "operation-2": {
                "status": "completed",
                "video_id": "video-2",
                "action": "create",
            },
        },
    }


def _owned_comment(comment_id: str, text_hash: str) -> dict[str, str]:
    return {
        "comment_id": comment_id,
        "text_sha256": text_hash,
    }


def _closed_audit() -> dict[str, object]:
    return {
        "schema_name": "video-manager.youtube-comment-audit",
        "schema_version": 1,
        "channel_id": "channel-1",
        "inventory_video_count": 2,
        "counts": {"owned_present": 2},
        "videos": [
            {
                "video_id": "video-1",
                "status": "owned_present",
                "owned_comment_count": 1,
                "owned_comments": [_owned_comment("comment-1", "sha256:text-1")],
            },
            {
                "video_id": "video-2",
                "status": "owned_present",
                "owned_comment_count": 1,
                "owned_comments": [_owned_comment("comment-2", "sha256:text-2")],
            },
        ],
    }


def test_recovery_journal_accepts_completed_attempts_before_final_status() -> None:
    assert validate_recovery_journal(
        _journal(),
        plan=_plan(),
        require_completed_status=False,
    ) == {"planned": 2, "completed_attempts": 2}


def test_recovery_journal_requires_completed_status_after_verify_only() -> None:
    with pytest.raises(ValueError, match="not completed"):
        validate_recovery_journal(
            _journal(),
            plan=_plan(),
            require_completed_status=True,
        )

    assert validate_recovery_journal(
        _journal(status="completed"),
        plan=_plan(),
        require_completed_status=True,
    ) == {"planned": 2, "completed_attempts": 2}


def test_recovery_journal_rejects_a_different_operation_set() -> None:
    journal = _journal()
    attempts = journal["attempts"]
    assert isinstance(attempts, dict)
    attempts.pop("operation-2")

    with pytest.raises(ValueError, match="operation set"):
        validate_recovery_journal(
            journal,
            plan=_plan(),
            require_completed_status=False,
        )


def test_strict_coverage_requires_at_least_one_owned_comment_on_every_video() -> None:
    assert strict_coverage_summary(_closed_audit(), expected_channel="channel-1") == {
        "inventory_video_count": 2,
        "owned_present": 2,
        "multiple_owned_videos": 0,
        "extra_owned_comments": 0,
        "exact_text_duplicate_videos": 0,
        "foreign_only": 0,
        "missing": 0,
        "comments_disabled": 0,
        "error": 0,
    }


def test_strict_coverage_allows_distinct_additional_channel_comments() -> None:
    audit = _closed_audit()
    videos = audit["videos"]
    assert isinstance(videos, list)
    first = videos[0]
    assert isinstance(first, dict)
    first["owned_comment_count"] = 2
    first["owned_comments"] = [
        _owned_comment("comment-1", "sha256:text-1"),
        _owned_comment("comment-1b", "sha256:text-1b"),
    ]

    summary = strict_coverage_summary(audit, expected_channel="channel-1")

    assert summary["multiple_owned_videos"] == 1
    assert summary["extra_owned_comments"] == 1
    assert summary["exact_text_duplicate_videos"] == 0


def test_strict_coverage_rejects_exact_duplicate_channel_comment_text() -> None:
    audit = _closed_audit()
    videos = audit["videos"]
    assert isinstance(videos, list)
    first = videos[0]
    assert isinstance(first, dict)
    first["owned_comment_count"] = 2
    first["owned_comments"] = [
        _owned_comment("comment-1", "sha256:text-1"),
        _owned_comment("comment-1b", "sha256:text-1"),
    ]

    with pytest.raises(ValueError, match="exact duplicate channel-authored comment text"):
        strict_coverage_summary(audit, expected_channel="channel-1")


def test_strict_coverage_rejects_malformed_owned_comment_evidence() -> None:
    audit = _closed_audit()
    videos = audit["videos"]
    assert isinstance(videos, list)
    first = videos[0]
    assert isinstance(first, dict)
    first["owned_comment_count"] = 2

    with pytest.raises(ValueError, match="length does not match"):
        strict_coverage_summary(audit, expected_channel="channel-1")


def test_strict_coverage_rejects_false_zeroes_and_incomplete_counts() -> None:
    audit = _closed_audit()
    audit["inventory_video_count"] = False
    with pytest.raises(ValueError, match="non-negative integer"):
        strict_coverage_summary(audit, expected_channel="channel-1")

    audit = _closed_audit()
    audit["counts"] = {"owned_present": 0, "missing": 0}
    with pytest.raises(ValueError, match="do not match"):
        strict_coverage_summary(audit, expected_channel="channel-1")


def test_strict_coverage_rejects_any_remaining_tail() -> None:
    audit = _closed_audit()
    videos = audit["videos"]
    assert isinstance(videos, list)
    second = videos[1]
    assert isinstance(second, dict)
    second["status"] = "foreign_only"
    second["owned_comment_count"] = 0
    second["owned_comments"] = []
    audit["counts"] = {"owned_present": 1, "foreign_only": 1}

    with pytest.raises(ValueError, match="without a channel-authored comment"):
        strict_coverage_summary(audit, expected_channel="channel-1")
