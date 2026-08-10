from __future__ import annotations

from html.parser import HTMLParser
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

GenericMessageEntityType = Literal["bold", "italic", "text_link", "custom_emoji"]


class GenericMessageEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: GenericMessageEntityType
    offset: int = Field(ge=0)
    length: int = Field(gt=0)
    url: str | None = None
    custom_emoji_id: str | None = Field(default=None, pattern=r"^[0-9]{10,22}$")

    @model_validator(mode="after")
    def validate_optional_fields_contract(self) -> "GenericMessageEntity":
        if self.type == "text_link":
            if not self.url:
                raise ValueError("text_link entity requires a URL")
            if self.custom_emoji_id is not None:
                raise ValueError("text_link entity must not contain a custom emoji id")
        elif self.type == "custom_emoji":
            if not self.custom_emoji_id:
                raise ValueError("custom_emoji entity requires custom_emoji_id")
            if self.url is not None:
                raise ValueError("custom_emoji entity must not contain a URL")
        elif self.url is not None or self.custom_emoji_id is not None:
            raise ValueError("formatting entities must not contain URL or custom emoji metadata")
        return self

    @model_serializer(mode="plain")
    def serialize_entity(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": self.type,
            "offset": self.offset,
            "length": self.length,
            "url": self.url,
        }
        if self.custom_emoji_id is not None:
            payload["custom_emoji_id"] = self.custom_emoji_id
        return payload


class _TelegramHtmlEntityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.entities: list[GenericMessageEntity] = []
        self._utf16_offset = 0
        self._stack: list[tuple[str, GenericMessageEntityType, int, str | None, str | None]] = []

    @staticmethod
    def _utf16_length(value: str) -> int:
        return len(value.encode("utf-16-le")) // 2

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        self._utf16_offset += self._utf16_length(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized in {"b", "strong"}:
            self._stack.append((normalized, "bold", self._utf16_offset, None, None))
            return
        if normalized in {"i", "em"}:
            self._stack.append((normalized, "italic", self._utf16_offset, None, None))
            return
        if normalized == "a":
            href = next((value for key, value in attrs if key.casefold() == "href"), None)
            if not href:
                raise ValueError("Telegram HTML link is missing href")
            self._stack.append((normalized, "text_link", self._utf16_offset, href, None))
            return
        if normalized == "tg-emoji":
            emoji_id = next((value for key, value in attrs if key.casefold() == "emoji-id"), None)
            if not emoji_id or not emoji_id.isdigit() or not 10 <= len(emoji_id) <= 22:
                raise ValueError("Telegram custom emoji tag requires a numeric emoji-id")
            self._stack.append((normalized, "custom_emoji", self._utf16_offset, None, emoji_id))
            return
        raise ValueError(f"unsupported Telegram HTML tag: <{tag}>")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        expected_group = {
            "b": {"b", "strong"},
            "strong": {"b", "strong"},
            "i": {"i", "em"},
            "em": {"i", "em"},
            "a": {"a"},
            "tg-emoji": {"tg-emoji"},
        }.get(normalized)
        if expected_group is None:
            raise ValueError(f"unsupported Telegram HTML closing tag: </{tag}>")
        if not self._stack:
            raise ValueError(f"unmatched Telegram HTML closing tag: </{tag}>")

        opened_tag, entity_type, start, url, custom_emoji_id = self._stack.pop()
        if opened_tag not in expected_group:
            raise ValueError(f"mismatched Telegram HTML closing tag: </{tag}>")
        length = self._utf16_offset - start
        if length <= 0:
            raise ValueError(f"empty Telegram HTML formatting entity: <{opened_tag}>")
        self.entities.append(
            GenericMessageEntity(
                type=entity_type,
                offset=start,
                length=length,
                url=url,
                custom_emoji_id=custom_emoji_id,
            )
        )

    def close(self) -> None:
        super().close()
        if self._stack:
            raise ValueError("unclosed Telegram HTML formatting tag")


def _entity_sort_key(entity: GenericMessageEntity) -> tuple[int, int, str, str, str]:
    return (
        entity.offset,
        entity.length,
        entity.type,
        entity.url or "",
        entity.custom_emoji_id or "",
    )


def parse_telegram_html(value: str) -> tuple[str, tuple[GenericMessageEntity, ...]]:
    parser = _TelegramHtmlEntityParser()
    parser.feed(value)
    parser.close()
    entities = tuple(sorted(parser.entities, key=_entity_sort_key))
    return "".join(parser.parts), entities


def message_entities_match(expected: tuple[GenericMessageEntity, ...], actual: Any) -> bool:
    if not isinstance(actual, list):
        return not expected

    relevant_types = {"bold", "italic", "text_link", "custom_emoji"}
    normalized: list[GenericMessageEntity] = []
    for entity in actual:
        if not isinstance(entity, dict):
            continue
        entity_type = str(entity.get("type") or "")
        if entity_type not in relevant_types:
            continue
        typed_entity_type = cast(GenericMessageEntityType, entity_type)
        try:
            offset = int(entity["offset"])
            length = int(entity["length"])
        except (KeyError, TypeError, ValueError):
            return False
        url = str(entity.get("url") or "") or None
        custom_emoji_id = str(entity.get("custom_emoji_id") or "") or None
        try:
            normalized.append(
                GenericMessageEntity(
                    type=typed_entity_type,
                    offset=offset,
                    length=length,
                    url=url,
                    custom_emoji_id=custom_emoji_id,
                )
            )
        except ValueError:
            return False

    return sorted(normalized, key=_entity_sort_key) == sorted(expected, key=_entity_sort_key)


__all__ = ["GenericMessageEntity", "message_entities_match", "parse_telegram_html"]
