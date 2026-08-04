from __future__ import annotations

import hashlib
import random
import json
import time
from datetime import UTC, datetime
from collections.abc import Callable
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
from video_channel_manager.platforms.vk.models import VkCommunityIdentity, VkUserIdentity
from video_channel_manager.platforms.vk.store import VkTokenStore

_API_BASE_URL = "https://api.vk.com/method"
_RETRYABLE_API_CODES = frozenset({6, 9, 10, 29})
_RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
ApiParam: TypeAlias = str | int | bool
ApiParams: TypeAlias = dict[str, ApiParam]


class VkApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        method: str,
        code: int | None = None,
        retryable: bool = False,
        kind: HttpFailureKind | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.method = method
        self.code = code
        self.retryable = retryable
        self.kind = kind
        self.attempts = attempts



def _provider_response_kind(response: httpx.Response) -> HttpFailureKind | None:
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    raw_error = payload.get("error")
    if not isinstance(raw_error, dict):
        return None
    raw_code = raw_error.get("error_code")
    code = int(raw_code) if isinstance(raw_code, int | str) and str(raw_code).isdigit() else None
    return HttpFailureKind.PROVIDER_TRANSIENT if code in _RETRYABLE_API_CODES else HttpFailureKind.PROVIDER_ERROR

def _revision(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _dict_items(payload: object, key: str = "items") -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _unix_datetime(value: object) -> datetime | None:
    if not isinstance(value, int) or value < 0:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def _best_image(images: object) -> str | None:
    if not isinstance(images, list):
        return None
    candidates: list[tuple[int, str]] = []
    for image in images:
        if not isinstance(image, dict) or not image.get("url"):
            continue
        width = image.get("width")
        height = image.get("height")
        area = (width if isinstance(width, int) else 0) * (height if isinstance(height, int) else 0)
        candidates.append((area, str(image["url"])))
    return max(candidates, default=(0, ""))[1] or None


def _video_remote_id(payload: dict[str, Any]) -> str | None:
    owner_id = payload.get("owner_id")
    video_id = payload.get("id")
    if not isinstance(owner_id, int) or not isinstance(video_id, int):
        return None
    return f"{owner_id}_{video_id}"


def _community_url(payload: dict[str, Any], community_id: int) -> str:
    screen_name = str(payload.get("screen_name") or "").strip()
    return f"https://vk.com/{screen_name}" if screen_name else f"https://vk.com/club{community_id}"


class VkApiClient(HttpClientOwner):
    """Read-only VK API 5.199 client using a locally stored user access token."""

    def __init__(
        self,
        *,
        token_store: VkTokenStore,
        account_alias: str,
        api_version: str = "5.199",
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
        max_attempts: int = 4,
        retry_policy: RetryPolicy | None = None,
        request_limiter: RequestRateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self.token_store = token_store
        self.account_alias = token_store.validate_alias(account_alias)
        self.api_version = api_version
        self._initialize_http_client(
            http_client,
            timeout=45.0,
            follow_redirects=True,
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.max_attempts = max(1, max_attempts)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=self.max_attempts,
            base_delay_seconds=0.35,
            max_delay_seconds=4.0,
        )
        self.request_limiter = request_limiter or RequestRateLimiter()
        self._sleep = sleep
        self._jitter = jitter

    def _call(self, method: str, *, params: ApiParams | None = None) -> object:
        token = self.token_store.load_token(self.account_alias)
        if token.is_expired():
            raise VkApiError(
                "VK access token is expired. Import a fresh user token with 'video' and 'groups' permissions.",
                method=method,
                code=5,
                kind=HttpFailureKind.PROVIDER_ERROR,
            )

        request_data: dict[str, str] = {
            "access_token": token.access_token,
            "v": self.api_version,
        }
        for key, value in (params or {}).items():
            if isinstance(value, bool):
                request_data[key] = "1" if value else "0"
            else:
                request_data[key] = str(value)

        try:
            result = execute_http_request(
                lambda: self._http_client.post(
                    f"{self.api_base_url}/{method}",
                    data=request_data,
                    headers={"User-Agent": "video-channel-manager/0.1"},
                ),
                provider="VK",
                operation=HttpOperationClass.SAFE_READ,
                method="POST",
                resource=method,
                retry_policy=self.retry_policy,
                limiter=self.request_limiter,
                response_classifier=_provider_response_kind,
                sleep=self._sleep,
                jitter=self._jitter,
            )
        except HttpTransportFailure as exc:
            raise VkApiError(
                str(exc),
                method=method,
                retryable=True,
                kind=exc.kind,
                attempts=exc.attempts,
            ) from exc

        response = result.response
        if response.status_code >= 400:
            kind = result.failure_kind or HttpFailureKind.PERMANENT_HTTP
            raise VkApiError(
                f"VK API HTTP {response.status_code} while calling {method} "
                f"[kind={kind.value} attempts={result.attempts}]",
                method=method,
                retryable=kind in {HttpFailureKind.RATE_LIMIT, HttpFailureKind.TRANSIENT_HTTP},
                kind=kind,
                attempts=result.attempts,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise VkApiError(
                f"VK API returned invalid JSON in {method} "
                f"[kind={HttpFailureKind.INVALID_JSON.value} attempts={result.attempts}]",
                method=method,
                kind=HttpFailureKind.INVALID_JSON,
                attempts=result.attempts,
            ) from exc
        if not isinstance(payload, dict):
            raise VkApiError(
                f"VK API returned a non-object response in {method} "
                f"[kind={HttpFailureKind.INVALID_PAYLOAD.value} attempts={result.attempts}]",
                method=method,
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            )
        raw_error = payload.get("error")
        if isinstance(raw_error, dict):
            raw_code = raw_error.get("error_code")
            code = int(raw_code) if isinstance(raw_code, int | str) and str(raw_code).isdigit() else None
            message = redact_sensitive_text(
                raw_error.get("error_msg") or "Unknown VK API error",
                secrets=(token.access_token,),
            )
            kind = result.failure_kind or HttpFailureKind.PROVIDER_ERROR
            raise VkApiError(
                f"VK API {code or 'error'} in {method}: {message} "
                f"[kind={kind.value} attempts={result.attempts}]",
                method=method,
                code=code,
                retryable=code in _RETRYABLE_API_CODES,
                kind=kind,
                attempts=result.attempts,
            )
        if "response" not in payload:
            raise VkApiError(
                f"VK API response has no 'response' field in {method} "
                f"[kind={HttpFailureKind.INVALID_PAYLOAD.value} attempts={result.attempts}]",
                method=method,
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            )
        return payload["response"]

    def _list_offset(self, method: str, *, params: ApiParams, page_size: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        while True:
            page_params = dict(params)
            page_params["offset"] = offset
            page_params["count"] = page_size
            response = self._call(method, params=page_params)
            page = _dict_items(response)
            items.extend(page)
            total = response.get("count") if isinstance(response, dict) else None
            offset += len(page)

            if not page:
                return items
            if isinstance(total, int):
                if offset >= total:
                    return items
                continue
            if len(page) < page_size:
                return items

    def get_current_user(self) -> VkUserIdentity:
        response = self._call("users.get", params={"fields": "screen_name"})
        users = [item for item in response if isinstance(item, dict)] if isinstance(response, list) else []
        if not users:
            raise VkApiError("VK users.get returned no current user.", method="users.get")
        user = users[0]
        user_id = user.get("id")
        if not isinstance(user_id, int) or user_id <= 0:
            raise VkApiError("VK users.get returned an invalid user ID.", method="users.get")
        first_name = str(user.get("first_name") or "").strip()
        last_name = str(user.get("last_name") or "").strip()
        display_name = " ".join(item for item in (first_name, last_name) if item) or str(user_id)
        screen_name = str(user.get("screen_name") or "").strip() or None
        return VkUserIdentity(user_id=user_id, display_name=display_name, screen_name=screen_name)

    def validate_video_access(self, user_id: int) -> None:
        self._call("video.get", params={"owner_id": user_id, "count": 1, "offset": 0})

    def list_managed_communities(self) -> list[VkCommunityIdentity]:
        items = self._list_offset(
            "groups.get",
            params={
                "extended": True,
                "filter": "moder",
                "fields": "description,screen_name,members_count,photo_200",
            },
            page_size=1000,
        )
        communities: list[VkCommunityIdentity] = []
        for item in items:
            community_id = item.get("id")
            if not isinstance(community_id, int) or community_id <= 0:
                continue
            screen_name = str(item.get("screen_name") or "").strip() or None
            communities.append(
                VkCommunityIdentity(
                    community_id=community_id,
                    title=str(item.get("name") or community_id),
                    screen_name=screen_name,
                    url=_community_url(item, community_id),
                )
            )
        return communities

    def get_community(self, community: str | int) -> ChannelRecord:
        value = str(community).strip()
        if not value:
            raise ValueError("VK community ID or screen name cannot be blank.")
        response = self._call(
            "groups.getById",
            params={
                "group_id": value,
                "fields": "description,screen_name,members_count,photo_200,site,status,verified",
            },
        )
        groups = _dict_items(response, key="groups")
        if not groups:
            raise VkApiError(f"VK community not found or inaccessible: {value}", method="groups.getById")
        item = groups[0]
        community_id = item.get("id")
        if not isinstance(community_id, int) or community_id <= 0:
            raise VkApiError("VK groups.getById returned an invalid community ID.", method="groups.getById")
        return ChannelRecord(
            ref=RemoteRef(platform=PlatformName.VK, channel_id=str(community_id), remote_id=str(community_id)),
            title=str(item.get("name") or community_id),
            kind=ChannelKind.COMMUNITY,
            description=str(item.get("description") or ""),
            url=_community_url(item, community_id),
            metadata={
                **item,
                "owner_id": -community_id,
                "managed_by_token": bool(item.get("is_admin")),
            },
        )

    def list_videos(self, community_id: int) -> list[VideoRecord]:
        items = self._list_offset(
            "video.get",
            params={"owner_id": -community_id, "extended": False},
            page_size=200,
        )
        records: list[VideoRecord] = []
        for item in items:
            remote_id = _video_remote_id(item)
            if remote_id is None:
                continue
            video_type = str(item.get("type") or "video")
            privacy_status = "private" if bool(item.get("is_private")) else "public"
            if item.get("processing") or item.get("converting"):
                privacy_status = "processing"
            thumbnail = _best_image(item.get("image")) or _best_image(item.get("first_frame"))
            records.append(
                VideoRecord(
                    ref=RemoteRef(platform=PlatformName.VK, channel_id=str(community_id), remote_id=remote_id),
                    title=str(item.get("title") or remote_id),
                    description=str(item.get("description") or ""),
                    duration_seconds=item.get("duration") if isinstance(item.get("duration"), int) else None,
                    published_at=_unix_datetime(item.get("date")),
                    privacy_status=privacy_status,
                    tags=[],
                    thumbnail_url=thumbnail,
                    revision=_revision(item),
                    metadata={
                        **item,
                        "vk_video_type": video_type,
                        "is_short_video": video_type == "short_video",
                        "permalink": f"https://vk.com/video{remote_id}",
                    },
                )
            )
        return records

    def list_collections(self, community_id: int) -> list[CollectionRecord]:
        items = self._list_offset(
            "video.getAlbums",
            params={"owner_id": -community_id, "extended": True, "need_system": True},
            page_size=100,
        )
        records: list[CollectionRecord] = []
        for item in items:
            album_id = item.get("id")
            if not isinstance(album_id, int):
                continue
            remote_id = str(album_id)
            is_system = bool(item.get("is_system")) or album_id < 0
            records.append(
                CollectionRecord(
                    ref=RemoteRef(platform=PlatformName.VK, channel_id=str(community_id), remote_id=remote_id),
                    title=str(item.get("title") or remote_id),
                    kind=CollectionKind.VIDEO_ALBUM,
                    privacy_status="system" if is_system else "public",
                    revision=_revision(item),
                    metadata={**item, "is_system": is_system},
                )
            )
        return records

    def list_memberships(
        self,
        *,
        community_id: int,
        collections: list[CollectionRecord],
        known_video_ids: set[str],
    ) -> list[CollectionMembership]:
        memberships: list[CollectionMembership] = []
        for collection in collections:
            album_id = int(collection.ref.remote_id)
            items = self._list_offset(
                "video.get",
                params={
                    "owner_id": -community_id,
                    "album_id": album_id,
                    "extended": False,
                    "sort_album": 1,
                },
                page_size=200,
            )
            for position, item in enumerate(items):
                remote_id = _video_remote_id(item)
                if remote_id is None or remote_id not in known_video_ids:
                    continue
                membership_payload = {
                    "album_id": album_id,
                    "video_id": remote_id,
                    "position": position,
                }
                memberships.append(
                    CollectionMembership(
                        collection_ref=collection.ref,
                        video_ref=RemoteRef(
                            platform=PlatformName.VK,
                            channel_id=str(community_id),
                            remote_id=remote_id,
                        ),
                        position=position,
                        membership_id=None,
                        revision=_revision(membership_payload),
                    )
                )
        return memberships
