from __future__ import annotations

import pytest

from scripts.report_youtube_duplicate_comments import build_duplicate_dossier


def _audit(*, comments: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_name": "video-manager.youtube-comment-audit",
        "schema_version": 1,
        "channel_id": "channel-1",
        "source_snapshot": "snapshot-1",
        "videos": [
            {
                "video_id": "video-1",
                "title": "Video title",
                "privacy_status": "public",
                "status": "owned_present",
                "owned_comment_count": len(comments),
                "owned_comments": comments,
            }
        ],
    }


def _comment(comment_id: str, text: str, digest: str) -> dict[str, object]:
    return {
        "thread_id": f"thread-{comment_id}",
        "comment_id": comment_id,
        "text": text,
        "text_sha256": f"sha256:{digest}",
        "published_at": "2026-07-26T10:00:00+00:00",
        "updated_at": "2026-07-26T10:00:00+00:00",
        "moderation_status": "published",
    }


def test_dossier_prefers_unique_completed_journal_comment_id() -> None:
    audit = _audit(
        comments=[
            _comment("old-comment", "Old text", "a" * 64),
            _comment("new-comment", "Approved text", "b" * 64),
        ]
    )
    plan = {
        "operations": [
            {
                "operation_id": "operation-1",
                "video_id": "video-1",
                "comment_text": "Approved text",
            }
        ]
    }
    journal = {
        "attempts": {
            "operation-1": {
                "status": "completed",
                "video_id": "video-1",
                "comment_id": "new-comment",
            }
        }
    }

    dossier = build_duplicate_dossier(
        audit,
        expected_channel="channel-1",
        plan=plan,
        journal=journal,
    )

    duplicate = dossier["duplicates"][0]
    assert duplicate["recommended_keep_comment_id"] == "new-comment"
    assert duplicate["recommendation_reason"] == "unique_completed_journal_comment_id"
    assert duplicate["deletion_candidates"] == ["old-comment"]
    assert duplicate["destructive_action_authorized"] is False
    assert dossier["remote_writes"] == 0


def test_dossier_can_recommend_unique_signed_plan_text_match_without_journal() -> None:
    audit = _audit(
        comments=[
            _comment("old-comment", "Old text", "a" * 64),
            _comment("approved-comment", "Approved text", "b" * 64),
        ]
    )
    plan = {
        "operations": [
            {
                "operation_id": "operation-1",
                "video_id": "video-1",
                "comment_text": "Approved text",
            }
        ]
    }

    dossier = build_duplicate_dossier(audit, expected_channel="channel-1", plan=plan)

    duplicate = dossier["duplicates"][0]
    assert duplicate["recommended_keep_comment_id"] == "approved-comment"
    assert duplicate["recommendation_reason"] == "unique_signed_plan_text_match"
    assert duplicate["deletion_candidates"] == ["old-comment"]


def test_dossier_refuses_ambiguous_keep_selection() -> None:
    audit = _audit(
        comments=[
            _comment("comment-1", "Same text", "a" * 64),
            _comment("comment-2", "Same text", "b" * 64),
        ]
    )
    plan = {
        "operations": [
            {
                "operation_id": "operation-1",
                "video_id": "video-1",
                "comment_text": "Same text",
            }
        ]
    }

    dossier = build_duplicate_dossier(audit, expected_channel="channel-1", plan=plan)

    duplicate = dossier["duplicates"][0]
    assert duplicate["recommended_keep_comment_id"] is None
    assert duplicate["recommendation_reason"] == "review_required"
    assert duplicate["deletion_candidates"] == []
    assert dossier["manual_review_count"] == 1


def test_dossier_rejects_owned_comment_count_mismatch() -> None:
    audit = _audit(
        comments=[
            _comment("comment-1", "One", "a" * 64),
            _comment("comment-2", "Two", "b" * 64),
        ]
    )
    audit["videos"][0]["owned_comment_count"] = 3  # type: ignore[index]

    with pytest.raises(ValueError, match="does not match owned_comment_count"):
        build_duplicate_dossier(audit, expected_channel="channel-1")


def test_dossier_rejects_wrong_channel() -> None:
    audit = _audit(
        comments=[
            _comment("comment-1", "One", "a" * 64),
            _comment("comment-2", "Two", "b" * 64),
        ]
    )

    with pytest.raises(ValueError, match="channel does not match"):
        build_duplicate_dossier(audit, expected_channel="channel-2")
