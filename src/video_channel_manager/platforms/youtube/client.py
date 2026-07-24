from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import httpx

from video_channel_manager.domain.enums import ChannelKind, CollectionKind, PlatformName
from video_channel_manager.domain.models import ChannelRecord, CollectionMembership, CollectionRecord, RemoteRef, VideoRecord
from video_channel_manager.platforms.youtube.models import InstalledClientConfig
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow
from video_channel_manager.platforms.youtube.store import TokenStore

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


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


def _best_thumbnail(thumbnails: dict[str, Any] | None) -> str | None:
    thumbnails = thumbnails or {}
    for key in ("maxres", "standard", "high", "medium", "default"):
        item = thumbnails.get(key)
        if isinstance(item, dict) and item.get("url"):
            return str(item["url"])
    return None


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


class YouTubeApiClient:
    """Read-only YouTube Data API client with transparent refresh-token handling."""

    def __init__(
        self,
        *,
        client_config: InstalledClientConfig,
        token_store: TokenStore,
        account_alias: str,
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
    ) -> None:
        self.client_config = client_config
        self.token_store = token_store
        self.account_alias = token_store.validate_alias(account_alias)
        self._http_client = http_client
        self.api_base_url = api_base_url.rstrip("/")

    def _get_access_token(self) -> str:
        token = self.token_store.load_token(self.account_alias)
        if token.needs_refresh():
            token = InstalledOAuthFlow(self.client_config, http_client=self._http_client).refresh(token)
            self.token_store.save_token(self.account_alias, token)
        return token.access_token

    def _get(self, resource: str, *, params: dict[str, object]) -> dict[str, Any]:
        client = self._http_client or httpx.Client(timeout=45.0, follow_redirects=True)
        close_client = self._http_client is None
        try:
            response = client.get(
                f"{self.api_base_url}/{resource.lstrip('/')}",
                params=params,
                headers={"Authorization": f"Bearer {self._get_access_token()}"},
            )
            if response.status_code >= 400:
                message = response.text[:500]
                try:
                    payload = response.json()
                    message = str(payload.get("error", {}).get("message") or message)
                except ValueError:
                    pass
                raise YouTubeApiError(f"YouTube API {response.status_code}: {message}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise YouTubeApiError("YouTube API returned a non-object response.")
            return payload
        except httpx.HTTPError as exc:
            raise YouTubeApiError(f"YouTube API request failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

    def _list_all(self, resource: str, *, params: dict[str, object]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            page_params = dict(params)
            if page_token:
                page_params["pageToken"] = page_token
            payload = self._get(resource, params=page_params)
            raw_items = payload.get("items", [])
            if isinstance(raw_items, list):
                items.extend(item for item in raw_items if isinstance(item, dict))
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
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
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
        payload = self._get(
            "channels",
            params={"part": "contentDetails", "id": channel_id, "maxResults": 1},
        )
        items = payload.get("items", [])
        if not items:
            raise YouTubeApiError(f"Channel not found or inaccessible: {channel_id}")
        content = items[0].get("contentDetails", {})
        related = content.get("relatedPlaylists", {}) if isinstance(content, dict) else {}
        uploads = str(related.get("uploads") or "").strip()
        if not uploads:
            raise YouTubeApiError(f"Channel does not expose an uploads playlist: {channel_id}")
        return uploads

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
        video_ids = [
            str(item.get("contentDetails", {}).get("videoId") or "")
            for item in playlist_items
            if isinstance(item.get("contentDetails"), dict)
        ]
        ordered_ids = [video_id for video_id in video_ids if video_id]
        raw_by_id: dict[str, dict[str, Any]] = {}
        for batch in _chunks(ordered_ids, 50):
            payload = self._get(
                "videos",
                params={
                    "part": "snippet,contentDetails,status",
                    "id": ",".join(batch),
                    "maxResults": 50,
                },
            )
            for item in payload.get("items", []):
                if isinstance(item, dict) and item.get("id"):
                    raw_by_id[str(item["id"])] = item

        records: list[VideoRecord] = []
        for video_id in ordered_ids:
            item = raw_by_id.get(video_id)
            if item is None:
                continue
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            details = item.get("contentDetails") if isinstance(item.get("contentDetails"), dict) else {}
            status = item.get("status") if isinstance(item.get("status"), dict) else {}
            records.append(
                VideoRecord(
                    ref=RemoteRef(platform=PlatformName.YOUTUBE, channel_id=channel_id, remote_id=video_id),
                    title=str(snippet.get("title") or video_id),
                    description=str(snippet.get("description") or ""),
                    duration_seconds=_parse_duration(str(details.get("duration") or "")),
                    published_at=_parse_datetime(str(snippet.get("publishedAt") or "")),
                    privacy_status=str(status.get("privacyStatus") or "") or None,
                    tags=[str(tag) for tag in snippet.get("tags", [])] if isinstance(snippet.get("tags"), list) else [],
                    thumbnail_url=_best_thumbnail(snippet.get("thumbnails")),
                    revision=_revision(item),
                    metadata=item,
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
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            if not playlist_id or str(snippet.get("channelId") or "") != channel_id:
                continue
            status = item.get("status") if isinstance(item.get("status"), dict) else {}
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
                content = item.get("contentDetails") if isinstance(item.get("contentDetails"), dict) else {}
                snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
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
