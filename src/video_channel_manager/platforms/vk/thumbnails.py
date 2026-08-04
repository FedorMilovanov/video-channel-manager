from __future__ import annotations

import json
import mimetypes
import random
import time
from collections.abc import Callable
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
from video_channel_manager.platforms.vk.writer import VkWriteError

_API_BASE_URL = "https://api.vk.com/method"
_RETRYABLE_API_CODES = frozenset({6, 9, 10, 29})
ApiParam: TypeAlias = str | int | bool
ApiParams: TypeAlias = dict[str, ApiParam]


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


class VkThumbnailWriter(HttpClientOwner):
    """Guarded writer for setting an existing image as a VK video thumbnail."""

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
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=max(1, max_attempts))
        self.request_limiter = request_limiter or RequestRateLimiter(0.0)
        self._sleep = sleep
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
            raise VkWriteError("VK thumbnail writes require a user access token.", method="token", code=27)
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
        """Retry only read/reservation-URL methods explicitly marked safe.

        ``video.saveUploadedThumb`` changes the selected thumbnail and can create
        an additional photo object. An ambiguous provider response must not be
        replayed by this low-level client.
        """

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
                sleep=self._sleep,
                jitter=self._jitter,
            )
        except HttpTransportFailure as exc:
            raise VkWriteError(
                str(exc),
                method=method,
                retryable=True,
                kind=exc.kind,
                attempts=exc.attempts,
            ) from exc

        response = result.response
        if response.status_code >= 400:
            kind = result.failure_kind or HttpFailureKind.PERMANENT_HTTP
            raise VkWriteError(
                f"VK API HTTP {response.status_code} while calling {method} "
                f"[kind={kind.value} attempts={result.attempts}].",
                method=method,
                retryable=kind is HttpFailureKind.TRANSIENT_HTTP,
                kind=kind,
                attempts=result.attempts,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise VkWriteError(
                f"VK API returned invalid JSON in {method} [attempts={result.attempts}].",
                method=method,
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            ) from exc
        if not isinstance(payload, dict):
            raise VkWriteError(
                "VK API returned a non-object response.",
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
                retryable=code in _RETRYABLE_API_CODES,
                kind=kind,
                attempts=result.attempts,
            )
        if "response" not in payload:
            raise VkWriteError(
                "VK API response has no 'response' field.",
                method=method,
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            )
        return payload["response"]

    def get_upload_url(self, *, owner_id: int) -> str:
        if owner_id == 0:
            raise ValueError("owner_id cannot be zero")
        response = self._call(
            "video.getThumbUploadUrl",
            params={"owner_id": owner_id},
            retry_transient=True,
        )
        upload_url = response.get("upload_url") if isinstance(response, dict) else None
        if not isinstance(upload_url, str):
            raise VkWriteError(
                "video.getThumbUploadUrl returned an invalid upload URL.",
                method="video.getThumbUploadUrl",
            )
        upload_url = upload_url.strip()
        if not upload_url.lower().startswith(("http://", "https://")):
            raise VkWriteError(
                "video.getThumbUploadUrl returned an invalid upload URL.",
                method="video.getThumbUploadUrl",
            )
        return upload_url

    def upload_image(self, *, upload_url: str, path: Path) -> dict[str, Any]:
        if not upload_url.strip().lower().startswith(("http://", "https://")):
            raise ValueError("upload_url must be an absolute http(s) URL")
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size <= 0:
            raise ValueError(f"Thumbnail file is empty: {path}")
        content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        if not content_type.startswith("image/"):
            raise ValueError(f"Thumbnail path has a non-image media type: {content_type}")

        try:
            with path.open("rb") as stream:
                result = execute_http_request(
                    lambda: self._http_client.post(
                        upload_url,
                        files={"file": (path.name, stream, content_type)},
                        headers={"User-Agent": "video-channel-manager/0.1"},
                        timeout=httpx.Timeout(connect=60.0, read=600.0, write=600.0, pool=60.0),
                    ),
                    provider="VK",
                    operation=HttpOperationClass.AMBIGUOUS_MUTATION,
                    method="POST",
                    resource="video.thumbUpload",
                    retry_policy=self.retry_policy,
                    limiter=self.request_limiter,
                    sleep=self._sleep,
                    jitter=self._jitter,
                )
        except HttpTransportFailure as exc:
            raise VkWriteError(
                str(exc),
                method="video.thumbUpload",
                retryable=True,
                kind=exc.kind,
                attempts=exc.attempts,
            ) from exc

        response = result.response
        if response.status_code >= 400:
            kind = result.failure_kind or HttpFailureKind.PERMANENT_HTTP
            raise VkWriteError(
                f"VK thumbnail upload server returned HTTP {response.status_code} "
                f"[kind={kind.value} attempts={result.attempts}].",
                method="video.thumbUpload",
                retryable=kind is HttpFailureKind.TRANSIENT_HTTP,
                kind=kind,
                attempts=result.attempts,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise VkWriteError(
                "VK thumbnail upload server returned invalid JSON.",
                method="video.thumbUpload",
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            ) from exc
        if not isinstance(payload, dict):
            raise VkWriteError(
                "VK thumbnail upload server returned a non-object response.",
                method="video.thumbUpload",
                kind=HttpFailureKind.INVALID_PAYLOAD,
                attempts=result.attempts,
            )

        # VK has two upload-server response shapes in production. Older
        # responses wrap the opaque value in `thumb_json`; current servers
        # return the opaque JSON object itself (server/hash/secret/meta/etc.).
        # video.saveUploadedThumb expects the complete raw upload response as
        # its `thumb_json` parameter, so preserve the exact response text.
        thumb_json = payload.get("thumb_json")
        if not isinstance(thumb_json, str) or not thumb_json:
            raw_thumb_json = response.text.strip()
            if not raw_thumb_json:
                raise VkWriteError(
                    "VK thumbnail upload server returned an empty response.",
                    method="video.thumbUpload",
                    kind=HttpFailureKind.INVALID_PAYLOAD,
                    attempts=result.attempts,
                )
            payload = dict(payload)
            payload["thumb_json"] = raw_thumb_json
        return payload

    def save_uploaded_thumbnail(
        self,
        *,
        owner_id: int,
        video_id: int,
        upload_payload: dict[str, Any],
    ) -> dict[str, Any]:
        if owner_id == 0 or video_id <= 0:
            raise ValueError("owner_id cannot be zero and video_id must be positive")
        thumb_json = upload_payload.get("thumb_json")
        if not isinstance(thumb_json, str) or not thumb_json:
            raise ValueError("upload_payload must contain non-empty thumb_json")

        params: ApiParams = {
            "owner_id": owner_id,
            "video_id": video_id,
            "thumb_json": thumb_json,
            "set_thumb": True,
        }
        for key in ("thumb_size", "random_tag"):
            value = upload_payload.get(key)
            if isinstance(value, str) and value:
                params[key] = value

        response = self._call("video.saveUploadedThumb", params=params)
        if not isinstance(response, dict):
            raise VkWriteError(
                "video.saveUploadedThumb returned a non-object response.",
                method="video.saveUploadedThumb",
            )
        photo_id = response.get("photo_id")
        photo_owner_id = response.get("photo_owner_id")
        photo_hash = response.get("photo_hash")
        if not isinstance(photo_id, int) or photo_id <= 0 or not isinstance(photo_hash, str) or not photo_hash:
            raise VkWriteError(
                "video.saveUploadedThumb returned an incomplete result.",
                method="video.saveUploadedThumb",
            )
        if isinstance(photo_owner_id, int) and photo_owner_id != owner_id:
            raise VkWriteError(
                f"video.saveUploadedThumb returned photo owner {photo_owner_id}, expected {owner_id}.",
                method="video.saveUploadedThumb",
            )
        return response

    def set_thumbnail(self, *, owner_id: int, video_id: int, path: Path) -> dict[str, Any]:
        upload_url = self.get_upload_url(owner_id=owner_id)
        upload_payload = self.upload_image(upload_url=upload_url, path=path)
        return self.save_uploaded_thumbnail(
            owner_id=owner_id,
            video_id=video_id,
            upload_payload=upload_payload,
        )
