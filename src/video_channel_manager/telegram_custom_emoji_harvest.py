from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, Sequence
from urllib.parse import quote_plus

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import DEFAULT_API_BASE
from video_channel_manager.telegram_transport import _api_call, _result_list

_ID_RE = re.compile(r"(?<!\d)([0-9]{10,22})(?!\d)")
_TG_EMOJI_RE = re.compile(r"tg://emoji\?id=([0-9]{10,22})", re.IGNORECASE)
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class CustomEmojiExemplarSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,64}$")
    query: str = Field(min_length=3, max_length=200)
    fingerprint: str = Field(min_length=8, max_length=300)
    expected_date: date


class CustomEmojiExemplarConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-custom-emoji-exemplars"]
    schema_version: Literal[1]
    channel_username: str = Field(pattern=r"^@[A-Za-z0-9_]{5,32}$")
    exemplars: tuple[CustomEmojiExemplarSpec, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_keys(self) -> "CustomEmojiExemplarConfig":
        keys = [item.key for item in self.exemplars]
        if len(set(keys)) != len(keys):
            raise ValueError("custom emoji exemplar keys must be unique")
        return self


class HarvestedExemplar(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    message_id: int = Field(gt=0)
    message_url: str
    message_date_utc: datetime
    visible_text_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    custom_emoji_ids: tuple[str, ...]


class VerifiedCustomEmoji(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    custom_emoji_id: str = Field(pattern=r"^[0-9]{10,22}$")
    emoji: str = Field(min_length=1, max_length=32)
    set_name: str | None = None
    is_animated: bool
    is_video: bool
    needs_repainting: bool
    source_exemplar_keys: tuple[str, ...]
    source_message_ids: tuple[int, ...]


class CustomEmojiHarvestReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-custom-emoji-harvest-report"]
    schema_version: Literal[1]
    channel_username: str
    checked_at_utc: datetime
    public_archive_reads_only: Literal[True] = True
    bot_api_validation_performed: bool
    provider_write_performed: Literal[False] = False
    exemplars: tuple[HarvestedExemplar, ...]
    all_custom_emoji_ids: tuple[str, ...]
    verified_custom_emoji: tuple[VerifiedCustomEmoji, ...]

    @model_validator(mode="after")
    def validate_verification_shape(self) -> "CustomEmojiHarvestReport":
        if self.bot_api_validation_performed:
            verified = {item.custom_emoji_id for item in self.verified_custom_emoji}
            if verified != set(self.all_custom_emoji_ids):
                raise ValueError("Bot API verification must cover every harvested custom emoji id")
        elif self.verified_custom_emoji:
            raise ValueError("verified custom emoji metadata requires Bot API validation")
        return self


class _PublicMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: int = Field(gt=0)
    message_date_utc: datetime
    text: str
    custom_emoji_ids: tuple[str, ...]


class _TelegramSearchPageParser(HTMLParser):
    def __init__(self, *, channel_username: str) -> None:
        super().__init__(convert_charrefs=True)
        self._bare_channel = channel_username.removeprefix("@").casefold()
        self.messages: list[_PublicMessage] = []
        self._message_depth = 0
        self._text_depth = 0
        self._message_id: int | None = None
        self._message_date: datetime | None = None
        self._parts: list[str] = []
        self._custom_ids: list[str] = []

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return set(attrs.get("class", "").split())

    @staticmethod
    def _extract_custom_ids(tag: str, attrs: dict[str, str]) -> tuple[str, ...]:
        ids: set[str] = set()
        for key, value in attrs.items():
            lowered_key = key.casefold()
            lowered_value = value.casefold()
            if "emoji" in lowered_key or "document" in lowered_key or tag.casefold() == "tg-emoji":
                ids.update(_ID_RE.findall(value))
            ids.update(_TG_EMOJI_RE.findall(value))
            if "emoji" in lowered_value and ("id" in lowered_value or "document" in lowered_value):
                ids.update(_ID_RE.findall(value))
        return tuple(sorted(ids, key=int))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        values = {key.casefold(): value or "" for key, value in attrs}
        classes = self._classes(values)

        if self._message_depth == 0:
            data_post = values.get("data-post", "")
            if normalized != "div" or "tgme_widget_message" not in classes or not data_post:
                return
            try:
                channel, raw_id = data_post.rsplit("/", 1)
                message_id = int(raw_id)
            except (ValueError, TypeError):
                return
            if channel.casefold() != self._bare_channel or message_id <= 0:
                return
            self._message_depth = 1
            self._message_id = message_id
            self._message_date = None
            self._parts = []
            self._custom_ids = list(self._extract_custom_ids(normalized, values))
            return

        if normalized not in _VOID_TAGS:
            self._message_depth += 1
        self._custom_ids.extend(self._extract_custom_ids(normalized, values))

        if normalized == "time" and values.get("datetime"):
            try:
                parsed = datetime.fromisoformat(values["datetime"].replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is not None:
                self._message_date = parsed.astimezone(UTC)

        if self._text_depth:
            if normalized not in _VOID_TAGS:
                self._text_depth += 1
            if normalized == "br":
                self._parts.append("\n")
            elif normalized == "img" and values.get("alt"):
                self._parts.append(values["alt"])
            return

        if normalized == "div" and "tgme_widget_message_text" in classes:
            self._text_depth = 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._message_depth == 0:
            return
        values = {key.casefold(): value or "" for key, value in attrs}
        normalized = tag.casefold()
        self._custom_ids.extend(self._extract_custom_ids(normalized, values))
        if self._text_depth and normalized == "br":
            self._parts.append("\n")
        elif self._text_depth and normalized == "img" and values.get("alt"):
            self._parts.append(values["alt"])

    def handle_data(self, data: str) -> None:
        if self._text_depth:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._message_depth == 0:
            return
        normalized = tag.casefold()
        if normalized in _VOID_TAGS:
            return

        if self._text_depth:
            self._text_depth -= 1

        self._message_depth -= 1
        if self._message_depth != 0:
            return

        if self._message_id is not None and self._message_date is not None:
            self.messages.append(
                _PublicMessage(
                    message_id=self._message_id,
                    message_date_utc=self._message_date,
                    text=_normalize_visible_text("".join(self._parts)),
                    custom_emoji_ids=tuple(sorted(set(self._custom_ids), key=int)),
                )
            )
        self._message_id = None
        self._message_date = None
        self._parts = []
        self._custom_ids = []
        self._text_depth = 0


def _normalize_visible_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in value.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_exemplar_config(path: Path) -> CustomEmojiExemplarConfig:
    try:
        return CustomEmojiExemplarConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid custom emoji exemplar config {path}: {exc}") from exc


def _select_exemplar_message(
    messages: Sequence[_PublicMessage],
    *,
    spec: CustomEmojiExemplarSpec,
) -> _PublicMessage:
    fingerprint = _normalize_visible_text(spec.fingerprint).casefold()
    candidates = [message for message in messages if fingerprint in message.text.casefold()]
    dated = [message for message in candidates if message.message_date_utc.date() == spec.expected_date]
    selected = dated if dated else candidates
    if len(selected) != 1:
        raise ValueError(
            f"expected exactly one public Telegram exemplar for {spec.key}; found {len(selected)}"
        )
    return selected[0]


def _fetch_exemplars(
    config: CustomEmojiExemplarConfig,
    *,
    client: httpx.Client,
) -> tuple[HarvestedExemplar, ...]:
    bare_channel = config.channel_username.removeprefix("@")
    harvested: list[HarvestedExemplar] = []
    for spec in config.exemplars:
        url = f"https://t.me/s/{bare_channel}?q={quote_plus(spec.query)}"
        response = client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").casefold()
        if content_type and "text/html" not in content_type:
            raise ValueError(f"Telegram public search returned non-HTML for {spec.key}")
        parser = _TelegramSearchPageParser(channel_username=config.channel_username)
        parser.feed(response.text)
        parser.close()
        message = _select_exemplar_message(parser.messages, spec=spec)
        harvested.append(
            HarvestedExemplar(
                key=spec.key,
                message_id=message.message_id,
                message_url=f"https://t.me/{bare_channel}/{message.message_id}",
                message_date_utc=message.message_date_utc,
                visible_text_sha256=_sha256_text(message.text),
                custom_emoji_ids=message.custom_emoji_ids,
            )
        )
    if not any(item.custom_emoji_ids for item in harvested):
        raise ValueError("no custom emoji ids were discoverable in the selected public Telegram exemplars")
    return tuple(harvested)


def _verify_custom_emoji_ids(
    *,
    token: str,
    api_base: str,
    custom_ids: tuple[str, ...],
    exemplars: tuple[HarvestedExemplar, ...],
    client: httpx.Client,
) -> tuple[VerifiedCustomEmoji, ...]:
    result = _api_call(
        client,
        api_base=api_base,
        token=token,
        method="getCustomEmojiStickers",
        payload={"custom_emoji_ids": list(custom_ids)},
        mutation=False,
    )
    stickers = _result_list(result, method="getCustomEmojiStickers")
    by_id: dict[str, dict[str, Any]] = {}
    for raw in stickers:
        if not isinstance(raw, dict):
            raise ValueError("getCustomEmojiStickers returned a non-object sticker")
        custom_id = str(raw.get("custom_emoji_id") or "")
        if custom_id in by_id:
            raise ValueError("getCustomEmojiStickers returned a duplicate custom emoji id")
        if custom_id:
            by_id[custom_id] = raw

    if set(by_id) != set(custom_ids):
        missing = sorted(set(custom_ids) - set(by_id), key=int)
        unexpected = sorted(set(by_id) - set(custom_ids), key=int)
        raise ValueError(f"custom emoji verification mismatch; missing={missing} unexpected={unexpected}")

    verified: list[VerifiedCustomEmoji] = []
    for custom_id in custom_ids:
        raw = by_id[custom_id]
        fallback = str(raw.get("emoji") or "").strip()
        if not fallback:
            raise ValueError(f"custom emoji {custom_id} has no fallback emoji")
        sources = [item for item in exemplars if custom_id in item.custom_emoji_ids]
        verified.append(
            VerifiedCustomEmoji(
                custom_emoji_id=custom_id,
                emoji=fallback,
                set_name=str(raw.get("set_name") or "") or None,
                is_animated=bool(raw.get("is_animated")),
                is_video=bool(raw.get("is_video")),
                needs_repainting=bool(raw.get("needs_repainting")),
                source_exemplar_keys=tuple(item.key for item in sources),
                source_message_ids=tuple(item.message_id for item in sources),
            )
        )
    return tuple(verified)


def harvest_custom_emoji(
    config: CustomEmojiExemplarConfig,
    *,
    token: str | None = None,
    api_base: str = DEFAULT_API_BASE,
    checked_at_utc: datetime | None = None,
    client: httpx.Client | None = None,
) -> CustomEmojiHarvestReport:
    own_client = client is None
    http_client = client or httpx.Client(
        timeout=httpx.Timeout(connect=15, read=30, write=30, pool=15),
        transport=httpx.HTTPTransport(retries=2),
        follow_redirects=False,
        trust_env=False,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "video-channel-manager/svodka-custom-emoji-harvest",
        },
    )
    try:
        exemplars = _fetch_exemplars(config, client=http_client)
        all_ids = tuple(
            sorted(
                {custom_id for exemplar in exemplars for custom_id in exemplar.custom_emoji_ids},
                key=int,
            )
        )
        verified = (
            _verify_custom_emoji_ids(
                token=token,
                api_base=api_base,
                custom_ids=all_ids,
                exemplars=exemplars,
                client=http_client,
            )
            if token
            else ()
        )
        return CustomEmojiHarvestReport(
            schema_name="video-channel-manager.telegram-custom-emoji-harvest-report",
            schema_version=1,
            channel_username=config.channel_username,
            checked_at_utc=checked_at_utc or datetime.now(tz=UTC),
            bot_api_validation_performed=bool(token),
            exemplars=exemplars,
            all_custom_emoji_ids=all_ids,
            verified_custom_emoji=verified,
        )
    finally:
        if own_client:
            http_client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harvest Svodka custom emoji ids from public historical posts.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-bot-api", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_exemplar_config(args.config)
    token = None
    if args.verify_bot_api:
        token = os.environ.get("SVODKA_TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("SVODKA_TELEGRAM_BOT_TOKEN is required for Bot API verification")
    report = harvest_custom_emoji(config, token=token)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "channel_username": report.channel_username,
                "exemplar_message_ids": [item.message_id for item in report.exemplars],
                "custom_emoji_count": len(report.all_custom_emoji_ids),
                "custom_emoji_ids": list(report.all_custom_emoji_ids),
                "bot_api_validation_performed": report.bot_api_validation_performed,
                "provider_write_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
