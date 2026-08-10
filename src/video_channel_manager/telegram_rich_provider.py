from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpOperationClass,
    HttpTransportFailure,
    RetryPolicy,
    execute_http_request,
)
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_models import DEFAULT_API_BASE
from video_channel_manager.telegram_multichannel_transport import GenericMessagePayload, GenericTargetProof
from video_channel_manager.telegram_target_binding import TelegramTargetBinding

RICH_MUTATION_TRANSPORT_RETRIES = 0
DEFAULT_TARGET_PROOF_MAX_AGE = timedelta(minutes=15)
_MEDIA_REFERENCE_RE = re.compile(r"tg://(?P<kind>photo|video|audio)\?id=(?P<id>[A-Za-z0-9_-]{1,64})")
_MEDIA_BLOCK_FIELDS = {
    "animation": "animation",
    "audio": "audio",
    "photo": "photo",
    "video": "video",
    "voice_note": "voice_note",
}
_RICH_BLOCK_TYPES = frozenset(
    {
        "paragraph",
        "heading",
        "pre",
        "footer",
        "divider",
        "mathematical_expression",
        "anchor",
        "list",
        "blockquote",
        "pullquote",
        "collage",
        "slideshow",
        "table",
        "details",
        "map",
        "animation",
        "audio",
        "photo",
        "video",
        "voice_note",
    }
)

RichProviderEffect = Literal["impossible", "not_dispatched", "confirmed_absent", "may_exist", "verified"]
RichStructureVerification = Literal["not_observed", "missing", "malformed", "mismatch", "exact"]
RichMediaVerification = Literal["not_observed", "not_applicable", "missing", "mismatch", "exact"]
RichDispatchPhase = Literal["not_started", "before_request", "request_may_have_been_dispatched", "response_received"]
RichBotVerification = Literal["not_checked", "mismatch", "stale", "exact_same_credential"]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _legacy_fallback_sha256(payload: GenericMessagePayload) -> str:
    return _sha256(
        {
            "kind": "message",
            "project_key": payload.project_key,
            "channel_username": payload.channel_username,
            "publication_id": payload.publication_id,
            "profile_sha256": payload.profile_sha256,
            "html_text": payload.html_text,
            "expected_plain_text": payload.expected_plain_text,
            "expected_entities": [entity.model_dump(mode="json") for entity in payload.expected_entities],
            "parse_mode": payload.parse_mode,
            "link_preview_disabled": payload.link_preview_disabled,
        }
    )


def _strict_positive_int(value: Any) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value if value > 0 else None


def _strict_int(value: Any) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value


def _media_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def walk(candidate: Any, path: str) -> None:
        if isinstance(candidate, dict):
            block_type = candidate.get("type")
            media_field = _MEDIA_BLOCK_FIELDS.get(block_type) if isinstance(block_type, str) else None
            if media_field is not None and media_field in candidate:
                records.append(
                    {
                        "path": path,
                        "type": block_type,
                        "media": candidate[media_field],
                    }
                )
            for key, child in candidate.items():
                walk(child, f"{path}/{key}")
        elif isinstance(candidate, list):
            for index, child in enumerate(candidate):
                walk(child, f"{path}/{index}")

    walk(value, "$")
    return records


def _media_signature(value: Any) -> tuple[tuple[str, str], ...]:
    return tuple((str(record["path"]), str(record["type"])) for record in _media_records(value))


def _textual_character_count(value: Any, *, inside_text: bool = False) -> int:
    if isinstance(value, str):
        return len(value) if inside_text else 0
    if isinstance(value, list):
        return sum(_textual_character_count(item, inside_text=inside_text) for item in value)
    if not isinstance(value, dict):
        return 0
    total = 0
    for key, child in value.items():
        textual = key in {"text", "summary", "credit", "caption", "expression", "label"}
        total += _textual_character_count(child, inside_text=textual)
    return total


def _validate_rich_limits(value: dict[str, Any]) -> None:
    selected_text = value.get("html") if "html" in value else value.get("markdown")
    character_count = (
        len(selected_text) if isinstance(selected_text, str) else _textual_character_count(value.get("blocks"))
    )
    if character_count > 32768:
        raise ValueError("rich message exceeds the official 32768-character limit")
    top_level_media = value.get("media")
    top_level_media_count = len(top_level_media) if isinstance(top_level_media, list) else 0
    if top_level_media_count + len(_media_records(value)) > 50:
        raise ValueError("rich message exceeds the official 50-media limit")


def _require_int_range(value: Any, *, field_name: str, minimum: int, maximum: int) -> int:
    parsed = _strict_int(value)
    if parsed is None or not minimum <= parsed <= maximum:
        raise ValueError(f"{field_name} must be an integer between {minimum} and {maximum}")
    return parsed


def _validate_true_only_fields(value: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field_name in fields:
        if field_name in value and value[field_name] is not True:
            raise ValueError(f"rich {field_name} must be omitted or exactly true")


def _validate_caption(value: Any) -> None:
    if not isinstance(value, dict) or "text" not in value or set(value) - {"text", "credit"}:
        raise ValueError("rich block caption must contain text and optional credit only")


def _validate_location(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("rich map location must be a Location object")
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    if isinstance(latitude, bool) or not isinstance(latitude, int | float) or not -90 <= latitude <= 90:
        raise ValueError("rich map latitude is invalid")
    if isinstance(longitude, bool) or not isinstance(longitude, int | float) or not -180 <= longitude <= 180:
        raise ValueError("rich map longitude is invalid")


def _validate_table_cells(value: Any) -> int:
    if not isinstance(value, list) or not value:
        raise ValueError("rich table must contain rows")
    cell_count = 0
    for row in value:
        if not isinstance(row, list) or not row:
            raise ValueError("rich table row must contain cells")
        for cell in row:
            if not isinstance(cell, dict):
                raise ValueError("rich table cell must be an object")
            if set(cell) - {"text", "is_header", "colspan", "rowspan", "align", "valign"}:
                raise ValueError("rich table cell contains unsupported fields")
            _validate_true_only_fields(cell, ("is_header",))
            for span_name in ("colspan", "rowspan"):
                if span_name in cell:
                    parsed = _strict_int(cell[span_name])
                    if parsed is None or parsed <= 1:
                        raise ValueError(f"rich table {span_name} must be an integer greater than 1")
            if cell.get("align") not in {"left", "center", "right"}:
                raise ValueError("rich table cell align is invalid")
            if cell.get("valign") not in {"top", "middle", "bottom"}:
                raise ValueError("rich table cell valign is invalid")
            cell_count += 1
    return cell_count


def _allowed_block_fields(block_type: str, *, outgoing: bool) -> set[str]:
    common: dict[str, set[str]] = {
        "paragraph": {"type", "text"},
        "heading": {"type", "text", "size"},
        "pre": {"type", "text", "language"},
        "footer": {"type", "text"},
        "divider": {"type"},
        "mathematical_expression": {"type", "expression"},
        "anchor": {"type", "name"},
        "list": {"type", "items"},
        "blockquote": {"type", "blocks", "credit"},
        "pullquote": {"type", "text", "credit"},
        "collage": {"type", "blocks", "caption"},
        "slideshow": {"type", "blocks", "caption"},
        "table": {"type", "cells", "is_bordered", "is_striped", "caption"},
        "details": {"type", "summary", "blocks", "is_open"},
        "map": {"type", "location", "zoom", "width", "height", "caption"},
        "animation": {"type", "animation", "caption"},
        "audio": {"type", "audio", "caption"},
        "photo": {"type", "photo", "caption"},
        "video": {"type", "video", "caption"},
        "voice_note": {"type", "voice_note", "caption"},
    }
    allowed = set(common[block_type])
    if not outgoing and block_type in {"animation", "photo", "video"}:
        allowed.add("has_spoiler")
    return allowed


def _validate_block_tree(blocks: Any, *, outgoing: bool, depth: int = 1) -> int:
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("rich block collection must be a non-empty list")
    if depth > 16:
        raise ValueError("rich block nesting exceeds the official 16-level limit")

    count = 0
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("each rich block must be an object")
        block_type = block.get("type")
        if block_type not in _RICH_BLOCK_TYPES:
            if block_type == "thinking":
                raise ValueError("thinking blocks are draft-only and cannot be used or received by sendRichMessage")
            raise ValueError("rich block type is unsupported by the reviewed Bot API contract")
        if set(block) - _allowed_block_fields(str(block_type), outgoing=outgoing):
            raise ValueError(f"rich {block_type} block contains unsupported fields")
        count += 1

        if block_type in {"paragraph", "heading", "pre", "footer", "pullquote"} and "text" not in block:
            raise ValueError(f"rich {block_type} block has no text")
        if block_type == "heading":
            _require_int_range(block.get("size"), field_name="rich heading size", minimum=1, maximum=6)
        if block_type == "mathematical_expression" and not isinstance(block.get("expression"), str):
            raise ValueError("rich mathematical_expression block has no expression")
        if block_type == "anchor" and (not isinstance(block.get("name"), str) or not block["name"]):
            raise ValueError("rich anchor block has no name")
        if block_type in {"blockquote", "collage", "slideshow", "details"}:
            count += _validate_block_tree(block.get("blocks"), outgoing=outgoing, depth=depth + 1)
        if block_type == "details" and "summary" not in block:
            raise ValueError("rich details block has no summary")
        _validate_true_only_fields(block, ("is_bordered", "is_striped", "is_open", "has_spoiler"))

        if block_type == "list":
            items = block.get("items")
            if not isinstance(items, list) or not items:
                raise ValueError("rich list block has no items")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("rich list item must be an object")
                allowed_item_fields = {"blocks", "has_checkbox", "is_checked", "value", "type"}
                if not outgoing:
                    allowed_item_fields.add("label")
                if set(item) - allowed_item_fields:
                    raise ValueError("rich list item contains unsupported fields")
                if not outgoing and not isinstance(item.get("label"), str):
                    raise ValueError("returned rich list item has no label")
                _validate_true_only_fields(item, ("has_checkbox", "is_checked"))
                if "value" in item and _strict_int(item["value"]) is None:
                    raise ValueError("rich list item value must be an integer")
                if "type" in item and item["type"] not in {"a", "A", "i", "I", "1"}:
                    raise ValueError("rich list item label type is invalid")
                count += 1 + _validate_block_tree(item.get("blocks"), outgoing=outgoing, depth=depth + 1)

        if block_type == "table":
            count += len(block.get("cells", []))
            _validate_table_cells(block.get("cells"))

        if block_type == "map":
            _validate_location(block.get("location"))
            zoom_minimum, zoom_maximum = (0, 24) if outgoing else (13, 20)
            _require_int_range(
                block.get("zoom"), field_name="rich map zoom", minimum=zoom_minimum, maximum=zoom_maximum
            )
            width = _require_int_range(block.get("width"), field_name="rich map width", minimum=0, maximum=10000)
            height = _require_int_range(block.get("height"), field_name="rich map height", minimum=0, maximum=10000)
            if outgoing and (
                width + height > 10000 or min(width, height) == 0 or max(width, height) / min(width, height) > 20
            ):
                raise ValueError("rich map dimensions violate the official total or aspect-ratio limit")

        if "caption" in block and block_type != "table":
            _validate_caption(block["caption"])

        media_field = _MEDIA_BLOCK_FIELDS.get(str(block_type))
        if media_field is not None:
            media = block.get(media_field)
            if outgoing:
                if not isinstance(media, dict) or media.get("type") != block_type:
                    raise ValueError(f"outgoing rich {block_type} block has invalid InputMedia")
                if not isinstance(media.get("media"), str) or not media["media"]:
                    raise ValueError(f"outgoing rich {block_type} block has no media identity")
            elif block_type == "photo":
                if not isinstance(media, list) or not media:
                    raise ValueError("returned rich photo block has no PhotoSize objects")
                for photo_size in media:
                    _validate_returned_file(photo_size, required_numeric=("width", "height"))
            else:
                required_numeric = {
                    "animation": ("width", "height", "duration"),
                    "audio": ("duration",),
                    "video": ("width", "height", "duration"),
                    "voice_note": ("duration",),
                }[str(block_type)]
                _validate_returned_file(media, required_numeric=required_numeric)

    if count > 500:
        raise ValueError("rich message exceeds the official 500-block limit")
    return count


def _validate_returned_file(value: Any, *, required_numeric: tuple[str, ...]) -> None:
    if not isinstance(value, dict):
        raise ValueError("returned rich media is not a Bot API file object")
    if not isinstance(value.get("file_id"), str) or not value["file_id"]:
        raise ValueError("returned rich media has no file_id")
    if not isinstance(value.get("file_unique_id"), str) or not value["file_unique_id"]:
        raise ValueError("returned rich media has no file_unique_id")
    for field_name in required_numeric:
        parsed = _strict_int(value.get(field_name))
        if parsed is None or parsed < 0:
            raise ValueError(f"returned rich media has invalid {field_name}")


def _validate_input_rich_message(value: dict[str, Any]) -> None:
    allowed = {"html", "markdown", "blocks", "media", "is_rtl", "skip_entity_detection"}
    unexpected = set(value) - allowed
    if unexpected:
        raise ValueError(f"InputRichMessage contains unsupported fields: {sorted(unexpected)}")

    selected = [name for name in ("html", "markdown", "blocks") if name in value]
    if len(selected) != 1:
        raise ValueError("InputRichMessage must contain exactly one of html, markdown, or blocks")
    selected_name = selected[0]
    if selected_name in {"html", "markdown"}:
        if not isinstance(value[selected_name], str) or not value[selected_name]:
            raise ValueError(f"InputRichMessage {selected_name} must be a non-empty string")
    elif not isinstance(value["blocks"], list) or not value["blocks"]:
        raise ValueError("InputRichMessage blocks must be a non-empty list")
    else:
        _validate_block_tree(value["blocks"], outgoing=True)

    for flag in ("is_rtl", "skip_entity_detection"):
        if flag in value and not isinstance(value[flag], bool):
            raise ValueError(f"InputRichMessage {flag} must be a boolean")

    media = value.get("media")
    if media is None:
        media_items: list[Any] = []
    elif not isinstance(media, list) or not media:
        raise ValueError("InputRichMessage media must be a non-empty list when present")
    else:
        media_items = media

    media_ids: list[str] = []
    for item in media_items:
        if not isinstance(item, dict) or set(item) != {"id", "media"}:
            raise ValueError("each InputRichMessageMedia must contain exactly id and media")
        media_id = item.get("id")
        media_object = item.get("media")
        if not isinstance(media_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", media_id) is None:
            raise ValueError("InputRichMessageMedia id is invalid")
        if not isinstance(media_object, dict):
            raise ValueError("InputRichMessageMedia media must be an InputMedia object")
        media_type = media_object.get("type")
        if media_type not in {"animation", "audio", "photo", "video", "voice_note"}:
            raise ValueError("InputRichMessageMedia uses an unsupported media type")
        if not isinstance(media_object.get("media"), str) or not media_object["media"]:
            raise ValueError("InputRichMessageMedia media object has no reusable file id, URL, or attachment")
        media_ids.append(media_id)
    if len(media_ids) != len(set(media_ids)):
        raise ValueError("InputRichMessageMedia ids must be unique")

    if selected_name == "blocks" and media_items:
        raise ValueError("block-form InputRichMessage must embed media in blocks, not in the top-level media list")
    if selected_name in {"html", "markdown"}:
        references = [match.group("id") for match in _MEDIA_REFERENCE_RE.finditer(str(value[selected_name]))]
        if sorted(references) != sorted(media_ids):
            raise ValueError("InputRichMessage media ids must exactly match tg:// media references")

    # Reject non-JSON values and non-finite numbers before a document digest is accepted.
    _canonical_json(value)
    _validate_rich_limits(value)


def _validate_expected_rich_message(value: dict[str, Any]) -> None:
    unexpected = set(value) - {"blocks", "is_rtl"}
    if unexpected:
        raise ValueError(f"expected RichMessage contains unsupported fields: {sorted(unexpected)}")
    if not isinstance(value.get("blocks"), list) or not value["blocks"]:
        raise ValueError("expected RichMessage must contain a non-empty blocks list")
    _validate_block_tree(value["blocks"], outgoing=False)
    if "is_rtl" in value and not isinstance(value["is_rtl"], bool):
        raise ValueError("expected RichMessage is_rtl must be a boolean")
    _canonical_json(value)
    _validate_rich_limits(value)


class TelegramRichTargetBinding(BaseModel):
    """Immutable target and bot identity bound into the rich document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-rich-target-binding"]
    schema_version: Literal[1]
    project_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    channel_username: str = Field(pattern=r"^@[A-Za-z0-9_]{5,32}$")
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_binding_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_binding: TelegramTargetBinding
    chat_id: int = Field(lt=0)
    chat_username: str = Field(pattern=r"^[A-Za-z0-9_]{5,32}$")
    bot_id: int = Field(gt=0)
    bot_username: str = Field(pattern=r"^[A-Za-z0-9_]{2,64}$")

    @model_validator(mode="after")
    def usernames_agree(self) -> "TelegramRichTargetBinding":
        if self.channel_username.removeprefix("@").casefold() != self.chat_username.casefold():
            raise ValueError("rich target channel and chat usernames differ")
        source = self.source_binding
        if self.target_binding_sha256 != source.digest:
            raise ValueError("rich target binding digest differs from the exact source binding")
        expected = (
            self.project_key,
            self.channel_username.casefold(),
            self.profile_sha256,
            self.chat_id,
            self.chat_username.casefold(),
            self.bot_id,
            self.bot_username.casefold(),
        )
        actual = (
            source.project_key,
            source.channel_username.casefold(),
            source.profile_sha256,
            source.chat_id,
            source.chat_username.casefold(),
            source.bot_id,
            source.bot_username.casefold(),
        )
        if actual != expected or source.can_post_messages is not True or source.provider_write_performed is not False:
            raise ValueError("rich target identity differs from the exact read-only source binding")
        return self


class TelegramRichMessageDocument(BaseModel):
    """Exact rich request plus the exact RichMessage shape required in Telegram's response.

    The optional legacy payload is only a pre-dispatch fallback. A caller must select
    it before any rich mutation; this module never follows a rich attempt with
    sendMessage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-rich-message-document"]
    schema_version: Literal[1]
    publication_id: str = Field(min_length=5, max_length=96)
    target: TelegramRichTargetBinding
    input_rich_message: dict[str, Any]
    expected_returned_rich_message: dict[str, Any]
    legacy_fallback: GenericMessagePayload | None = None

    @model_validator(mode="after")
    def validate_document(self) -> "TelegramRichMessageDocument":
        _validate_input_rich_message(self.input_rich_message)
        _validate_expected_rich_message(self.expected_returned_rich_message)

        if "blocks" in self.input_rich_message:
            input_signature = _media_signature(self.input_rich_message)
            expected_signature = _media_signature(self.expected_returned_rich_message)
            if input_signature != expected_signature:
                raise ValueError("input and expected rich block media positions or types differ")

        fallback = self.legacy_fallback
        if fallback is not None:
            if fallback.publication_id != self.publication_id:
                raise ValueError("legacy fallback publication differs from rich document")
            if fallback.project_key != self.target.project_key:
                raise ValueError("legacy fallback project differs from rich document")
            if fallback.channel_username.casefold() != self.target.channel_username.casefold():
                raise ValueError("legacy fallback channel differs from rich document")
            if fallback.profile_sha256 != self.target.profile_sha256:
                raise ValueError("legacy fallback profile differs from rich document")
            if fallback.provider_payload_sha256 != _legacy_fallback_sha256(fallback):
                raise ValueError("legacy fallback provider payload digest is invalid")
        return self

    @property
    def input_rich_message_sha256(self) -> str:
        return _sha256(self.input_rich_message)

    @property
    def expected_rich_structure_sha256(self) -> str:
        return _sha256(self.expected_returned_rich_message)

    @property
    def expected_media_sha256(self) -> str | None:
        media = _media_records(self.expected_returned_rich_message)
        return _sha256(media) if media else None

    @property
    def document_sha256(self) -> str:
        return _sha256(self.model_dump(mode="json"))


class TelegramRichRequestTimeout(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connect_seconds: float = Field(default=15, gt=0, le=120)
    read_seconds: float = Field(default=45, gt=0, le=120)
    write_seconds: float = Field(default=30, gt=0, le=120)
    pool_seconds: float = Field(default=15, gt=0, le=120)

    def as_httpx(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.connect_seconds,
            read=self.read_seconds,
            write=self.write_seconds,
            pool=self.pool_seconds,
        )


class TelegramRichProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status_code: int = Field(ge=100, le=599)
    body: Any


class TelegramRichProviderTimeout(TimeoutError):
    def __init__(self, *, request_may_have_been_dispatched: bool) -> None:
        super().__init__("Telegram rich provider timeout")
        self.request_may_have_been_dispatched = request_may_have_been_dispatched


class TelegramRichProviderTransportError(RuntimeError):
    def __init__(self, *, request_may_have_been_dispatched: bool) -> None:
        super().__init__("Telegram rich provider transport failure")
        self.request_may_have_been_dispatched = request_may_have_been_dispatched


class TelegramRichMutationProvider(Protocol):
    def get_me(self, *, timeout: TelegramRichRequestTimeout) -> TelegramRichProviderResponse: ...

    def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message: dict[str, Any],
        timeout: TelegramRichRequestTimeout,
    ) -> TelegramRichProviderResponse: ...


class HttpxTelegramRichMutationProvider(HttpClientOwner):
    """Official Bot API sendRichMessage adapter with exactly one HTTP POST and no retries."""

    def __init__(
        self,
        *,
        token: str,
        api_base: str = DEFAULT_API_BASE,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not token.strip():
            raise ValueError("Telegram bot token is required")
        method_base = f"{api_base.rstrip('/')}/bot{token}"
        self._get_me_url = f"{method_base}/getMe"
        self._send_url = f"{method_base}/sendRichMessage"
        self._initialize_http_client(
            http_client,
            timeout=TelegramRichRequestTimeout().as_httpx(),
            follow_redirects=False,
            trust_env=False,
        )

    def get_me(self, *, timeout: TelegramRichRequestTimeout) -> TelegramRichProviderResponse:
        try:
            result = execute_http_request(
                lambda: self._http_client.post(
                    self._get_me_url,
                    json={},
                    timeout=timeout.as_httpx(),
                ),
                provider="telegram",
                operation=HttpOperationClass.SAFE_READ,
                method="POST",
                resource="getMe",
                retry_policy=RetryPolicy(max_attempts=1),
            )
        except HttpTransportFailure as exc:
            if "Timeout" in exc.cause_type:
                raise TelegramRichProviderTimeout(request_may_have_been_dispatched=False) from exc
            raise TelegramRichProviderTransportError(request_may_have_been_dispatched=False) from exc

        response = result.response
        try:
            body: Any = response.json()
        except ValueError:
            body = None
        return TelegramRichProviderResponse(status_code=response.status_code, body=body)

    def send_rich_message(
        self,
        *,
        chat_id: int,
        rich_message: dict[str, Any],
        timeout: TelegramRichRequestTimeout,
    ) -> TelegramRichProviderResponse:
        try:
            result = execute_http_request(
                lambda: self._http_client.post(
                    self._send_url,
                    json={"chat_id": chat_id, "rich_message": rich_message},
                    timeout=timeout.as_httpx(),
                ),
                provider="telegram",
                operation=HttpOperationClass.AMBIGUOUS_MUTATION,
                method="POST",
                resource="sendRichMessage",
                retry_policy=RetryPolicy(max_attempts=RICH_MUTATION_TRANSPORT_RETRIES + 1),
            )
        except HttpTransportFailure as exc:
            before_request = exc.cause_type in {"ConnectTimeout", "PoolTimeout", "ConnectError"}
            if "Timeout" in exc.cause_type:
                raise TelegramRichProviderTimeout(request_may_have_been_dispatched=not before_request) from exc
            raise TelegramRichProviderTransportError(request_may_have_been_dispatched=not before_request) from exc

        response = result.response
        try:
            body: Any = response.json()
        except ValueError:
            body = None
        return TelegramRichProviderResponse(status_code=response.status_code, body=body)


class TelegramRichProviderOutcome(BaseModel):
    """Evidence, not a delivery assertion.

    `message_id` is reserved for fully verified outcomes. Ambiguous responses may
    retain `observed_message_id` for reconciliation without claiming publication.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-rich-provider-outcome"]
    schema_version: Literal[1]
    publication_id: str = Field(min_length=5, max_length=96)
    project_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    channel_username: str = Field(pattern=r"^@[A-Za-z0-9_]{5,32}$")
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_binding_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_chat_id: int = Field(lt=0)
    expected_chat_username: str = Field(pattern=r"^[A-Za-z0-9_]{5,32}$")
    expected_bot_id: int = Field(gt=0)
    expected_bot_username: str = Field(pattern=r"^[A-Za-z0-9_]{2,64}$")
    target_proof_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_proof_checked_at_utc: datetime
    proof_chat_id: int = Field(lt=0)
    proof_chat_username: str = Field(pattern=r"^[A-Za-z0-9_]{5,32}$")
    proof_bot_id: int = Field(gt=0)
    proof_bot_username: str = Field(pattern=r"^[A-Za-z0-9_]{2,64}$")
    credential_bot_id: int | None = Field(default=None, gt=0)
    credential_bot_username: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_]{2,64}$")
    document_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_rich_message_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_rich_structure_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_media_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    provider_method: Literal["sendRichMessage"] = "sendRichMessage"
    legacy_fallback_method: Literal["sendMessage"] = "sendMessage"
    provider_effect: RichProviderEffect
    automatic_retry_allowed: Literal[False] = False
    provider_call_count: int = Field(ge=0, le=1)
    mutation_request_count: int = Field(ge=0, le=1)
    dispatch_phase: RichDispatchPhase
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    bot_identity_verification: RichBotVerification
    provider_write_gate_verified: bool
    exact_target_binding_verified: bool
    returned_chat_verified: bool
    structure_verification: RichStructureVerification
    media_verification: RichMediaVerification
    returned_rich_structure_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    returned_media_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    observed_message_id: int | None = Field(default=None, gt=0)
    observed_chat_id: int | None = None
    observed_chat_username: str | None = None
    message_id: int | None = Field(default=None, gt=0)
    message_url: str | None = None
    error: str | None = Field(default=None, max_length=1000)
    proves: tuple[str, ...]
    does_not_prove: tuple[str, ...]

    @model_validator(mode="after")
    def validate_evidence(self) -> "TelegramRichProviderOutcome":
        if self.channel_username.removeprefix("@").casefold() != self.expected_chat_username.casefold():
            raise ValueError("outcome channel username differs from expected chat username")
        if self.target_proof_checked_at_utc.tzinfo is None:
            raise ValueError("outcome target proof timestamp must be timezone-aware")
        if self.bot_identity_verification == "exact_same_credential" and (
            self.proof_chat_id != self.expected_chat_id
            or self.proof_chat_username.casefold() != self.expected_chat_username.casefold()
            or self.proof_bot_id != self.expected_bot_id
            or self.proof_bot_username.casefold() != self.expected_bot_username.casefold()
            or self.credential_bot_id != self.expected_bot_id
            or (self.credential_bot_username or "").casefold() != self.expected_bot_username.casefold()
        ):
            raise ValueError("exact bot verification requires matching proof, credential, and expected identity")
        if self.provider_call_count < self.mutation_request_count:
            raise ValueError("mutation request count cannot exceed provider call count")
        if self.provider_effect == "impossible":
            if (
                self.provider_call_count != 0
                or self.mutation_request_count != 0
                or self.dispatch_phase != "not_started"
            ):
                raise ValueError("impossible outcome cannot claim a provider call")
        if self.provider_effect == "not_dispatched":
            if self.mutation_request_count != 0 or self.dispatch_phase != "before_request":
                raise ValueError("not_dispatched outcome requires proof that no mutation request started")
        if self.provider_effect in {"confirmed_absent", "may_exist", "verified"}:
            if self.provider_call_count != 1 or self.mutation_request_count != 1:
                raise ValueError(f"{self.provider_effect} outcome requires exactly one mutation request")
        if self.provider_effect == "verified":
            if (
                self.message_id is None
                or not self.message_url
                or self.error is not None
                or self.bot_identity_verification != "exact_same_credential"
                or not self.provider_write_gate_verified
                or not self.exact_target_binding_verified
                or not self.returned_chat_verified
                or self.observed_chat_id != self.expected_chat_id
                or (self.observed_chat_username or "").casefold() != self.expected_chat_username.casefold()
                or self.message_url != f"https://t.me/{self.expected_chat_username}/{self.message_id}"
                or self.structure_verification != "exact"
                or self.media_verification not in {"exact", "not_applicable"}
                or self.returned_rich_structure_sha256 != self.expected_rich_structure_sha256
                or self.returned_media_sha256 != self.expected_media_sha256
            ):
                raise ValueError(
                    "verified outcome requires exact target, message id, rich structure, and media evidence"
                )
            if self.observed_message_id != self.message_id:
                raise ValueError("verified message_id must equal the observed message id")
        elif self.message_id is not None or self.message_url is not None:
            raise ValueError("non-verified outcome cannot claim a verified message identity")
        if self.provider_effect != "verified" and not self.error:
            raise ValueError("non-verified outcome requires an error")
        return self

    @property
    def archive_bytes(self) -> bytes:
        return (_canonical_json(self.model_dump(mode="json")) + "\n").encode("utf-8")

    @property
    def outcome_sha256(self) -> str:
        return "sha256:" + hashlib.sha256(self.archive_bytes).hexdigest()


class TelegramRichOutcomeArchiveReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-rich-outcome-archive-receipt"]
    schema_version: Literal[1]
    outcome_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    archive_reference: str = Field(min_length=1, max_length=500)
    durable_before_state_mutation: Literal[True]


class ArchivedTelegramRichOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: TelegramRichProviderOutcome
    archive: TelegramRichOutcomeArchiveReceipt

    @model_validator(mode="after")
    def archive_matches_outcome(self) -> "ArchivedTelegramRichOutcome":
        if self.archive.outcome_sha256 != self.outcome.outcome_sha256:
            raise ValueError("archive receipt digest differs from exact provider outcome bytes")
        return self


class TelegramRichOutcomeArchiver(Protocol):
    def archive(
        self,
        outcome_bytes: bytes,
        *,
        outcome_sha256: str,
    ) -> TelegramRichOutcomeArchiveReceipt: ...


RichStateMutation = Callable[[ArchivedTelegramRichOutcome], None]


def _base_outcome(
    document: TelegramRichMessageDocument,
    target: GenericTargetProof,
    **updates: Any,
) -> TelegramRichProviderOutcome:
    values: dict[str, Any] = {
        "schema_name": "video-channel-manager.telegram-rich-provider-outcome",
        "schema_version": 1,
        "publication_id": document.publication_id,
        "project_key": document.target.project_key,
        "channel_username": document.target.channel_username,
        "profile_sha256": document.target.profile_sha256,
        "target_binding_sha256": document.target.target_binding_sha256,
        "expected_chat_id": document.target.chat_id,
        "expected_chat_username": document.target.chat_username,
        "expected_bot_id": document.target.bot_id,
        "expected_bot_username": document.target.bot_username,
        "target_proof_sha256": _sha256(target.model_dump(mode="json")),
        "target_proof_checked_at_utc": target.checked_at_utc,
        "proof_chat_id": target.chat_id,
        "proof_chat_username": target.chat_username,
        "proof_bot_id": target.bot_id,
        "proof_bot_username": target.bot_username,
        "credential_bot_id": document.target.bot_id,
        "credential_bot_username": document.target.bot_username,
        "document_sha256": document.document_sha256,
        "input_rich_message_sha256": document.input_rich_message_sha256,
        "expected_rich_structure_sha256": document.expected_rich_structure_sha256,
        "expected_media_sha256": document.expected_media_sha256,
        "provider_effect": "may_exist",
        "provider_call_count": 1,
        "mutation_request_count": 1,
        "dispatch_phase": "request_may_have_been_dispatched",
        "bot_identity_verification": "exact_same_credential",
        "provider_write_gate_verified": True,
        "exact_target_binding_verified": True,
        "returned_chat_verified": False,
        "structure_verification": "not_observed",
        "media_verification": "not_observed",
        "proves": (
            "the exact immutable request document and expected response digests",
            "at most one provider mutation request was made by this transport",
        ),
        "does_not_prove": (
            "the Bot API Message does not echo the authenticated bot identity; that identity comes from fresh preflight",
            "the Bot API does not echo the original rich HTML or Markdown source",
            "client-specific visual rendering beyond the returned RichMessage structure",
        ),
    }
    values.update(updates)
    return TelegramRichProviderOutcome.model_validate(values)


def _preflight_error(
    document: TelegramRichMessageDocument,
    profile: TelegramChannelProfile,
    target: GenericTargetProof,
    *,
    now: datetime,
) -> tuple[str | None, RichBotVerification, bool]:
    binding = document.target
    profile_matches = (
        profile.project_key == binding.project_key
        and profile.channel_username.casefold() == binding.channel_username.casefold()
        and profile.digest == binding.profile_sha256
    )
    if not profile_matches:
        return "runtime profile differs from the exact rich target binding", "mismatch", False
    if not profile.provider_writes_authorized:
        return "runtime profile does not authorize Telegram provider writes", "not_checked", False
    expected = (
        binding.project_key,
        binding.channel_username.casefold(),
        binding.profile_sha256,
        binding.chat_id,
        binding.chat_username.casefold(),
        binding.bot_id,
        binding.bot_username.casefold(),
    )
    actual = (
        target.project_key,
        target.channel_username.casefold(),
        target.profile_sha256,
        target.chat_id,
        target.chat_username.casefold(),
        target.bot_id,
        target.bot_username.casefold(),
    )
    if actual != expected or target.chat_type != "channel" or target.can_post_messages is not True:
        return "fresh target proof differs from the exact rich target or bot binding", "mismatch", True
    age = now - target.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > DEFAULT_TARGET_PROOF_MAX_AGE:
        return "target and bot identity proof is stale or has an invalid future timestamp", "stale", True
    return None, "not_checked", True


def _credential_identity_result(
    document: TelegramRichMessageDocument,
    response: TelegramRichProviderResponse,
) -> tuple[int | None, str | None, str | None, RichProviderEffect]:
    body = response.body
    if not isinstance(body, dict):
        return None, None, "Telegram getMe returned a malformed non-object response", "not_dispatched"
    if not 200 <= response.status_code < 300 or body.get("ok") is not True:
        description = str(body.get("description") or f"HTTP {response.status_code}")[:500]
        error_code = _strict_int(body.get("error_code"))
        effective_code = error_code if error_code is not None else response.status_code
        effect: RichProviderEffect = (
            "not_dispatched"
            if response.status_code == 429 or response.status_code >= 500 or effective_code >= 500
            else "impossible"
        )
        return None, None, f"Telegram getMe did not verify the provider credential: {description}", effect
    result = body.get("result")
    if not isinstance(result, dict) or result.get("is_bot") is not True:
        return None, None, "Telegram getMe returned no valid bot identity", "not_dispatched"
    bot_id = _strict_positive_int(result.get("id"))
    username_value = result.get("username")
    bot_username = username_value if isinstance(username_value, str) and username_value else None
    if bot_id is None or bot_username is None:
        return bot_id, bot_username, "Telegram getMe returned an incomplete bot identity", "not_dispatched"
    if bot_id != document.target.bot_id or bot_username.casefold() != document.target.bot_username.casefold():
        return bot_id, bot_username, "provider credential resolved to an unexpected Telegram bot", "impossible"
    return bot_id, bot_username, None, "verified"


def _rejection_effect(status_code: int, body: dict[str, Any]) -> RichProviderEffect:
    error_code = _strict_int(body.get("error_code"))
    effective_code = error_code if error_code is not None else status_code
    if status_code >= 500 or effective_code >= 500:
        return "may_exist"
    return "confirmed_absent"


def _outcome_from_response(
    document: TelegramRichMessageDocument,
    target: GenericTargetProof,
    response: TelegramRichProviderResponse,
) -> TelegramRichProviderOutcome:
    body = response.body
    if not isinstance(body, dict):
        return _base_outcome(
            document,
            target,
            dispatch_phase="response_received",
            http_status_code=response.status_code,
            error="Telegram returned a malformed non-object response after the mutation request",
        )

    if not 200 <= response.status_code < 300 or body.get("ok") is not True:
        if body.get("ok") is False:
            effect = _rejection_effect(response.status_code, body)
            description = str(body.get("description") or f"HTTP {response.status_code}")
            return _base_outcome(
                document,
                target,
                provider_effect=effect,
                dispatch_phase="response_received",
                http_status_code=response.status_code,
                error=f"Telegram rejected sendRichMessage: {description[:500]}",
                proves=(
                    "the exact immutable request document and expected response digests",
                    "Telegram returned an explicit no-effect rejection"
                    if effect == "confirmed_absent"
                    else "one request was made but provider effect remains ambiguous",
                    "no automatic retry or fallback mutation was attempted",
                ),
            )
        return _base_outcome(
            document,
            target,
            dispatch_phase="response_received",
            http_status_code=response.status_code,
            error="Telegram returned an untrusted HTTP error response after the mutation request",
        )

    result = body.get("result")
    if not isinstance(result, dict):
        return _base_outcome(
            document,
            target,
            dispatch_phase="response_received",
            http_status_code=response.status_code,
            error="Telegram sendRichMessage result is missing or malformed",
        )

    observed_message_id = _strict_positive_int(result.get("message_id"))
    chat = result.get("chat")
    observed_chat_id: int | None = None
    observed_chat_username: str | None = None
    chat_verified = False
    if isinstance(chat, dict):
        observed_chat_id = _strict_int(chat.get("id"))
        username_value = chat.get("username")
        observed_chat_username = username_value if isinstance(username_value, str) else None
        chat_verified = (
            observed_chat_id == document.target.chat_id
            and (observed_chat_username or "").casefold() == document.target.chat_username.casefold()
            and chat.get("type") == "channel"
        )

    returned_rich = result.get("rich_message")
    returned_structure_sha256: str | None = None
    returned_media_sha256: str | None = None
    structure_verification: RichStructureVerification = "not_observed"
    media_verification: RichMediaVerification = "not_observed"
    if returned_rich is None:
        structure_verification = "missing"
        media_verification = "missing" if document.expected_media_sha256 is not None else "not_observed"
    elif not isinstance(returned_rich, dict) or not isinstance(returned_rich.get("blocks"), list):
        structure_verification = "malformed"
        media_verification = "missing" if document.expected_media_sha256 is not None else "not_observed"
    else:
        try:
            _validate_expected_rich_message(returned_rich)
            returned_structure_sha256 = _sha256(returned_rich)
            returned_media = _media_records(returned_rich)
            returned_media_sha256 = _sha256(returned_media) if returned_media else None
        except (TypeError, ValueError):
            structure_verification = "malformed"
            media_verification = "missing" if document.expected_media_sha256 is not None else "not_observed"
        else:
            structure_verification = (
                "exact" if returned_structure_sha256 == document.expected_rich_structure_sha256 else "mismatch"
            )
            if document.expected_media_sha256 is None and returned_media_sha256 is None:
                media_verification = "not_applicable"
            elif returned_media_sha256 is None:
                media_verification = "missing"
            elif returned_media_sha256 == document.expected_media_sha256:
                media_verification = "exact"
            else:
                media_verification = "mismatch"

    common: dict[str, Any] = {
        "dispatch_phase": "response_received",
        "http_status_code": response.status_code,
        "returned_chat_verified": chat_verified,
        "structure_verification": structure_verification,
        "media_verification": media_verification,
        "returned_rich_structure_sha256": returned_structure_sha256,
        "returned_media_sha256": returned_media_sha256,
        "observed_message_id": observed_message_id,
        "observed_chat_id": observed_chat_id,
        "observed_chat_username": observed_chat_username,
    }
    if not chat_verified:
        return _base_outcome(
            document,
            target,
            **common,
            error="Telegram returned a Message for an unexpected or incomplete exact channel identity",
        )
    if observed_message_id is None:
        return _base_outcome(document, target, **common, error="Telegram returned no valid positive message_id")
    if structure_verification in {"missing", "malformed", "not_observed"}:
        return _base_outcome(
            document,
            target,
            **common,
            error="Telegram did not return the complete exact rich structure required by the expected document",
        )
    if media_verification in {"missing", "mismatch"}:
        return _base_outcome(
            document,
            target,
            **common,
            error="Telegram returned rich-message media that differs from the expected document",
        )
    if structure_verification != "exact":
        return _base_outcome(
            document,
            target,
            **common,
            error="Telegram did not return the complete exact rich structure required by the expected document",
        )

    return _base_outcome(
        document,
        target,
        **common,
        provider_effect="verified",
        message_id=observed_message_id,
        message_url=f"https://t.me/{document.target.chat_username}/{observed_message_id}",
        error=None,
        proves=(
            "fresh preflight and same-credential getMe matched the exact target and bot binding",
            "Telegram returned the exact expected channel identity and a positive message_id",
            "the complete returned RichMessage canonical digest matched the expected document",
            "returned media matched exactly"
            if document.expected_media_sha256
            else "the expected and returned structures contain no media blocks",
            "no automatic retry or fallback mutation was attempted",
        ),
    )


def _dispatch_rich_once(
    document: TelegramRichMessageDocument,
    profile: TelegramChannelProfile,
    target: GenericTargetProof,
    provider: TelegramRichMutationProvider,
    *,
    now: datetime,
    timeout: TelegramRichRequestTimeout,
) -> TelegramRichProviderOutcome:
    preflight_error, bot_verification, write_gate_verified = _preflight_error(document, profile, target, now=now)
    if preflight_error is not None:
        return _base_outcome(
            document,
            target,
            provider_effect="impossible",
            provider_call_count=0,
            mutation_request_count=0,
            dispatch_phase="not_started",
            bot_identity_verification=bot_verification,
            credential_bot_id=None,
            credential_bot_username=None,
            provider_write_gate_verified=write_gate_verified,
            exact_target_binding_verified=False,
            error=preflight_error,
            proves=(
                "no provider method was called",
                "the local exact target or bot precondition failed closed",
            ),
        )

    try:
        identity_response = provider.get_me(timeout=timeout)
    except (TelegramRichProviderTimeout, TelegramRichProviderTransportError) as exc:
        return _base_outcome(
            document,
            target,
            provider_effect="not_dispatched",
            provider_call_count=0,
            mutation_request_count=0,
            dispatch_phase="before_request",
            bot_identity_verification="not_checked",
            credential_bot_id=None,
            credential_bot_username=None,
            error=f"Telegram credential identity unavailable before mutation: {type(exc).__name__}",
            proves=(
                "the local profile, target binding, and fresh target proof matched",
                "no Telegram mutation request was dispatched",
            ),
        )
    except Exception as exc:
        return _base_outcome(
            document,
            target,
            provider_effect="not_dispatched",
            provider_call_count=0,
            mutation_request_count=0,
            dispatch_phase="before_request",
            bot_identity_verification="not_checked",
            credential_bot_id=None,
            credential_bot_username=None,
            error=f"unexpected Telegram getMe failure before mutation: {type(exc).__name__}",
            proves=(
                "the local profile, target binding, and fresh target proof matched",
                "no Telegram mutation request was dispatched",
            ),
        )

    credential_bot_id, credential_bot_username, credential_error, credential_effect = _credential_identity_result(
        document, identity_response
    )
    if credential_error is not None:
        return _base_outcome(
            document,
            target,
            provider_effect=credential_effect,
            provider_call_count=0,
            mutation_request_count=0,
            dispatch_phase="not_started" if credential_effect == "impossible" else "before_request",
            bot_identity_verification="mismatch" if credential_bot_id is not None else "not_checked",
            credential_bot_id=credential_bot_id,
            credential_bot_username=credential_bot_username,
            error=credential_error,
            proves=(
                "the local profile, target binding, and fresh target proof matched",
                "no Telegram mutation request was dispatched",
            ),
        )

    try:
        response = provider.send_rich_message(
            chat_id=document.target.chat_id,
            rich_message=document.input_rich_message,
            timeout=timeout,
        )
    except TelegramRichProviderTimeout as exc:
        may_exist = exc.request_may_have_been_dispatched
        return _base_outcome(
            document,
            target,
            provider_effect="may_exist" if may_exist else "not_dispatched",
            provider_call_count=1,
            mutation_request_count=1 if may_exist else 0,
            dispatch_phase="request_may_have_been_dispatched" if may_exist else "before_request",
            error=(
                "Telegram timed out after the mutation request may have been dispatched"
                if may_exist
                else "Telegram timed out before any mutation request was dispatched"
            ),
            proves=(
                "fresh preflight and same-credential getMe matched the exact target and bot binding",
                "no automatic retry or fallback mutation was attempted",
                (
                    "the mutation may have reached Telegram and must be reconciled"
                    if may_exist
                    else "the provider reported that no mutation request was dispatched"
                ),
            ),
        )
    except TelegramRichProviderTransportError as exc:
        may_exist = exc.request_may_have_been_dispatched
        return _base_outcome(
            document,
            target,
            provider_effect="may_exist" if may_exist else "not_dispatched",
            provider_call_count=1,
            mutation_request_count=1 if may_exist else 0,
            dispatch_phase="request_may_have_been_dispatched" if may_exist else "before_request",
            error=(
                "Telegram transport failed after the mutation request may have been dispatched"
                if may_exist
                else "Telegram transport failed before any mutation request was dispatched"
            ),
            proves=(
                "fresh preflight and same-credential getMe matched the exact target and bot binding",
                "no automatic retry or fallback mutation was attempted",
            ),
        )
    except Exception as exc:
        return _base_outcome(
            document,
            target,
            provider_effect="may_exist",
            provider_call_count=1,
            mutation_request_count=1,
            dispatch_phase="request_may_have_been_dispatched",
            error=f"unexpected rich provider failure after dispatch boundary: {type(exc).__name__}",
            proves=(
                "fresh preflight and same-credential getMe matched the exact target and bot binding",
                "no automatic retry or fallback mutation was attempted",
            ),
        )
    return _outcome_from_response(document, target, response)


def publish_rich_once(
    document: TelegramRichMessageDocument,
    target: GenericTargetProof,
    provider: TelegramRichMutationProvider,
    archiver: TelegramRichOutcomeArchiver,
    *,
    profile: TelegramChannelProfile,
    state_mutation: RichStateMutation | None = None,
    now: datetime | None = None,
    timeout: TelegramRichRequestTimeout | None = None,
) -> ArchivedTelegramRichOutcome:
    """Dispatch at most one rich mutation, archive its exact outcome, then mutate state.

    An archive failure or digest mismatch raises before `state_mutation` is called.
    A non-verified rich result never triggers the document's sendMessage fallback.
    """

    effective_now = now or datetime.now(tz=UTC)
    if effective_now.tzinfo is None:
        raise ValueError("rich provider timestamp must be timezone-aware")
    effective_timeout = timeout or TelegramRichRequestTimeout()
    outcome = _dispatch_rich_once(
        document,
        profile,
        target,
        provider,
        now=effective_now,
        timeout=effective_timeout,
    )
    archive_receipt = archiver.archive(outcome.archive_bytes, outcome_sha256=outcome.outcome_sha256)
    archived = ArchivedTelegramRichOutcome(outcome=outcome, archive=archive_receipt)
    if state_mutation is not None:
        state_mutation(archived)
    return archived


__all__ = [
    "ArchivedTelegramRichOutcome",
    "HttpxTelegramRichMutationProvider",
    "RICH_MUTATION_TRANSPORT_RETRIES",
    "RichProviderEffect",
    "TelegramRichMessageDocument",
    "TelegramRichMutationProvider",
    "TelegramRichOutcomeArchiveReceipt",
    "TelegramRichOutcomeArchiver",
    "TelegramRichProviderOutcome",
    "TelegramRichProviderResponse",
    "TelegramRichProviderTimeout",
    "TelegramRichProviderTransportError",
    "TelegramRichRequestTimeout",
    "TelegramRichTargetBinding",
    "publish_rich_once",
]
