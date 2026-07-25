from __future__ import annotations

import sys
import time
from typing import Any, NoReturn, TextIO

from video_channel_manager.platforms.youtube.comments import (
    TopLevelCommentSnapshot,
    YouTubeCommentConflictError,
    YouTubeCommentError,
    YouTubeCommentWriter,
    canonicalize_comment_text,
    comments_equivalent,
    validate_comment_text,
)

_MODERATION_STATES = ("published", "heldForReview", "likelySpam")
_VERIFY_DELAYS_SECONDS = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0)


def _configure_utf8_stream(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def _configure_utf8_stdio() -> None:
    _configure_utf8_stream(sys.stdout)
    _configure_utf8_stream(sys.stderr)


def _author_channel_id(snippet: dict[str, Any]) -> str | None:
    raw = snippet.get("authorChannelId")
    if not isinstance(raw, dict):
        return None
    value = str(raw.get("value") or "").strip()
    return value or None


def _comment_snapshot_from_direct_resource(
    comment: dict[str, Any],
    *,
    video_id: str,
    channel_id: str,
) -> TopLevelCommentSnapshot | None:
    comment_id = str(comment.get("id") or "").strip()
    snippet = comment.get("snippet")
    if not comment_id or not isinstance(snippet, dict):
        return None
    text = str(snippet.get("textOriginal") or snippet.get("textDisplay") or "")
    return TopLevelCommentSnapshot(
        thread_id=str(snippet.get("parentId") or comment_id),
        comment_id=comment_id,
        video_id=video_id,
        channel_id=channel_id,
        author_channel_id=_author_channel_id(snippet),
        author_display_name=str(snippet.get("authorDisplayName") or ""),
        text=canonicalize_comment_text(text),
        published_at=None,
        updated_at=None,
        moderation_status=str(snippet.get("moderationStatus") or "").strip() or None,
        raw=comment,
    )


def _read_comment_with_context(
    writer: YouTubeCommentWriter,
    *,
    comment_id: str,
    video_id: str,
    channel_id: str,
) -> TopLevelCommentSnapshot | None:
    payload = writer._request(  # type: ignore[attr-defined]
        "GET",
        "comments",
        params={"part": "snippet", "id": comment_id, "textFormat": "plainText"},
    )
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict) or str(item.get("id") or "").strip() != comment_id:
            continue
        return _comment_snapshot_from_direct_resource(item, video_id=video_id, channel_id=channel_id)
    return None


def _list_top_level_comments_compat(
    self: YouTubeCommentWriter,
    video_id: str,
) -> list[TopLevelCommentSnapshot]:
    records: list[TopLevelCommentSnapshot] = []
    seen_comment_ids: set[str] = set()

    for moderation_status in _MODERATION_STATES:
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 100,
                "textFormat": "plainText",
                "order": "time",
                "moderationStatus": moderation_status,
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                payload = self._request("GET", "commentThreads", params=params)  # type: ignore[attr-defined]
            except YouTubeCommentError:
                if moderation_status == "published":
                    raise
                break

            items = payload.get("items")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    snapshot = self._parse_thread(item)  # type: ignore[attr-defined]
                    if snapshot.comment_id in seen_comment_ids:
                        continue
                    seen_comment_ids.add(snapshot.comment_id)
                    records.append(snapshot)

            next_token = str(payload.get("nextPageToken") or "").strip()
            if not next_token:
                break
            page_token = next_token

    return records


def _find_top_level_comment(
    writer: YouTubeCommentWriter,
    *,
    video_id: str,
    channel_id: str,
    comment_id: str,
) -> TopLevelCommentSnapshot | None:
    direct = _read_comment_with_context(
        writer,
        comment_id=comment_id,
        video_id=video_id,
        channel_id=channel_id,
    )
    if direct is not None:
        return direct
    return next(
        (item for item in writer.list_top_level_comments(video_id) if item.comment_id == comment_id),
        None,
    )


def _verify_comment_eventually(
    writer: YouTubeCommentWriter,
    *,
    video_id: str,
    channel_id: str,
    comment_id: str,
    expected_text: str,
    fallback: TopLevelCommentSnapshot,
) -> TopLevelCommentSnapshot:
    last_error: YouTubeCommentError | None = None
    for delay in _VERIFY_DELAYS_SECONDS:
        if delay:
            time.sleep(delay)
        try:
            verified = _find_top_level_comment(
                writer,
                video_id=video_id,
                channel_id=channel_id,
                comment_id=comment_id,
            )
        except YouTubeCommentError as exc:
            last_error = exc
            continue
        if verified is None:
            continue
        if verified.author_channel_id != channel_id:
            raise YouTubeCommentError(f"Comment {comment_id} is not authored by the expected channel.")
        if not comments_equivalent(verified.text, expected_text):
            raise YouTubeCommentError(f"Verification found unexpected text for comment {comment_id}.")
        return verified

    if fallback.author_channel_id == channel_id and comments_equivalent(fallback.text, expected_text):
        print(
            f"WARNING: comment {comment_id} is not indexed in list results yet; "
            "the successful API write response is retained and the final postflight will retry.",
            file=sys.stderr,
        )
        return fallback

    if last_error is not None:
        raise last_error
    raise YouTubeCommentError(f"Comment {comment_id} was not available for verification after retries.")


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

    payload = self._request(  # type: ignore[attr-defined]
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
    created = self._parse_thread(payload)  # type: ignore[attr-defined]
    if created.video_id != video_id or created.channel_id != expected_channel_id:
        raise YouTubeCommentError(f"YouTube created a comment on an unexpected target for {video_id}.")
    if created.author_channel_id != expected_channel_id or not comments_equivalent(created.text, normalized):
        raise YouTubeCommentError(f"YouTube returned an unexpected created comment for {video_id}.")

    return _verify_comment_eventually(
        self,
        video_id=video_id,
        channel_id=expected_channel_id,
        comment_id=created.comment_id,
        expected_text=normalized,
        fallback=created,
    )


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
    current = _find_top_level_comment(
        self,
        video_id=video_id,
        channel_id=expected_channel_id,
        comment_id=comment_id,
    )
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

    payload = self._request(  # type: ignore[attr-defined]
        "PUT",
        "comments",
        params={"part": "snippet"},
        json_body={"id": comment_id, "snippet": {"textOriginal": normalized_new}},
        require_write=True,
    )
    updated = _comment_snapshot_from_direct_resource(
        payload,
        video_id=video_id,
        channel_id=expected_channel_id,
    )
    if updated is None or updated.comment_id != comment_id:
        raise YouTubeCommentError(f"YouTube returned an unexpected comment after updating {comment_id}.")

    return _verify_comment_eventually(
        self,
        video_id=video_id,
        channel_id=expected_channel_id,
        comment_id=comment_id,
        expected_text=normalized_new,
        fallback=updated,
    )


def _run() -> NoReturn:
    _configure_utf8_stdio()
    YouTubeCommentWriter.list_top_level_comments = _list_top_level_comments_compat  # type: ignore[method-assign]
    YouTubeCommentWriter.create_top_level_comment = _create_top_level_comment_compat  # type: ignore[method-assign]
    YouTubeCommentWriter.update_top_level_comment = _update_top_level_comment_compat  # type: ignore[method-assign]

    from apply_youtube_comment_plan import main

    raise SystemExit(main())


if __name__ == "__main__":
    _run()
