from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

import httpx

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
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.upload_lifecycle import (
    VkUploadReadiness,
    VkUploadReadinessAssessment,
    assess_vk_upload_readiness,
)

_API_BASE_URL = "https://api.vk.com/method"
_RETRYABLE_API_CODES = frozenset({6, 9, 10, 29})
_RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
ApiParam: TypeAlias = str | int | bool
ApiParams: TypeAlias = dict[str, ApiParam]
UploadObservationCallback: TypeAlias = Callable[[dict[str, Any] | None, VkUploadReadinessAssessment | None], None]


class VkWriteError(RuntimeError):
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


@dataclass(frozen=True, slots=True)
class VkUploadTicket:
    owner_id: int
    video_id: int
    upload_url: str
    reservation_response: dict[str, Any] | None = field(default=None, repr=False, compare=False)

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
            timeout=60.0,
            follow_redirects=True,
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.max_attempts = max(1, max_attempts)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=self.max_attempts,
            base_delay_seconds=0.5,
            max_delay_seconds=8.0,
        )
        self.request_limiter = request_limiter or RequestRateLimiter()
        self._request_sleep = sleep
        self._jitter = jitter

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
        """Call VK under explicit read or ambiguous-mutation authority."""

        access_token = self._token_value()
        request_data: dict[str, str] = {
            "access_token": access_token,
            "v": self.api_version,
        }
        for key, value in (params or {}).items():
            request_data[key] = "1" if value is True else "0" if value is False else str(value)

        operation = HttpOperationClass.SAFE_READ if retry_transient else HttpOperationClass.AMBIGUOUS_MUTATION
        try:
            result = execute_http_request(
                lambda: self._http_client.post(
                    f"{self.api_base_url}/{method}",
                    data=request_data,
                    headers={"User-Agent": "video-channel-manager/0.1"},
                ),
                provider="VK",
                operation=operation,
                method="POST",
                resource=method,
                retry_policy=self.retry_policy,
                limiter=self.request_limiter,
                response_classifier=_provider_response_kind,
                sleep=self._request_sleep,
                jitter=self._jitter,
            )
        except HttpTransportFailure as exc:
            raise VkWriteError(
                str(exc),
                method=method,
                retryable=operation is HttpOperationClass.SAFE_READ,
                kind=exc.kind,
                attempts=exc.attempts,
            ) from exc

        response = result.response
        if response.status_code >= 400:
            kind = result.failure_kind or HttpFailureKind.PERMANENT_HTTP
            raise VkWriteError(
                f"VK API HTTP {response.status_code} while calling {method} "
                f"[kind={kind.value} attempts={result.attempts}]",
                method=method,
                retryable=(
                    operation is HttpOperationClass.SAFE_READ
                    and kind in {HttpFailureKind.RATE_LIMIT, HttpFailureKind.TRANSIENT_HTTP}
                ),
                kind=kind,
                attempts=result.attempts,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise VkWriteError(
                f"VK API returned invalid JSON in {method} "
                f"[kind={HttpFailureKind.INVALID_JSON.value} attempts={result.attempts}]",
                method=method,
                kind=HttpFailureKind.INVALID_JSON,
                attempts=result.attempts,
            ) from exc
        if not isinstance(payload, dict):
            raise VkWriteError(
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
                secrets=(access_token,),
            )
            kind = result.failure_kind or HttpFailureKind.PROVIDER_ERROR
            raise VkWriteError(
                f"VK API {code or 'error'} in {method}: {message} [kind={kind.value} attempts={result.attempts}]",
                method=method,
                code=code,
                retryable=operation is HttpOperationClass.SAFE_READ and code in _RETRYABLE_API_CODES,
                kind=kind,
                attempts=result.attempts,
            )
        if "response" not in payload:
            raise VkWriteError(
                f"VK API response has no 'response' field in {method} "
                f"[kind={HttpFailureKind.INVALID_PAYLOAD.value} attempts={result.attempts}]",
                method=method,
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            )
        return payload["response"]

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
        return VkUploadTicket(
            owner_id=owner_id,
            video_id=video_id,
            upload_url=upload_url,
            reservation_response=dict(response),
        )

    def upload_file(self, ticket: VkUploadTicket, path: Path) -> dict[str, Any]:
        if ticket.video_id <= 0 or ticket.owner_id == 0 or not ticket.upload_url:
            raise ValueError("VK upload ticket is invalid")
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size <= 0:
            raise ValueError(f"VK upload file is empty: {path}")

        def send_upload() -> httpx.Response:
            with path.open("rb") as stream:
                return self._http_client.post(
                    ticket.upload_url,
                    files={"video_file": (path.name, stream, "video/mp4")},
                    headers={"User-Agent": "video-channel-manager/0.1"},
                    timeout=httpx.Timeout(connect=60.0, read=7200.0, write=7200.0, pool=60.0),
                )

        try:
            result = execute_http_request(
                send_upload,
                provider="VK upload",
                operation=HttpOperationClass.AMBIGUOUS_MUTATION,
                method="POST",
                resource="video.upload",
                retry_policy=self.retry_policy,
                sleep=self._request_sleep,
                jitter=self._jitter,
            )
        except HttpTransportFailure as exc:
            raise VkWriteError(
                str(exc),
                method="video.upload",
                retryable=False,
                kind=exc.kind,
                attempts=exc.attempts,
            ) from exc

        response = result.response
        if response.status_code >= 400:
            kind = result.failure_kind or HttpFailureKind.PERMANENT_HTTP
            raise VkWriteError(
                f"VK upload server returned HTTP {response.status_code} [kind={kind.value} attempts={result.attempts}]",
                method="video.upload",
                retryable=False,
                kind=kind,
                attempts=result.attempts,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise VkWriteError(
                f"VK upload server returned invalid JSON "
                f"[kind={HttpFailureKind.INVALID_JSON.value} attempts={result.attempts}]",
                method="video.upload",
                kind=HttpFailureKind.INVALID_JSON,
                attempts=result.attempts,
            ) from exc
        if not isinstance(payload, dict):
            raise VkWriteError(
                f"VK upload server returned a non-object response "
                f"[kind={HttpFailureKind.INVALID_PAYLOAD.value} attempts={result.attempts}]",
                method="video.upload",
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            )
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
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            )
        return payload

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
        readiness: VkUploadReadiness | None = None,
        timeout_seconds: int = 3600,
        poll_seconds: float = 10.0,
        on_observation: UploadObservationCallback | None = None,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("timeout_seconds and poll_seconds must be positive")
        deadline = time.monotonic() + timeout_seconds
        last_item: dict[str, Any] | None = None
        last_assessment: VkUploadReadinessAssessment | None = None
        while time.monotonic() < deadline:
            item = self.read_video(owner_id=ticket.owner_id, video_id=ticket.video_id)
            assessment: VkUploadReadinessAssessment | None = None
            if item is not None:
                last_item = item
                if readiness is None:
                    processing = bool(item.get("processing")) or bool(item.get("converting"))
                    if on_observation is not None:
                        on_observation(item, None)
                    if not processing:
                        return item
                else:
                    assessment = assess_vk_upload_readiness(
                        item,
                        expected_owner_id=ticket.owner_id,
                        expected_video_id=ticket.video_id,
                        readiness=readiness,
                    )
                    last_assessment = assessment
                    if on_observation is not None:
                        on_observation(item, assessment)
                    if assessment.ready:
                        return item
            elif on_observation is not None:
                on_observation(None, None)
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(poll_seconds, remaining))
        state = json.dumps(last_item, ensure_ascii=False)[:500] if last_item else "not visible"
        reasons = f"; readiness reasons: {last_assessment.reasons}" if last_assessment is not None else ""
        raise VkWriteError(
            f"Uploaded video {ticket.remote_id} did not become ready within {timeout_seconds}s; "
            f"last state: {state}{reasons}",
            method="video.get",
        )
