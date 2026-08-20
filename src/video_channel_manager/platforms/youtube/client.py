from __future__ import annotations

import hashlib
import random
import json
import re
import time
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any, TypeAlias

import httpx

from video_channel_manager.domain.enums import ChannelKind, CollectionKind, PlatformName
from video_channel_manager.domain.models import (
    ChannelRecord,
    CollectionMembership,
    CollectionRecord,
    RemoteRef,
    VideoRecord,
)
from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpFailureKind,
    HttpOperationClass,
    HttpTransportFailure,
    RequestRateLimiter,
    RetryPolicy,
    execute_http_request,
    redact_sensitive_text,
)
from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow
from video_channel_manager.platforms.youtube.store import TokenStore

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)
QueryParam: TypeAlias = str | int
QueryParams: TypeAlias = dict[str, QueryParam]


class YouTubeApiError(RuntimeError):
    pass


def _revision(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = _DURATION_RE.fullmatch(value)
    if match is None:
        return None
    parts = {name: int(number or 0) for name, number in match.groupdict().items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _dict_items(payload: dict[str, Any], key: str = "items") -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _best_thumbnail(thumbnails: object) -> str | None:
    if not isinstance(thumbnails, dict):
        return None
    for key in ("maxres", "standard", "high", "medium", "default"):
        item = thumbnails.get(key)
        if isinstance(item, dict) and item.get("url"):
            return str(item["url"])
    return None


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


class YouTubeApiClient(HttpClientOwner):
    """Read-only YouTube Data API client with transparent refresh-token handling."""

    def __init__(
        self,
        *,
        client_config: InstalledClientConfig,
        token_store: TokenStore,
        account_alias: str,
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
        retry_policy: RetryPolicy | None = None,
        request_limiter: RequestRateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self.client_config = client_config
        self.token_store = token_store
        self.account_alias = token_store.validate_alias(account_alias)
        self._initialize_http_client(
            http_client,
            timeout=45.0,
            follow_redirects=True,
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.retry_policy = retry_policy or RetryPolicy()
        self.request_limiter = request_limiter or RequestRateLimiter()
        self._sleep = sleep
        self._jitter = jitter
        self._uploads_playlist_cache: dict[str, str] = {}

    def _get_access_token(self) -> str:
        token = self.token_store.load_token(self.account_alias)
        if token.needs_refresh():
            token = InstalledOAuthFlow(self.client_config, http_client=self._http_client).refresh(token)
            self.token_store.save_token(self.account_alias, token)
        return token.access_token

    def _get(self, resource: str, *, params: QueryParams) -> dict[str, Any]:
        access_token = self._get_access_token()
        try:
            result = execute_http_request(
                lambda: self._http_client.get(
                    f"{self.api_base_url}/{resource.lstrip('/')}",
                    params=httpx.QueryParams(params),
                    headers={"Authorization": f"Bearer {access_token}"},
                ),
                provider="YouTube",
                operation=HttpOperationClass.SAFE_READ,
                method="GET",
                resource=resource,
                retry_policy=self.retry_policy,
                limiter=self.request_limiter,
                sleep=self._sleep,
                jitter=self._jitter,
            )
        except HttpTransportFailure as exc:
            raise YouTubeApiError(str(exc)) from exc

        response = result.response
        if response.status_code >= 400:
            message = response.text
            try:
                error_payload = response.json()
                if isinstance(error_payload, dict):
                    error = _dict_field(error_payload, "error")
                    message = str(error.get("message") or message)
            except ValueError:
                pass
            kind = result.failure_kind or HttpFailureKind.PERMANENT_HTTP
            safe_message = redact_sensitive_text(message, secrets=(access_token,))
            raise YouTubeApiError(
                f"YouTube API {response.status_code} in {resource}: {safe_message} "
                f"[kind={kind.value} attempts={result.attempts}]"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise YouTubeApiError(
                f"YouTube API returned invalid JSON in {resource} "
                f"[kind={HttpFailureKind.INVALID_JSON.value} attempts={result.attempts}]"
            ) from exc
        if not isinstance(payload, dict):
            raise YouTubeApiError(
                f"YouTube API returned a non-object response in {resource} "
                f"[kind={HttpFailureKind.INVALID_PAYLOAD.value} attempts={result.attempts}]"
            )
        return payload

    def _list_all(self, resource: str, *, params: QueryParams) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token
            payload = self._get(resource, params=page_params)
            items.extend(_dict_items(payload))
            next_token = payload.get("nextPageToken")
            if not next_token:
                return items
            page_token = str(next_token)

    def list_my_channels(self) -> list[ChannelRecord]:
        items = self._list_all(
            "channels",
            params={
                "part": "snippet,contentDetails,statistics,status",
                "mine": "true",
                "maxResults": 50,
            },
        )
        records: list[ChannelRecord] = []
        for item in items:
            channel_id = str(item.get("id") or "").strip()
            if not channel_id:
                continue
            snippet = _dict_field(item, "snippet")
            records.append(
                ChannelRecord(
                    ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=channel_id),
                    title=str(snippet.get("title") or channel_id),
                    kind=ChannelKind.VIDEO_CHANNEL,
                    description=str(snippet.get("description") or ""),
                    url=f"https://www.youtube.com/channel/{channel_id}",
                    metadata=item,
                )
            )
        return records

    def _uploads_playlist_id(self, channel_id: str) -> str:
        cached = self._uploads_playlist_cache.get(channel_id)
        if cached is not None:
            return cached
        payload = self._get(
            "channels",
            params={"part": "contentDetails", "id": channel_id, "maxResults": 1},
        )
        items = _dict_items(payload)
        if not items:
            raise YouTubeApiError(f"Channel not found or inaccessible: {channel_id}")
        content = _dict_field(items[0], "contentDetails")
        related = _dict_field(content, "relatedPlaylists")
        uploads = str(related.get("uploads") or "").strip()
        if not uploads:
            raise YouTubeApiError(f"Channel does not expose an uploads playlist: {channel_id}")
        self._uploads_playlist_cache[channel_id] = uploads
        return uploads

    def get_video(self, video_id: str) -> VideoRecord:
        """Read one exact video ID without enumerating the channel uploads playlist."""

        expected_id = video_id.strip()
        if not expected_id:
            raise YouTubeApiError("video_id cannot be blank")
        payload = self._get(
            "videos",
            params={
                "part": "snippet,contentDetails,status,fileDetails",
                "id": expected_id,
                "maxResults": 1,
            },
        )
        items = _dict_items(payload)
        if len(items) != 1:
            raise YouTubeApiError(f"Video not found or inaccessible: {expected_id}")
        raw = items[0]
        actual_id = str(raw.get("id") or "").strip()
        snippet = _dict_field(raw, "snippet")
        channel_id = str(snippet.get("channelId") or "").strip()
        if actual_id != expected_id or not channel_id:
            raise YouTubeApiError(f"YouTube returned an invalid video record for: {expected_id}")
        details = _dict_field(raw, "contentDetails")
        status = _dict_field(raw, "status")
        raw_tags = snippet.get("tags")
        return VideoRecord(
            ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=actual_id),
            title=str(snippet.get("title") or actual_id),
            description=str(snippet.get("description") or ""),
            duration_seconds=_parse_duration(str(details.get("duration") or "")),
            published_at=_parse_datetime(str(snippet.get("publishedAt") or "")),
            privacy_status=str(status.get("privacyStatus") or "") or None,
            tags=[str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else [],
            thumbnail_url=_best_thumbnail(snippet.get("thumbnails")),
            revision=_revision(raw),
            metadata=raw,
        )

    def list_videos(self, channel_id: str) -> list[VideoRecord]:
        uploads_playlist = self._uploads_playlist_id(channel_id)
        playlist_items = self._list_all(
            "playlistItems",
            params={
                "part": "contentDetails",
                "playlistId": uploads_playlist,
                "maxResults": 50,
            },
        )
        ordered_ids: list[str] = []
        for item in playlist_items:
            video_id = str(_dict_field(item, "contentDetails").get("videoId") or "").strip()
            if video_id:
                ordered_ids.append(video_id)

        raw_by_id: dict[str, dict[str, Any]] = {}
        for batch in _chunks(ordered_ids, 50):
            payload = self._get(
                "videos",
                params={
                    "part": "snippet,contentDetails,status,fileDetails",
                    "id": ",".join(batch),
                    "maxResults": 50,
                },
            )
            for raw_item in _dict_items(payload):
                item_id = str(raw_item.get("id") or "").strip()
                if item_id:
                    raw_by_id[item_id] = raw_item

        missing_ids = [video_id for video_id in ordered_ids if video_id not in raw_by_id]
        if missing_ids:
            raise YouTubeApiError(
                "YouTube videos.list omitted upload IDs from the owner uploads playlist: " + ",".join(missing_ids)
            )

        records: list[VideoRecord] = []
        for video_id in ordered_ids:
            video_payload = raw_by_id[video_id]
            snippet = _dict_field(video_payload, "snippet")
            details = _dict_field(video_payload, "contentDetails")
            status = _dict_field(video_payload, "status")
            raw_tags = snippet.get("tags")
            records.append(
                VideoRecord(
                    ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=video_id),
                    title=str(snippet.get("title") or video_id),
                    description=str(snippet.get("description") or ""),
                    duration_seconds=_parse_duration(str(details.get("duration") or "")),
                    published_at=_parse_datetime(str(snippet.get("publishedAt") or "")),
                    privacy_status=str(status.get("privacyStatus") or "") or None,
                    tags=[str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else [],
                    thumbnail_url=_best_thumbnail(snippet.get("thumbnails")),
                    revision=_revision(video_payload),
                    metadata=video_payload,
                )
            )
        return records

    def list_collections(self, channel_id: str) -> list[CollectionRecord]:
        items = self._list_all(
            "playlists",
            params={
                "part": "snippet,status,contentDetails",
                "mine": "true",
                "maxResults": 50,
            },
        )
        records: list[CollectionRecord] = []
        for item in items:
            playlist_id = str(item.get("id") or "").strip()
            snippet = _dict_field(item, "snippet")
            if not playlist_id or str(snippet.get("channelId") or "") != channel_id:
                continue
            status = _dict_field(item, "status")
            records.append(
                CollectionRecord(
                    ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=playlist_id),
                    title=str(snippet.get("title") or playlist_id),
                    kind=CollectionKind.PLAYLIST,
                    description=str(snippet.get("description") or ""),
                    privacy_status=str(status.get("privacyStatus") or "") or None,
                    revision=_revision(item),
                    metadata=item,
                )
            )
        return records

    def list_memberships(
        self,
        *,
        channel_id: str,
        collections: list[CollectionRecord],
        known_video_ids: set[str],
    ) -> list[CollectionMembership]:
        memberships: list[CollectionMembership] = []
        for collection in collections:
            items = self._list_all(
                "playlistItems",
                params={
                    "part": "id,snippet,contentDetails",
                    "playlistId": collection.ref.remote_id,
                    "maxResults": 50,
                },
            )
            for item in items:
                content = _dict_field(item, "contentDetails")
                snippet = _dict_field(item, "snippet")
                video_id = str(content.get("videoId") or "").strip()
                if not video_id or video_id not in known_video_ids:
                    continue
                position = snippet.get("position")
                memberships.append(
                    CollectionMembership(
                        collection_ref=collection.ref,
                        video_ref=RemoteRef(
                            platform=PlatformName.YOUTUBE,
                            channel_id=channel_id,
                            remote_id=video_id,
                        ),
                        position=int(position) if isinstance(position, int) else None,
                        membership_id=str(item.get("id") or "") or None,
                        revision=_revision(item),
                    )
                )
        return memberships
