from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

import httpx

from video_channel_manager.platforms.http import HttpClientOwner
from video_channel_manager.platforms.vk.store import VkTokenStore

_API_BASE_URL = "https://api.vk.com/method"
_RETRYABLE_API_CODES = frozenset({6, 9, 10, 29})
_RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
ApiParam: TypeAlias = str | int | bool
ApiParams: TypeAlias = dict[str, ApiParam]


class VkWriteError(RuntimeError):
    def __init__(self, message: str, *, method: str, code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.method = method
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class VkUploadTicket:
    owner_id: int
    video_id: int
    upload_url: str

    @property
    def remote_id(self) -> str:
        return f"{self.owner_id}_{self.video_id}"


class VkVideoWriter(HttpClientOwner):
    """Narrow guarded writer for VK video uploads and video-album operations."""

    def __init__(
        self,
        *,
        token_store: VkTokenStore,
        account_alias: str,
        api_version: str = "5.199",
        http_client: httpx.Client | None = None,
        api_base_url: str = _API_BASE_URL,
        max_attempts: int = 4,
    ) -> None:
        self.token_store = token_store
        self.account_alias = token_store.validate_alias(account_alias)
        self.api_version = api_version
        self._initialize_http_client(
            http_client,
            timeout=60.0,
            follow_redirects=True,
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.max_attempts = max(1, max_attempts)

    def _token_value(self) -> str:
        token = self.token_store.load_token(self.account_alias)
        if token.is_expired():
            raise VkWriteError(
                "VK access token is expired. Import a fresh user token with video permission.",
                method="token",
                code=5,
            )
        if token.token_type != "user":
            raise VkWriteError("VK write operations require a user access token.", method="token", code=27)
        if "video" not in token.scopes:
            raise VkWriteError("Stored VK token does not declare the video permission.", method="token", code=7)
        return token.access_token

    def _call(
        self,
        method: str,
        *,
        params: ApiParams | None = None,
        retry_transient: bool = False,
    ) -> object:
        """Call VK, retrying only when the caller proves the request is read-only.

        A network/5xx error after ``video.save`` or ``video.addAlbum`` is
        ambiguous: VK may have completed the mutation before the response was
        lost. Blindly retrying can reserve or create a duplicate. Mutation
        workflows must instead journal intent and reconcile live state.
        """

        request_data: dict[str, str] = {
            "access_token": self._token_value(),
            "v": self.api_version,
        }
        for key, value in (params or {}).items():
            request_data[key] = "1" if value is True else "0" if value is False else str(value)

        attempts = self.max_attempts if retry_transient else 1
        delay_seconds = 0.5
        last_error: VkWriteError | None = None
        for attempt in range(attempts):
            try:
                return self._call_once(method, request_data)
            except VkWriteError as exc:
                last_error = exc
                if not exc.retryable or attempt + 1 >= attempts:
                    raise
                time.sleep(delay_seconds)
                delay_seconds *= 2
        assert last_error is not None
        raise last_error

    def _call_once(self, method: str, request_data: dict[str, str]) -> object:
        try:
            response = self._http_client.post(
                f"{self.api_base_url}/{method}",
                data=request_data,
                headers={"User-Agent": "video-channel-manager/0.1"},
            )
            if response.status_code >= 400:
                raise VkWriteError(
                    f"VK API HTTP {response.status_code} while calling {method}.",
                    method=method,
                    retryable=response.status_code in _RETRYABLE_HTTP_STATUS_CODES,
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise VkWriteError("VK API returned a non-object response.", method=method)
            raw_error = payload.get("error")
            if isinstance(raw_error, dict):
                raw_code = raw_error.get("error_code")
                code = int(raw_code) if isinstance(raw_code, int | str) and str(raw_code).isdigit() else None
                message = str(raw_error.get("error_msg") or "Unknown VK API error")
                raise VkWriteError(
                    f"VK API {code or 'error'} in {method}: {message}",
                    method=method,
                    code=code,
                    retryable=code in _RETRYABLE_API_CODES,
                )
            if "response" not in payload:
                raise VkWriteError("VK API response has no 'response' field.", method=method)
            return payload["response"]
        except httpx.HTTPError as exc:
            raise VkWriteError(f"VK API request failed in {method}: {exc}", method=method, retryable=True) from exc
        except ValueError as exc:
            raise VkWriteError(f"VK API returned invalid JSON in {method}.", method=method) from exc

    def create_album(self, *, community_id: int, title: str) -> int:
        title = title.strip()
        if community_id <= 0 or not title:
            raise ValueError("community_id must be positive and album title cannot be blank")
        response = self._call("video.addAlbum", params={"group_id": community_id, "title": title})
        album_id = response.get("album_id") if isinstance(response, dict) else response
        if not isinstance(album_id, int) or album_id <= 0:
            raise VkWriteError("video.addAlbum returned an invalid album ID.", method="video.addAlbum")
        return album_id

    def album_ids_for_video(self, *, community_id: int, owner_id: int, video_id: int) -> set[int]:
        if community_id <= 0 or owner_id == 0 or video_id <= 0:
            raise ValueError("community_id/video_id must be positive and owner_id cannot be zero")
        response = self._call(
            "video.getAlbumsByVideo",
            params={
                "target_id": -community_id,
                "owner_id": owner_id,
                "video_id": video_id,
                "extended": False,
            },
            retry_transient=True,
        )
        if not isinstance(response, list):
            raise VkWriteError("video.getAlbumsByVideo returned a non-list response.", method="video.getAlbumsByVideo")
        return {item for item in response if isinstance(item, int) and item > 0}

    def add_to_album(
        self,
        *,
        community_id: int,
        album_id: int,
        owner_id: int,
        video_id: int,
        verification_attempts: int = 5,
        verification_delay_seconds: float = 0.5,
    ) -> bool:
        if community_id <= 0 or album_id <= 0 or owner_id == 0 or video_id <= 0:
            raise ValueError("community_id/album_id/video_id must be positive and owner_id cannot be zero")
        if album_id in self.album_ids_for_video(
            community_id=community_id,
            owner_id=owner_id,
            video_id=video_id,
        ):
            return False
        response = self._call(
            "video.addToAlbum",
            params={
                "target_id": -community_id,
                "album_id": album_id,
                "owner_id": owner_id,
                "video_id": video_id,
            },
        )

        attempts = max(1, verification_attempts)
        delay_seconds = max(0.0, verification_delay_seconds)
        for attempt in range(attempts):
            if album_id in self.album_ids_for_video(
                community_id=community_id,
                owner_id=owner_id,
                video_id=video_id,
            ):
                return True
            if attempt + 1 < attempts and delay_seconds > 0:
                time.sleep(delay_seconds)
                delay_seconds *= 2

        raise VkWriteError(
            "video.addToAlbum returned "
            f"{response!r}, but the album membership was not visible after {attempts} verification attempts.",
            method="video.addToAlbum",
        )

    def begin_upload(self, *, community_id: int, title: str, description: str) -> VkUploadTicket:
        title = title.strip()
        if community_id <= 0:
            raise ValueError("community_id must be positive")
        if not title:
            raise ValueError("VK video title cannot be blank")
        response = self._call(
            "video.save",
            params={
                "group_id": community_id,
                "name": title,
                "description": description,
                "wallpost": False,
                "is_private": False,
                "no_comments": False,
            },
        )
        if not isinstance(response, dict):
            raise VkWriteError("video.save returned a non-object response.", method="video.save")
        owner_id = response.get("owner_id")
        video_id = response.get("video_id")
        upload_url = response.get("upload_url")
        if not isinstance(owner_id, int) or not isinstance(video_id, int) or not isinstance(upload_url, str):
            raise VkWriteError("video.save returned an incomplete upload ticket.", method="video.save")
        upload_url = upload_url.strip()
        if owner_id != -community_id:
            raise VkWriteError(
                f"video.save returned owner {owner_id}, expected {-community_id}.",
                method="video.save",
            )
        if video_id <= 0 or not upload_url or not upload_url.lower().startswith(("https://", "http://")):
            raise VkWriteError("video.save returned an invalid upload ticket.", method="video.save")
        return VkUploadTicket(owner_id=owner_id, video_id=video_id, upload_url=upload_url)

    def upload_file(self, ticket: VkUploadTicket, path: Path) -> dict[str, Any]:
        if ticket.video_id <= 0 or ticket.owner_id == 0 or not ticket.upload_url:
            raise ValueError("VK upload ticket is invalid")
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size <= 0:
            raise ValueError(f"VK upload file is empty: {path}")
        try:
            with path.open("rb") as stream:
                response = self._http_client.post(
                    ticket.upload_url,
                    files={"video_file": (path.name, stream, "video/mp4")},
                    headers={"User-Agent": "video-channel-manager/0.1"},
                    timeout=httpx.Timeout(connect=60.0, read=7200.0, write=7200.0, pool=60.0),
                )
            if response.status_code >= 400:
                raise VkWriteError(
                    f"VK upload server returned HTTP {response.status_code}.",
                    method="video.upload",
                    retryable=response.status_code in _RETRYABLE_HTTP_STATUS_CODES,
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise VkWriteError("VK upload server returned a non-object response.", method="video.upload")
            upload_video_id_raw = payload.get("video_id")
            upload_video_id = (
                int(upload_video_id_raw)
                if isinstance(upload_video_id_raw, int | str) and str(upload_video_id_raw).isdigit()
                else None
            )
            if upload_video_id is not None and upload_video_id != ticket.video_id:
                raise VkWriteError(
                    f"VK upload response video ID {upload_video_id} differs from ticket {ticket.video_id}.",
                    method="video.upload",
                )
            return payload
        except httpx.HTTPError as exc:
            raise VkWriteError(f"VK video upload failed: {exc}", method="video.upload", retryable=True) from exc
        except json.JSONDecodeError as exc:
            raise VkWriteError("VK upload server returned invalid JSON.", method="video.upload") from exc

    def read_video(self, *, owner_id: int, video_id: int) -> dict[str, Any] | None:
        if owner_id == 0 or video_id <= 0:
            raise ValueError("owner_id cannot be zero and video_id must be positive")
        response = self._call(
            "video.get",
            params={"videos": f"{owner_id}_{video_id}", "count": 1, "extended": False},
            retry_transient=True,
        )
        if not isinstance(response, dict):
            raise VkWriteError("video.get returned a non-object response.", method="video.get")
        items = response.get("items")
        if not isinstance(items, list) or not items:
            return None
        item = items[0]
        if not isinstance(item, dict):
            return None
        observed_owner = item.get("owner_id")
        observed_id = item.get("id")
        if observed_owner != owner_id or observed_id != video_id:
            raise VkWriteError(
                f"video.get returned unexpected identity {observed_owner}_{observed_id} for {owner_id}_{video_id}.",
                method="video.get",
            )
        return item

    def wait_until_available(
        self,
        ticket: VkUploadTicket,
        *,
        timeout_seconds: int = 3600,
        poll_seconds: float = 10.0,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("timeout_seconds and poll_seconds must be positive")
        deadline = time.monotonic() + timeout_seconds
        last_item: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            item = self.read_video(owner_id=ticket.owner_id, video_id=ticket.video_id)
            if item is not None:
                last_item = item
                processing = bool(item.get("processing")) or bool(item.get("converting"))
                if not processing:
                    return item
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(poll_seconds, remaining))
        state = json.dumps(last_item, ensure_ascii=False)[:500] if last_item else "not visible"
        raise VkWriteError(
            f"Uploaded video {ticket.remote_id} did not finish processing within {timeout_seconds}s; last state: {state}",
            method="video.get",
        )
