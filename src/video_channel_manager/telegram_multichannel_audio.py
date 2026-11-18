from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_html_entities import (
    GenericMessageEntity,
    message_entities_match,
    parse_telegram_html,
)
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


def _sha256_payload(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class GenericAudioPayload(BaseModel):
    """One reviewed, byte-bound Telegram sendAudio item; no independent dispatch path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-audio-payload"]
    schema_version: Literal[1]
    project_key: str
    channel_username: str
    publication_id: str
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    caption_html: str = Field(min_length=1, max_length=8192)
    expected_plain_caption: str = Field(min_length=1, max_length=1024)
    expected_caption_entities: tuple[GenericMessageEntity, ...]
    media_path: str = Field(min_length=1, max_length=500)
    media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_byte_size: int = Field(gt=0, le=50_000_000)
    media_filename: str = Field(min_length=5, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    media_mime_type: Literal["audio/mpeg"] = "audio/mpeg"
    title: str = Field(min_length=1, max_length=200)
    performer: str = Field(min_length=1, max_length=200)
    duration: int = Field(gt=0, le=86_400)
    thumbnail_path: str | None = Field(default=None, max_length=500)
    thumbnail_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    thumbnail_byte_size: int | None = Field(default=None, gt=0, le=200_000)
    thumbnail_filename: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{5,128}$")

    @model_validator(mode="after")
    def verify_structure(self) -> "GenericAudioPayload":
        path = PurePosixPath(self.media_path)
        win_path = PureWindowsPath(self.media_path)
        if (
            path.is_absolute()
            or win_path.is_absolute()
            or win_path.drive
            or ".." in path.parts
            or ".." in win_path.parts
        ):
            raise ValueError("audio media_path must be repository-relative without parent traversal")
        if path.suffix.casefold() != ".mp3" or not self.media_filename.casefold().endswith(".mp3"):
            raise ValueError("audio payload must use an MP3 path and filename")
        thumbs = [self.thumbnail_path, self.thumbnail_sha256, self.thumbnail_byte_size, self.thumbnail_filename]
        if any(v is not None for v in thumbs) and not all(v is not None for v in thumbs):
            raise ValueError("audio thumbnail path, hash, bytes and filename must be supplied together")
        if self.thumbnail_path is not None:
            p = PurePosixPath(self.thumbnail_path)
            win_path = PureWindowsPath(self.thumbnail_path)
            if (
                p.is_absolute()
                or win_path.is_absolute()
                or win_path.drive
                or ".." in p.parts
                or ".." in win_path.parts
                or p.suffix.casefold() not in {".jpg", ".jpeg"}
            ):
                raise ValueError("audio thumbnail must be repository-relative JPEG without parent traversal")
            if not self.thumbnail_filename or not self.thumbnail_filename.casefold().endswith((".jpg", ".jpeg")):
                raise ValueError("audio thumbnail filename must be JPEG")
        plain, entities = parse_telegram_html(self.caption_html)
        if plain != self.expected_plain_caption or entities != self.expected_caption_entities:
            raise ValueError("audio caption HTML/plain text/entities contract differs")
        if _sha256_payload(self._digest_input()) != self.provider_payload_sha256:
            raise ValueError("audio provider payload digest differs")
        return self

    def _digest_input(self) -> dict[str, Any]:
        return {
            "kind": "audio",
            "project_key": self.project_key,
            "channel_username": self.channel_username,
            "publication_id": self.publication_id,
            "profile_sha256": self.profile_sha256,
            "caption_html": self.caption_html,
            "expected_plain_caption": self.expected_plain_caption,
            "expected_caption_entities": [e.model_dump(mode="json") for e in self.expected_caption_entities],
            "media_path": self.media_path,
            "media_sha256": self.media_sha256,
            "media_byte_size": self.media_byte_size,
            "media_filename": self.media_filename,
            "media_mime_type": self.media_mime_type,
            "title": self.title,
            "performer": self.performer,
            "duration": self.duration,
            "thumbnail_path": self.thumbnail_path,
            "thumbnail_sha256": self.thumbnail_sha256,
            "thumbnail_byte_size": self.thumbnail_byte_size,
            "thumbnail_filename": self.thumbnail_filename,
            "parse_mode": "HTML",
        }


def render_audio_payload(
    profile: TelegramChannelProfile,
    *,
    publication_id: str,
    caption_html: str,
    media_path: str,
    media_sha256: str,
    media_byte_size: int,
    media_filename: str,
    title: str,
    performer: str,
    duration: int,
    thumbnail_path: str | None = None,
    thumbnail_sha256: str | None = None,
    thumbnail_byte_size: int | None = None,
    thumbnail_filename: str | None = None,
) -> GenericAudioPayload:
    if not publication_id.startswith(profile.publication_id_prefix) or len(publication_id) > 96:
        raise ValueError("audio publication_id differs from selected channel prefix")
    plain, entities = parse_telegram_html(caption_html)
    if not plain or len(plain) > 1024:
        raise ValueError("audio caption must contain 1–1024 parsed characters")
    fields: dict[str, Any] = {
        "schema_name": "video-channel-manager.telegram-generic-audio-payload",
        "schema_version": 1,
        "project_key": profile.project_key,
        "channel_username": profile.channel_username,
        "publication_id": publication_id,
        "profile_sha256": profile.digest,
        "caption_html": caption_html,
        "expected_plain_caption": plain,
        "expected_caption_entities": entities,
        "media_path": media_path,
        "media_sha256": media_sha256,
        "media_byte_size": media_byte_size,
        "media_filename": media_filename,
        "title": title,
        "performer": performer,
        "duration": duration,
        "thumbnail_path": thumbnail_path,
        "thumbnail_sha256": thumbnail_sha256,
        "thumbnail_byte_size": thumbnail_byte_size,
        "thumbnail_filename": thumbnail_filename,
    }
    draft = GenericAudioPayload.model_construct(provider_payload_sha256="sha256:" + "0" * 64, **fields)
    return GenericAudioPayload(provider_payload_sha256=_sha256_payload(draft._digest_input()), **fields)


def _read_exact_file(path: str, length: int, digest: str, label: str) -> bytes:
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read exact {label}: {path}") from exc
    if len(payload) != length:
        raise ValueError(f"{label} byte-size differs from reviewed payload")
    if "sha256:" + hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError(f"{label} SHA-256 differs from reviewed payload")
    return payload


class _AudioMultipartClient:
    def __init__(
        self, client: httpx.Client, payload: GenericAudioPayload, audio: bytes, thumbnail: bytes | None
    ) -> None:
        self._client = client
        self._payload = payload
        self._audio = audio
        self._thumbnail = thumbnail

    def post(self, url: str, *, json: dict[str, Any]) -> httpx.Response:
        expected = {
            "caption": self._payload.caption_html,
            "parse_mode": "HTML",
            "title": self._payload.title,
            "performer": self._payload.performer,
            "duration": self._payload.duration,
        }
        if int(json.get("chat_id", 0)) == 0 or any(json.get(k) != v for k, v in expected.items()):
            raise ValueError("audio transport received altered provider payload")
        data = {
            "chat_id": str(json["chat_id"]),
            "caption": self._payload.caption_html,
            "parse_mode": "HTML",
            "title": self._payload.title,
            "performer": self._payload.performer,
            "duration": str(self._payload.duration),
        }
        files = {"audio": (self._payload.media_filename, self._audio, "audio/mpeg")}
        if self._thumbnail is not None:
            assert self._payload.thumbnail_filename is not None
            files["thumbnail"] = (self._payload.thumbnail_filename, self._thumbnail, "image/jpeg")
        return self._client.post(url, data=data, files=files)


def send_audio_once(
    profile: TelegramChannelProfile,
    target: GenericTargetProof,
    payload: GenericAudioPayload,
    *,
    token: str,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> GenericSendReceipt:
    _require_provider_write_authorized(profile)
    instant = now or datetime.now(tz=UTC)
    _verified_target(profile, target, instant)
    if payload.project_key != profile.project_key or payload.profile_sha256 != profile.digest:
        raise ValueError("audio payload is not bound to the selected channel profile")
    if payload.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("audio target differs from selected channel profile")
    # All validation happens before constructing the provider adapter or dispatching.
    payload = GenericAudioPayload.model_validate(payload.model_dump(mode="json"))
    audio = _read_exact_file(payload.media_path, payload.media_byte_size, payload.media_sha256, "audio")
    thumbnail: bytes | None = None
    if payload.thumbnail_path is not None:
        assert payload.thumbnail_byte_size is not None
        assert payload.thumbnail_sha256 is not None
        thumbnail = _read_exact_file(
            payload.thumbnail_path, payload.thumbnail_byte_size, payload.thumbnail_sha256, "thumbnail"
        )
    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=100, write=100, pool=15),
        transport=httpx.HTTPTransport(retries=MUTATION_TRANSPORT_RETRIES),
        trust_env=False,
    )
    adapter = _AudioMultipartClient(http_client, payload, audio, thumbnail)
    try:
        msg = _result_dict(
            _api_call(
                cast(httpx.Client, adapter),
                api_base=api_base,
                token=token,
                method="sendAudio",
                payload={
                    "chat_id": target.chat_id,
                    "caption": payload.caption_html,
                    "parse_mode": "HTML",
                    "title": payload.title,
                    "performer": payload.performer,
                    "duration": payload.duration,
                },
                mutation=True,
            ),
            method="sendAudio",
            provider_effect="may_exist",
        )
        _verify_returned_chat(msg, target)
        actual_caption = msg.get("caption")
        allowed_terminal_lf = (
            payload.expected_plain_caption.endswith("\n")
            and not payload.expected_plain_caption.endswith("\n\n")
            and actual_caption == payload.expected_plain_caption[:-1]
        )
        if actual_caption != payload.expected_plain_caption and not allowed_terminal_lf:
            raise TelegramApiError("Telegram returned audio caption mismatch", provider_effect="may_exist")
        if not message_entities_match(payload.expected_caption_entities, msg.get("caption_entities")):
            raise TelegramApiError("Telegram returned audio caption entities mismatch", provider_effect="may_exist")
        audio_echo = msg.get("audio")
        if not isinstance(audio_echo, dict) or not audio_echo.get("file_id"):
            raise TelegramApiError("Telegram returned no audio file_id", provider_effect="may_exist")
        if audio_echo.get("mime_type") not in (None, "", "audio/mpeg"):
            raise TelegramApiError("Telegram returned wrong audio mime type", provider_effect="may_exist")
        if audio_echo.get("title") not in (None, "", payload.title):
            raise TelegramApiError("Telegram returned wrong audio title", provider_effect="may_exist")
        if audio_echo.get("performer") not in (None, "", payload.performer):
            raise TelegramApiError("Telegram returned wrong audio performer", provider_effect="may_exist")
        return _receipt(
            profile,
            publication_id=payload.publication_id,
            payload_sha256=payload.provider_payload_sha256,
            target=target,
            message_id=_message_id(msg),
            now=instant,
        )
    finally:
        if own_client:
            http_client.close()


__all__ = ["GenericAudioPayload", "render_audio_payload", "send_audio_once"]
