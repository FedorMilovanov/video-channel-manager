from __future__ import annotations

import hashlib
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeAlias

import httpx

from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow, YOUTUBE_FORCE_SSL_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore
from video_channel_manager.platforms.youtube.writer import YouTubeWriteError, YouTubeWriteScopeError

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
_COMMENT_TEXT_LIMIT = 8000
_MODERATION_STATES = ("published", "heldForReview", "likelySpam")
_DEFAULT_VERIFY_DELAYS_SECONDS = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0)
QueryParam: TypeAlias = str | int
QueryParams: TypeAlias = dict[str, QueryParam]


class YouTubeCommentError(YouTubeWriteError):
    pass


class YouTubeCommentsDisabledError(YouTubeCommentError):
    pass


class YouTubeCommentConflictError(YouTubeCommentError):
    pass


@dataclass(frozen=True, slots=True)
class VideoIdentity:
    video_id: str
    channel_id: str
    title: str
    privacy_status: str | None


@dataclass(frozen=True, slots=True)
class TopLevelCommentSnapshot:
    thread_id: str
    comment_id: str
    video_id: str
    channel_id: str
    author_channel_id: str | None
    author_display_name: str
    text: str
    published_at: datetime | None
    updated_at: datetime | None
    moderation_status: str | None
    raw: dict[str, Any]

    @property
    def text_sha256(self) -> str:
        return comment_text_sha256(self.text)


def canonicalize_comment_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip()


def comments_equivalent(left: str, right: str) -> bool:
    return canonicalize_comment_text(left) == canonicalize_comment_text(right)


def comment_text_sha256(value: str) -> str:
    encoded = canonicalize_comment_text(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_comment_text(value: str) -> str:
    normalized = canonicalize_comment_text(value)
    if not normalized:
        raise ValueError("YouTube comment text cannot be blank.")
    if len(normalized) > _COMMENT_TEXT_LIMIT:
        raise ValueError(
            f"YouTube comment text is {len(normalized)} characters; the project safety limit is {_COMMENT_TEXT_LIMIT}."
        )
    return normalized


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _dict_items(payload: dict[str, Any], key: str = "items") -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _error_reason(payload: dict[str, Any]) -> str | None:
    error = _dict_field(payload, "error")
    errors = error.get("errors")
    if not isinstance(errors, list):
        return None
    for item in errors:
        if isinstance(item, dict) and item.get("reason"):
            return str(item["reason"])
    return None


def _author_channel_id(snippet: dict[str, Any]) -> str | None:
    raw = snippet.get("authorChannelId")
    if not isinstance(raw, dict):
        return None
    value = str(raw.get("value") or "").strip()
    return value or None


class YouTubeCommentWriter:
    """Read and guardedly write top-level comments through YouTube Data API v3.

    The writer deliberately reads every moderation view available to the
    authenticated channel and performs bounded eventual verification after a
    successful mutation. This prevents duplicate creates when YouTube accepts a
    write before the comment is visible in the default thread listing.
    """

    def __init__(
        self,
        *,
        client_config: InstalledClientConfig,
        token_store: TokenStore,
        account_alias: str,
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
        verify_delays_seconds: tuple[float, ...] = _DEFAULT_VERIFY_DELAYS_SECONDS,
    ) -> None:
        self.client_config = client_config
        self.token_store = token_store
        self.account_alias = token_store.validate_alias(account_alias)
        self._http_client = http_client
        self.api_base_url = api_base_url.rstrip("/")
        cleaned_delays = tuple(max(0.0, float(item)) for item in verify_delays_seconds)
        self.verify_delays_seconds = cleaned_delays or (0.0,)

    def _token(self, *, require_write: bool) -> OAuthToken:
        token = self.token_store.load_token(self.account_alias)
        if token.needs_refresh():
            token = InstalledOAuthFlow(self.client_config, http_client=self._http_client).refresh(token)
            self.token_store.save_token(self.account_alias, token)
        if require_write and YOUTUBE_FORCE_SSL_SCOPE not in token.scopes:
            raise YouTubeWriteScopeError(
                "Stored token is read-only. Re-authorize with: "
                f"video-manager youtube login --account {self.account_alias} --write --force"
            )
        return token

    def _request(
        self,
        method: str,
        resource: str,
        *,
        params: QueryParams,
        json_body: dict[str, Any] | None = None,
        require_write: bool = False,
    ) -> dict[str, Any]:
        client = self._http_client or httpx.Client(timeout=45.0, follow_redirects=True)
        close_client = self._http_client is None
        try:
            response = client.request(
                method,
                f"{self.api_base_url}/{resource.lstrip('/')}",
                params=httpx.QueryParams(params),
                headers={"Authorization": f"Bearer {self._token(require_write=require_write).access_token}"},
                json=json_body,
            )
            if response.status_code >= 400:
                message = response.text[:500]
                reason: str | None = None
                try:
                    payload = response.json()
                    if isinstance(payload, dict):
                        error = _dict_field(payload, "error")
                        message = str(error.get("message") or message)
                        reason = _error_reason(payload)
                except ValueError:
                    pass
                if reason == "commentsDisabled":
                    raise YouTubeCommentsDisabledError(message)
                raise YouTubeCommentError(
                    f"YouTube API {response.status_code}" + (f" ({reason})" if reason else "") + f": {message}"
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise YouTubeCommentError("YouTube API returned a non-object response.")
            return payload
        except httpx.HTTPError as exc:
            raise YouTubeCommentError(f"YouTube API request failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

    def read_video_identity(self, video_id: str) -> VideoIdentity:
        payload = self._request(
            "GET",
            "videos",
            params={"part": "snippet,status", "id": video_id, "maxResults": 1},
        )
        items = _dict_items(payload)
        if not items:
            raise YouTubeCommentError(f"Video not found or inaccessible: {video_id}")
        raw = items[0]
        snippet = _dict_field(raw, "snippet")
        status = _dict_field(raw, "status")
        actual_id = str(raw.get("id") or "").strip()
        channel_id = str(snippet.get("channelId") or "").strip()
        if actual_id != video_id or not channel_id:
            raise YouTubeCommentError(f"YouTube returned an invalid video record for: {video_id}")
        privacy_status = str(status.get("privacyStatus") or "").strip() or None
        return VideoIdentity(
            video_id=video_id,
            channel_id=channel_id,
            title=str(snippet.get("title") or video_id),
            privacy_status=privacy_status,
        )

    def _parse_thread(self, item: dict[str, Any]) -> TopLevelCommentSnapshot:
        thread_id = str(item.get("id") or "").strip()
        thread_snippet = _dict_field(item, "snippet")
        top_level = _dict_field(thread_snippet, "topLevelComment")
        comment_id = str(top_level.get("id") or "").strip()
        comment_snippet = _dict_field(top_level, "snippet")
        video_id = str(thread_snippet.get("videoId") or comment_snippet.get("videoId") or "").strip()
        channel_id = str(thread_snippet.get("channelId") or comment_snippet.get("channelId") or "").strip()
        text = str(comment_snippet.get("textOriginal") or comment_snippet.get("textDisplay") or "")
        if not thread_id or not comment_id or not video_id or not channel_id:
            raise YouTubeCommentError("YouTube returned an incomplete comment thread.")
        return TopLevelCommentSnapshot(
            thread_id=thread_id,
            comment_id=comment_id,
            video_id=video_id,
            channel_id=channel_id,
            author_channel_id=_author_channel_id(comment_snippet),
            author_display_name=str(comment_snippet.get("authorDisplayName") or ""),
            text=canonicalize_comment_text(text),
            published_at=_parse_datetime(comment_snippet.get("publishedAt")),
            updated_at=_parse_datetime(comment_snippet.get("updatedAt")),
            moderation_status=str(comment_snippet.get("moderationStatus") or "").strip() or None,
            raw=item,
        )

    def _parse_direct_comment(
        self,
        comment: dict[str, Any],
        *,
        video_id: str,
        channel_id: str,
    ) -> TopLevelCommentSnapshot:
        comment_id = str(comment.get("id") or "").strip()
        snippet = _dict_field(comment, "snippet")
        direct_video_id = str(snippet.get("videoId") or "").strip()
        direct_channel_id = str(snippet.get("channelId") or "").strip()
        if not comment_id:
            raise YouTubeCommentError("YouTube returned an invalid direct comment record.")
        if direct_video_id and direct_video_id != video_id:
            raise YouTubeCommentError(f"Direct comment {comment_id} belongs to unexpected video {direct_video_id}.")
        if direct_channel_id and direct_channel_id != channel_id:
            raise YouTubeCommentError(f"Direct comment {comment_id} belongs to unexpected channel {direct_channel_id}.")
        text = str(snippet.get("textOriginal") or snippet.get("textDisplay") or "")
        return TopLevelCommentSnapshot(
            thread_id=str(snippet.get("parentId") or comment_id),
            comment_id=comment_id,
            video_id=video_id,
            channel_id=channel_id,
            author_channel_id=_author_channel_id(snippet),
            author_display_name=str(snippet.get("authorDisplayName") or ""),
            text=canonicalize_comment_text(text),
            published_at=_parse_datetime(snippet.get("publishedAt")),
            updated_at=_parse_datetime(snippet.get("updatedAt")),
            moderation_status=str(snippet.get("moderationStatus") or "").strip() or None,
            raw=comment,
        )

    def list_top_level_comments(self, video_id: str) -> list[TopLevelCommentSnapshot]:
        records: list[TopLevelCommentSnapshot] = []
        seen_comment_ids: set[str] = set()
        for moderation_status in _MODERATION_STATES:
            page_token: str | None = None
            while True:
                params: QueryParams = {
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
                    payload = self._request("GET", "commentThreads", params=params)
                except YouTubeCommentError:
                    if moderation_status == "published":
                        raise
                    break
                for item in _dict_items(payload):
                    snapshot = self._parse_thread(item)
                    if snapshot.comment_id in seen_comment_ids:
                        continue
                    seen_comment_ids.add(snapshot.comment_id)
                    records.append(snapshot)
                next_token = str(payload.get("nextPageToken") or "").strip()
                if not next_token:
                    break
                page_token = next_token
        return records

    def read_comment(
        self,
        comment_id: str,
        *,
        video_id: str | None = None,
        channel_id: str | None = None,
    ) -> TopLevelCommentSnapshot:
        payload = self._request(
            "GET",
            "comments",
            params={"part": "snippet", "id": comment_id, "textFormat": "plainText"},
        )
        items = _dict_items(payload)
        if not items:
            raise YouTubeCommentError(f"Comment not found or inaccessible: {comment_id}")
        comment = items[0]
        snippet = _dict_field(comment, "snippet")
        actual_id = str(comment.get("id") or "").strip()
        resolved_video_id = str(snippet.get("videoId") or video_id or "").strip()
        resolved_channel_id = str(snippet.get("channelId") or channel_id or "").strip()
        if actual_id != comment_id or not resolved_video_id or not resolved_channel_id:
            raise YouTubeCommentError(f"YouTube returned an invalid comment record for: {comment_id}")
        return self._parse_direct_comment(
            comment,
            video_id=resolved_video_id,
            channel_id=resolved_channel_id,
        )

    def _find_top_level_comment(
        self,
        *,
        comment_id: str,
        video_id: str,
        channel_id: str,
    ) -> TopLevelCommentSnapshot | None:
        try:
            direct = self.read_comment(comment_id, video_id=video_id, channel_id=channel_id)
        except YouTubeCommentError:
            direct = None
        if direct is not None:
            return direct
        return next(
            (item for item in self.list_top_level_comments(video_id) if item.comment_id == comment_id),
            None,
        )

    def _verify_comment_eventually(
        self,
        *,
        video_id: str,
        channel_id: str,
        comment_id: str,
        expected_text: str,
        fallback: TopLevelCommentSnapshot,
    ) -> TopLevelCommentSnapshot:
        last_error: YouTubeCommentError | None = None
        for delay in self.verify_delays_seconds:
            if delay:
                time.sleep(delay)
            try:
                verified = self._find_top_level_comment(
                    comment_id=comment_id,
                    video_id=video_id,
                    channel_id=channel_id,
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
            return fallback
        if last_error is not None:
            raise last_error
        raise YouTubeCommentError(f"Comment {comment_id} was not available for verification after retries.")

    def create_top_level_comment(
        self,
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
        if created.author_channel_id != expected_channel_id or not comments_equivalent(created.text, normalized):
            raise YouTubeCommentError(f"YouTube returned an unexpected created comment for {video_id}.")
        return self._verify_comment_eventually(
            video_id=video_id,
            channel_id=expected_channel_id,
            comment_id=created.comment_id,
            expected_text=normalized,
            fallback=created,
        )

    def update_top_level_comment(
        self,
        *,
        comment_id: str,
        video_id: str,
        expected_channel_id: str,
        expected_text: str,
        new_text: str,
    ) -> TopLevelCommentSnapshot:
        normalized_new = validate_comment_text(new_text)
        current = self._find_top_level_comment(
            comment_id=comment_id,
            video_id=video_id,
            channel_id=expected_channel_id,
        )
        if current is None:
            raise YouTubeCommentConflictError(f"Top-level comment {comment_id} was not found on video {video_id}.")
        if current.video_id != video_id or current.channel_id != expected_channel_id:
            raise YouTubeCommentConflictError(f"Comment target mismatch for {comment_id}.")
        if current.author_channel_id != expected_channel_id:
            raise YouTubeCommentConflictError(f"Comment {comment_id} is not authored by the expected channel.")
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
        updated = self._parse_direct_comment(
            payload,
            video_id=video_id,
            channel_id=expected_channel_id,
        )
        if updated.comment_id != comment_id:
            raise YouTubeCommentError(f"YouTube returned an unexpected comment ID after updating {comment_id}.")
        return self._verify_comment_eventually(
            video_id=video_id,
            channel_id=expected_channel_id,
            comment_id=comment_id,
            expected_text=normalized_new,
            fallback=updated,
        )


__all__ = [
    "TopLevelCommentSnapshot",
    "VideoIdentity",
    "YouTubeCommentConflictError",
    "YouTubeCommentError",
    "YouTubeCommentWriter",
    "YouTubeCommentsDisabledError",
    "canonicalize_comment_text",
    "comment_text_sha256",
    "comments_equivalent",
    "validate_comment_text",
]
