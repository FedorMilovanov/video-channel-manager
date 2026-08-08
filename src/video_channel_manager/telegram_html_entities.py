from __future__ import annotations

from html.parser import HTMLParser
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

GenericMessageEntityType = Literal["bold", "italic", "text_link"]


class GenericMessageEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: GenericMessageEntityType
    offset: int = Field(ge=0)
    length: int = Field(gt=0)
    url: str | None = None

    @model_validator(mode="after")
    def validate_url_contract(self) -> "GenericMessageEntity":
        if self.type == "text_link":
            if not self.url:
                raise ValueError("text_link entity requires a URL")
        elif self.url is not None:
            raise ValueError("only text_link entities may contain a URL")
        return self


class _TelegramHtmlEntityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.entities: list[GenericMessageEntity] = []
        self._utf16_offset = 0
        self._stack: list[tuple[str, GenericMessageEntityType, int, str | None]] = []

    @staticmethod
    def _utf16_length(value: str) -> int:
        return len(value.encode("utf-16-le")) // 2

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        self._utf16_offset += self._utf16_length(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized in {"b", "strong"}:
            self._stack.append((normalized, "bold", self._utf16_offset, None))
            return
        if normalized in {"i", "em"}:
            self._stack.append((normalized, "italic", self._utf16_offset, None))
            return
        if normalized == "a":
            href = next((value for key, value in attrs if key.casefold() == "href"), None)
            if not href:
                raise ValueError("Telegram HTML link is missing href")
            self._stack.append((normalized, "text_link", self._utf16_offset, href))
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
        }.get(normalized)
        if expected_group is None:
            raise ValueError(f"unsupported Telegram HTML closing tag: </{tag}>")
        if not self._stack:
            raise ValueError(f"unmatched Telegram HTML closing tag: </{tag}>")

        opened_tag, entity_type, start, url = self._stack.pop()
        if opened_tag not in expected_group:
            raise ValueError(f"mismatched Telegram HTML closing tag: </{tag}>")
        length = self._utf16_offset - start
        if length <= 0:
            raise ValueError(f"empty Telegram HTML formatting entity: <{opened_tag}>")
        self.entities.append(GenericMessageEntity(type=entity_type, offset=start, length=length, url=url))

    def close(self) -> None:
        super().close()
        if self._stack:
            raise ValueError("unclosed Telegram HTML formatting tag")


def parse_telegram_html(value: str) -> tuple[str, tuple[GenericMessageEntity, ...]]:
    parser = _TelegramHtmlEntityParser()
    parser.feed(value)
    parser.close()
    entities = tuple(
        sorted(
            parser.entities,
            key=lambda entity: (entity.offset, entity.length, entity.type, entity.url or ""),
        )
    )
    return "".join(parser.parts), entities


def message_entities_match(expected: tuple[GenericMessageEntity, ...], actual: Any) -> bool:
    if not isinstance(actual, list):
        return not expected

    relevant_types = {"bold", "italic", "text_link"}
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
        try:
            normalized.append(
                GenericMessageEntity(
                    type=typed_entity_type,
                    offset=offset,
                    length=length,
                    url=url,
                )
            )
        except ValueError:
            return False

    expected_sorted = sorted(
        expected,
        key=lambda item: (item.offset, item.length, item.type, item.url or ""),
    )
    actual_sorted = sorted(
        normalized,
        key=lambda item: (item.offset, item.length, item.type, item.url or ""),
    )
    return actual_sorted == expected_sorted


__all__ = ["GenericMessageEntity", "message_entities_match", "parse_telegram_html"]
