from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class CustomEmojiCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    custom_emoji_id: str = Field(pattern=r"^[0-9]{10,22}$")
    fallback_emoji: str = Field(min_length=1, max_length=32)
    set_name: str = Field(min_length=1, max_length=128)
    source_message_ids: tuple[int, ...] = Field(min_length=1)


class CustomEmojiNumberSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    set_name: str = Field(min_length=1, max_length=128)
    digits: dict[str, str]


class SvodkaCustomEmojiCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.svodka-custom-emoji-catalog"]
    schema_version: Literal[1]
    channel_username: Literal["@deep_info_life"]
    verified_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    verification_issue: Literal[273]
    verification_comment_id: int = Field(gt=0)
    verification_method: Literal["Telegram Bot API getCustomEmojiStickers"]
    provider_write_performed: Literal[False]
    source_message_ids: tuple[int, ...]
    items: tuple[CustomEmojiCatalogItem, ...] = Field(min_length=1)
    number_sets: dict[str, CustomEmojiNumberSet]
    roles: dict[str, str]
    check_variants: tuple[str, ...]

    @model_validator(mode="after")
    def validate_catalog_integrity(self) -> "SvodkaCustomEmojiCatalog":
        if self.source_message_ids != (12, 17, 20, 23):
            raise ValueError("catalog must stay bound to the four verified historical exemplars")
        if len(self.items) != 67:
            raise ValueError("catalog must contain exactly the 67 Bot-API-verified custom emoji ids")

        ids = [item.custom_emoji_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("custom emoji ids must be globally unique in catalog items")
        by_id = {item.custom_emoji_id: item for item in self.items}
        source_ids = set(self.source_message_ids)
        for item in self.items:
            if not set(item.source_message_ids).issubset(source_ids):
                raise ValueError(f"custom emoji {item.custom_emoji_id} has an unknown source message")

        required_sets = {"primary", "alternate", "compact"}
        if set(self.number_sets) != required_sets:
            raise ValueError("catalog must define primary, alternate, and compact number sets")
        expected_digits = {
            "primary": set("0123456789"),
            "alternate": set("0123456789"),
            "compact": set("12345"),
        }
        for key, number_set in self.number_sets.items():
            if set(number_set.digits) != expected_digits[key]:
                raise ValueError(f"number set {key} has incomplete or unexpected digits")
            for digit, custom_id in number_set.digits.items():
                item = by_id.get(custom_id)
                if item is None:
                    raise ValueError(f"number set {key} references unknown custom emoji {custom_id}")
                if item.set_name != number_set.set_name:
                    raise ValueError(f"number set {key} crosses sticker-set identity")
                if not item.fallback_emoji.startswith(digit):
                    raise ValueError(f"number set {key} digit {digit} has a mismatched fallback")

        if not self.roles:
            raise ValueError("catalog must define curated semantic roles")
        for role, custom_id in self.roles.items():
            if not role or role.strip() != role or "." not in role:
                raise ValueError(f"invalid custom emoji role: {role!r}")
            if custom_id not in by_id:
                raise ValueError(f"role {role} references unknown custom emoji {custom_id}")

        if len(self.check_variants) != 4 or len(set(self.check_variants)) != 4:
            raise ValueError("catalog must preserve all four distinct verified check-mark variants")
        for custom_id in self.check_variants:
            item = by_id.get(custom_id)
            if item is None or item.fallback_emoji != "✅":
                raise ValueError("check variant must reference a verified check-mark custom emoji")
        return self

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def by_id(self) -> dict[str, CustomEmojiCatalogItem]:
        return {item.custom_emoji_id: item for item in self.items}

    def item_for_role(self, role: str) -> CustomEmojiCatalogItem:
        try:
            custom_id = self.roles[role]
        except KeyError as exc:
            raise ValueError(f"unknown custom emoji role: {role}") from exc
        return self.by_id[custom_id]

    def item_for_digit(self, digit: int, *, style: str = "primary") -> CustomEmojiCatalogItem:
        if digit < 0 or digit > 9:
            raise ValueError("custom emoji digit must be between 0 and 9")
        try:
            number_set = self.number_sets[style]
            custom_id = number_set.digits[str(digit)]
        except KeyError as exc:
            raise ValueError(f"digit {digit} is unavailable in number style {style!r}") from exc
        return self.by_id[custom_id]


def load_custom_emoji_catalog(path: Path) -> SvodkaCustomEmojiCatalog:
    try:
        return SvodkaCustomEmojiCatalog.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Svodka custom emoji catalog {path}: {exc}") from exc


def render_custom_emoji(item: CustomEmojiCatalogItem) -> str:
    fallback = html.escape(item.fallback_emoji, quote=False)
    return f'<tg-emoji emoji-id="{item.custom_emoji_id}">{fallback}</tg-emoji>'


def render_role(catalog: SvodkaCustomEmojiCatalog, role: str) -> str:
    return render_custom_emoji(catalog.item_for_role(role))


def render_digit(catalog: SvodkaCustomEmojiCatalog, digit: int, *, style: str = "primary") -> str:
    return render_custom_emoji(catalog.item_for_digit(digit, style=style))


def build_capability_canary_html(catalog: SvodkaCustomEmojiCatalog) -> str:
    microscope = render_role(catalog, "science.microscope")
    number_one = render_digit(catalog, 1, style="primary")
    scroll = render_role(catalog, "history.scroll")
    return (
        f"{microscope} <b>СВОДКА — проверка оформления</b>\n\n"
        f"{number_one} Премиальный номер из исторического набора\n"
        f"{scroll} <i>Исторический акцент</i>\n\n"
        "Техническая проверка: Telegram должен сохранить те же Premium Emoji и форматирование."
    )


__all__ = [
    "CustomEmojiCatalogItem",
    "CustomEmojiNumberSet",
    "SvodkaCustomEmojiCatalog",
    "build_capability_canary_html",
    "load_custom_emoji_catalog",
    "render_custom_emoji",
    "render_digit",
    "render_role",
]
