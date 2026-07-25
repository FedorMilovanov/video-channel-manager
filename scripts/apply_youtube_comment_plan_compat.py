from __future__ import annotations

from typing import NoReturn

from video_channel_manager.platforms.youtube.comments import (
    TopLevelCommentSnapshot,
    YouTubeCommentConflictError,
    YouTubeCommentError,
    YouTubeCommentWriter,
    comments_equivalent,
    validate_comment_text,
)


def _find_top_level_comment(
    writer: YouTubeCommentWriter,
    *,
    video_id: str,
    comment_id: str,
) -> TopLevelCommentSnapshot | None:
    return next(
        (item for item in writer.list_top_level_comments(video_id) if item.comment_id == comment_id),
        None,
    )


def _create_top_level_comment_compat(
    self: YouTubeCommentWriter,
    *,
    video_id: str,
    expected_channel_id: str,
    text: str,
) -> TopLevelCommentSnapshot:
    normalized = validate_comment_text(text)
    identity = self.read_video_identity(video_id)
    if identity.channel_id != expected_channel_id:
        raise YouTubeCommentConflictError(
            f"Channel mismatch for {video_id}: expected {expected_channel_id}, got {identity.channel_id}."
        )

    existing = self.list_top_level_comments(video_id)
    owned = [item for item in existing if item.author_channel_id == expected_channel_id]
    for item in owned:
        if comments_equivalent(item.text, normalized):
            return item
    if owned:
        ids = ", ".join(item.comment_id for item in owned)
        raise YouTubeCommentConflictError(
            f"Video {video_id} already has {len(owned)} different top-level channel comment(s): {ids}."
        )

    payload = self._request(
        "POST",
        "commentThreads",
        params={"part": "snippet"},
        json_body={
            "snippet": {
                "channelId": expected_channel_id,
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": normalized}},
            }
        },
        require_write=True,
    )
    created = self._parse_thread(payload)
    if created.video_id != video_id or created.channel_id != expected_channel_id:
        raise YouTubeCommentError(f"YouTube created a comment on an unexpected target for {video_id}.")

    verified = _find_top_level_comment(self, video_id=video_id, comment_id=created.comment_id)
    if verified is None:
        raise YouTubeCommentError(
            f"YouTube created comment {created.comment_id}, but it was not found during thread verification."
        )
    if verified.author_channel_id != expected_channel_id or not comments_equivalent(verified.text, normalized):
        raise YouTubeCommentError(f"Verification failed after creating a comment for {video_id}.")
    return verified


def _update_top_level_comment_compat(
    self: YouTubeCommentWriter,
    *,
    comment_id: str,
    video_id: str,
    expected_channel_id: str,
    expected_text: str,
    new_text: str,
) -> TopLevelCommentSnapshot:
    normalized_new = validate_comment_text(new_text)
    current = _find_top_level_comment(self, video_id=video_id, comment_id=comment_id)
    if current is None:
        raise YouTubeCommentConflictError(f"Top-level comment {comment_id} was not found on video {video_id}.")
    if current.channel_id != expected_channel_id or current.author_channel_id != expected_channel_id:
        raise YouTubeCommentConflictError(f"Comment target or ownership mismatch for {comment_id}.")
    if comments_equivalent(current.text, normalized_new):
        return current
    if not comments_equivalent(current.text, expected_text):
        raise YouTubeCommentConflictError(
            f"Comment {comment_id} text changed after review; refusing to overwrite it."
        )

    payload = self._request(
        "PUT",
        "comments",
        params={"part": "snippet"},
        json_body={"id": comment_id, "snippet": {"textOriginal": normalized_new}},
        require_write=True,
    )
    if str(payload.get("id") or "").strip() != comment_id:
        raise YouTubeCommentError(f"YouTube returned an unexpected comment ID after updating {comment_id}.")

    verified = _find_top_level_comment(self, video_id=video_id, comment_id=comment_id)
    if verified is None:
        raise YouTubeCommentError(f"Updated comment {comment_id} was not found during thread verification.")
    if verified.author_channel_id != expected_channel_id or not comments_equivalent(verified.text, normalized_new):
        raise YouTubeCommentError(f"Verification failed after updating comment {comment_id}.")
    return verified


def _run() -> NoReturn:
    YouTubeCommentWriter.create_top_level_comment = _create_top_level_comment_compat  # type: ignore[method-assign]
    YouTubeCommentWriter.update_top_level_comment = _update_top_level_comment_compat  # type: ignore[method-assign]

    from apply_youtube_comment_plan import main

    raise SystemExit(main())


if __name__ == "__main__":
    _run()
