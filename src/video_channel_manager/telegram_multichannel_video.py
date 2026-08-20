from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_models import DEFAULT_API_BASE
from video_channel_manager.telegram_transport import _api_call, _result_dict
from video_channel_manager.telegram_multichannel_transport import (
    GenericSendReceipt,
    GenericTargetProof,
    MUTATION_TRANSPORT_RETRIES,
    TelegramApiError,
    _message_id,
    _receipt,
    _require_provider_write_authorized,
    _verified_target,
    _verify_returned_chat,
)


class GenericVideoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-video-payload"]
    schema_version: Literal[1]
    project_key: str
    channel_username: str
    publication_id: str
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    caption: str = Field(min_length=1, max_length=1024)
    media_path: str = Field(min_length=1, max_length=500)
    media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_byte_size: int = Field(gt=0, le=50_000_000)
    media_filename: str = Field(min_length=5, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    media_mime_type: Literal["video/mp4"] = "video/mp4"
    supports_streaming: Literal[True] = True

    @model_validator(mode="after")
    def validate_media_path(self) -> "GenericVideoPayload":
        path = Path(self.media_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("video media_path must be repository-relative without parent traversal")
        if path.suffix.casefold() != ".mp4" or not self.media_filename.casefold().endswith(".mp4"):
            raise ValueError("video payload must use an MP4 path and filename")
        return self


def _sha256_payload(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_video_payload(
    profile: TelegramChannelProfile,
    *,
    publication_id: str,
    caption: str,
    media_path: str,
    media_sha256: str,
    media_byte_size: int,
    media_filename: str,
) -> GenericVideoPayload:
    if not publication_id.startswith(profile.publication_id_prefix):
        raise ValueError(f"publication_id must start with {profile.publication_id_prefix!r}")
    if len(publication_id) > 96:
        raise ValueError("publication_id is too long")
    digest_input: dict[str, Any] = {
        "kind": "video",
        "project_key": profile.project_key,
        "channel_username": profile.channel_username,
        "publication_id": publication_id,
        "profile_sha256": profile.digest,
        "caption": caption,
        "media_path": media_path,
        "media_sha256": media_sha256,
        "media_byte_size": media_byte_size,
        "media_filename": media_filename,
        "media_mime_type": "video/mp4",
        "supports_streaming": True,
    }
    return GenericVideoPayload(
        schema_name="video-channel-manager.telegram-generic-video-payload",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        publication_id=publication_id,
        profile_sha256=profile.digest,
        provider_payload_sha256=_sha256_payload(digest_input),
        caption=caption,
        media_path=media_path,
        media_sha256=media_sha256,
        media_byte_size=media_byte_size,
        media_filename=media_filename,
    )


class _VideoMultipartClient:
    def __init__(self, client: httpx.Client, payload: GenericVideoPayload, media: bytes) -> None:
        self._client = client
        self._payload = payload
        self._media = media

    def post(self, url: str, *, json: dict[str, Any]) -> httpx.Response:
        if (
            int(json.get("chat_id", 0)) == 0
            or str(json.get("caption") or "") != self._payload.caption
            or json.get("supports_streaming") is not True
        ):
            raise ValueError("video adapter received a provider payload that differs from the exact video payload")
        return self._client.post(
            url,
            data={
                "chat_id": str(json["chat_id"]),
                "caption": self._payload.caption,
                "supports_streaming": "true",
            },
            files={"video": (self._payload.media_filename, self._media, self._payload.media_mime_type)},
        )


def _read_exact_video_media(payload: GenericVideoPayload) -> bytes:
    try:
        media = Path(payload.media_path).read_bytes()
    except OSError as exc:
        raise ValueError(f"unable to read exact Telegram video media: {payload.media_path}") from exc
    if len(media) != payload.media_byte_size:
        raise ValueError("Telegram video media byte-size differs from reviewed payload")
    actual_sha256 = "sha256:" + hashlib.sha256(media).hexdigest()
    if actual_sha256 != payload.media_sha256:
        raise ValueError("Telegram video media SHA-256 differs from reviewed payload")
    return media


def send_video_once(
    profile: TelegramChannelProfile,
    target: GenericTargetProof,
    payload: GenericVideoPayload,
    *,
    token: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> GenericSendReceipt:
    _require_provider_write_authorized(profile)
    target_check_now = now or datetime.now(tz=UTC)
    _verified_target(profile, target, target_check_now)
    if payload.project_key != profile.project_key or payload.profile_sha256 != profile.digest:
        raise ValueError("video payload is not bound to the selected channel profile")
    if payload.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("video payload target differs from selected channel profile")
    media = _read_exact_video_media(payload)

    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=90, write=90, pool=15),
        transport=httpx.HTTPTransport(retries=MUTATION_TRANSPORT_RETRIES),
        trust_env=False,
    )
    adapter = _VideoMultipartClient(http_client, payload, media)
    try:
        message = _result_dict(
            _api_call(
                cast(httpx.Client, adapter),
                api_base=api_base,
                token=token,
                method="sendVideo",
                payload={
                    "chat_id": target.chat_id,
                    "caption": payload.caption,
                    "supports_streaming": payload.supports_streaming,
                },
                mutation=True,
            ),
            method="sendVideo",
            provider_effect="may_exist",
        )
        _verify_returned_chat(message, target)
        if str(message.get("caption") or "") != payload.caption:
            raise TelegramApiError(
                "Telegram returned a caption that differs from the exact video payload",
                provider_effect="may_exist",
            )
        video = message.get("video")
        if not isinstance(video, dict) or not video:
            raise TelegramApiError("Telegram returned a video message without video data", provider_effect="may_exist")
        returned_mime = str(video.get("mime_type") or "")
        if returned_mime and returned_mime.casefold() != payload.media_mime_type:
            raise TelegramApiError(
                "Telegram returned a video mime type that differs from the exact payload",
                provider_effect="may_exist",
            )
        message_id = _message_id(message)
        return _receipt(
            profile,
            publication_id=payload.publication_id,
            payload_sha256=payload.provider_payload_sha256,
            target=target,
            message_id=message_id,
            now=now or datetime.now(tz=UTC),
        )
    finally:
        if own_client:
            http_client.close()


__all__ = ["GenericVideoPayload", "render_video_payload", "send_video_once"]
