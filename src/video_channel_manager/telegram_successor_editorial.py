from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import SHA256_PATTERN
from video_channel_manager.telegram_quote_successor import SuccessorQuoteCorpus

SUCCESSOR_EDITORIAL_SCHEMA = "video-channel-manager.telegram-successor-runtime-editorial"
SUCCESSOR_EDITORIAL_SCHEMA_VERSION = 1
SUCCESSOR_EDITORIAL_FILENAME = "successor-runtime-editorial-v1.json"
SUCCESSOR_CORPUS_ID = "lordchrist-successor-quotes-v1"
SUCCESSOR_RELEASE_ID = "lordchrist-successor-quotes-v1-integrity-v2"


class SuccessorEditorialEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication_id: str = Field(pattern=r"^lordchrist-successor-[a-z0-9][a-z0-9-]{4,90}$")
    editorial_context_ru: str = Field(min_length=80, max_length=1800)

    @model_validator(mode="after")
    def validate_context(self) -> "SuccessorEditorialEntry":
        value = self.editorial_context_ru.strip()
        if value != self.editorial_context_ru:
            raise ValueError("successor editorial context must not contain surrounding whitespace")
        if value.casefold().startswith("пояснение:"):
            raise ValueError("successor editorial context must not embed the presentation label")
        return self


class SuccessorEditorialLayer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-runtime-editorial"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    corpus_id: Literal["lordchrist-successor-quotes-v1"]
    release_id: Literal["lordchrist-successor-quotes-v1-integrity-v2"]
    owning_issue: Literal[665]
    normalized_corpus_digest: str = Field(pattern=SHA256_PATTERN)
    review_state: Literal["editorial_complete"]
    entries: tuple[SuccessorEditorialEntry, ...] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def validate_entries(self) -> "SuccessorEditorialLayer":
        ids = [entry.publication_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("successor editorial publication IDs must be unique")
        return self


def load_successor_editorial_layer(path: Path) -> SuccessorEditorialLayer:
    try:
        return SuccessorEditorialLayer.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist successor editorial layer {path}: {exc}") from exc


def resolve_successor_editorial_contexts(
    corpus: SuccessorQuoteCorpus,
    layer_path: Path,
) -> dict[str, str]:
    """Resolve one visible explanation for every reviewed successor card.

    Source-side editorial contexts remain authoritative. The separate runtime
    layer may fill only cards whose sealed source context is absent. Coverage is
    exact and digest-bound so a missing, stale, or shadowing entry fails closed
    before a runtime queue can become renderable.
    """

    layer = load_successor_editorial_layer(layer_path)
    if layer.normalized_corpus_digest != corpus.digest:
        raise ValueError("successor editorial layer digest differs from the reviewed normalized corpus")

    cards_by_id = {card.publication_id: card for card in corpus.posts}
    source_context_ids = {
        card.publication_id
        for card in corpus.posts
        if card.editorial_context_ru is not None and card.editorial_context_ru.strip()
    }
    fallback_ids = set(cards_by_id) - source_context_ids
    entries_by_id = {entry.publication_id: entry.editorial_context_ru for entry in layer.entries}
    entry_ids = set(entries_by_id)

    if entry_ids != fallback_ids:
        missing = sorted(fallback_ids - entry_ids)
        extra = sorted(entry_ids - fallback_ids)
        raise ValueError(
            f"successor editorial coverage differs from cards lacking source context: missing={missing}, extra={extra}"
        )

    resolved: dict[str, str] = {}
    for card in corpus.posts:
        source_context = card.editorial_context_ru.strip() if card.editorial_context_ru is not None else ""
        context = source_context or entries_by_id.get(card.publication_id, "")
        if len(context) < 80:
            raise ValueError(f"successor editorial context is incomplete for {card.publication_id}")
        if context.casefold().startswith("пояснение:"):
            raise ValueError(f"successor editorial context embeds presentation label for {card.publication_id}")
        resolved[card.publication_id] = context

    if set(resolved) != set(cards_by_id):
        raise ValueError("successor editorial resolution did not cover the complete reviewed corpus")
    return resolved
