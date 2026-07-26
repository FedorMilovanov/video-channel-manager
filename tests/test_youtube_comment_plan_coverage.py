from __future__ import annotations

from scripts.build_youtube_comment_plan import _is_actionable


def test_missing_and_foreign_only_without_owned_comment_are_actionable() -> None:
    assert _is_actionable({"status": "missing", "owned_comments": []})
    assert _is_actionable({"status": "foreign_only", "owned_comments": []})


def test_owned_or_non_actionable_states_are_not_channel_tail() -> None:
    assert not _is_actionable(
        {
            "status": "foreign_only",
            "owned_comments": [{"comment_id": "comment-1"}],
        }
    )
    assert not _is_actionable({"status": "owned_present", "owned_comments": [{"comment_id": "comment-1"}]})
    assert not _is_actionable({"status": "comments_disabled", "owned_comments": []})
    assert not _is_actionable({"status": "error", "owned_comments": []})
