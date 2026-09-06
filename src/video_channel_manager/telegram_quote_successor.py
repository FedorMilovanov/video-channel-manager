from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

LEGACY_QUEUE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"

RightsClass = Literal["public_domain_contiguous_excerpt", "modern_short_quote_editorial_context"]
SourceTier = Literal["public_domain_primary_text", "official_author_or_ministry"]
Theme = Literal[
    "trinity",
    "christ",
    "grace",
    "faith",
    "repentance",
    "sin_mortification",
    "humility",
    "sovereignty",
    "providence",
    "resurrection_eternity",
    "worship_fear_obedience",
    "church_love_service",
]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def word_count(value: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", value, flags=re.UNICODE))


class SuccessorSourceProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    author: str = Field(min_length=2, max_length=120)
    work: str = Field(min_length=2, max_length=240)
    location: str = Field(min_length=2, max_length=300)
    url: str = Field(pattern=r"^https://")
    publisher: str = Field(min_length=2, max_length=160)
    source_tier: SourceTier
    rights_class: RightsClass
    original_language: Literal["en"] = "en"
    exact_fragment: str = Field(min_length=20, max_length=1400)
    checked_on: date
    verification_status: Literal["accepted"] = "accepted"

    @field_validator("url")
    @classmethod
    def require_public_https_host(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.hostname or parsed.hostname in {"localhost", "127.0.0.1"}:
            raise ValueError("source proof must use a public HTTPS host")
        return value

    @model_validator(mode="after")
    def rights_match_source_tier(self) -> "SuccessorSourceProof":
        count = word_count(self.exact_fragment)
        if self.rights_class == "modern_short_quote_editorial_context":
            if self.source_tier != "official_author_or_ministry":
                raise ValueError("modern quote fragments require an official author/ministry source")
            if count > 25:
                raise ValueError("modern exact source fragments are limited to 25 words")
        elif self.source_tier != "public_domain_primary_text":
            raise ValueError("public-domain excerpts require a public-domain primary-text source")
        return self

    @property
    def fragment_sha256(self) -> str:
        return sha256_text(self.exact_fragment)


class SuccessorQuoteCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=60)
    publication_id: str = Field(pattern=r"^lordchrist-successor-[a-z0-9][a-z0-9-]{4,90}$")
    title: str = Field(min_length=2, max_length=160)
    theme: Theme
    quote_ru: str = Field(min_length=40, max_length=1800)
    editorial_context_ru: str | None = Field(default=None, max_length=1800)
    attribution_ru: str = Field(min_length=4, max_length=260)
    hashtags: tuple[str, ...]
    semantic_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{5,100}$")
    source: SuccessorSourceProof

    @field_validator("hashtags")
    @classmethod
    def validate_hashtags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 2 <= len(value) <= 6:
            raise ValueError("successor cards require 2..6 hashtags")
        if len(value) != len(set(value)):
            raise ValueError("successor card hashtags must be unique")
        if any(not tag.startswith("#") or any(ch.isspace() for ch in tag) for tag in value):
            raise ValueError("hashtags must be compact #tokens")
        return value

    @model_validator(mode="after")
    def content_matches_rights_class(self) -> "SuccessorQuoteCard":
        if self.source.rights_class == "modern_short_quote_editorial_context":
            if self.editorial_context_ru is None or len(self.editorial_context_ru.strip()) < 80:
                raise ValueError("modern cards require substantial Russian editorial context")
        elif self.editorial_context_ru is not None:
            raise ValueError("public-domain cards must keep editorial context out of the translated quote payload")
        return self

    @property
    def payload_sha256(self) -> str:
        return sha256_text(
            canonical_json(
                {
                    "sequence": self.sequence,
                    "publication_id": self.publication_id,
                    "title": self.title,
                    "theme": self.theme,
                    "quote_ru": self.quote_ru,
                    "editorial_context_ru": self.editorial_context_ru,
                    "attribution_ru": self.attribution_ru,
                    "hashtags": self.hashtags,
                    "semantic_key": self.semantic_key,
                    "source": self.source.model_dump(mode="json"),
                }
            )
        )


class SuccessorQuoteCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-successor-corpus"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    corpus_id: Literal["lordchrist-successor-quotes-v1"]
    predecessor_queue_digest: Literal[LEGACY_QUEUE_DIGEST]
    review_state: Literal["source_verified_staged"]
    posts: tuple[SuccessorQuoteCard, ...]

    @model_validator(mode="after")
    def validate_corpus(self) -> "SuccessorQuoteCorpus":
        if len(self.posts) != 60:
            raise ValueError("successor corpus must contain exactly 60 source-verified cards")
        if [post.sequence for post in self.posts] != list(range(1, 61)):
            raise ValueError("successor sequence must be exactly 1..60")
        ids = [post.publication_id for post in self.posts]
        keys = [post.semantic_key for post in self.posts]
        fragments = [post.source.fragment_sha256 for post in self.posts]
        if len(ids) != len(set(ids)):
            raise ValueError("successor publication_id values must be unique")
        if len(keys) != len(set(keys)):
            raise ValueError("successor semantic keys must be unique")
        if len(fragments) != len(set(fragments)):
            raise ValueError("successor exact source fragments must be unique")

        authors = Counter(post.source.author for post in self.posts)
        if len(authors) < 12:
            raise ValueError("successor corpus must contain at least 12 authors")
        if max(authors.values()) > 8:
            raise ValueError("no successor author may occupy more than 8 cards")
        if authors.get("Charles Spurgeon", 0) > 1:
            raise ValueError("Spurgeon is intentionally limited to at most one successor card")

        rights = Counter(post.source.rights_class for post in self.posts)
        if rights["public_domain_contiguous_excerpt"] < 36:
            raise ValueError("successor corpus requires a strong public-domain primary-source majority")
        if not 12 <= rights["modern_short_quote_editorial_context"] <= 24:
            raise ValueError("modern short-quote share must stay within the reviewed copyright-safe band")

        themes = Counter(post.theme for post in self.posts)
        if len(themes) < 10:
            raise ValueError("successor corpus must cover at least ten theological themes")
        return self

    @property
    def digest(self) -> str:
        return sha256_text(
            canonical_json(
                {
                    "schema_version": self.schema_version,
                    "project_key": self.project_key,
                    "channel_username": self.channel_username,
                    "corpus_id": self.corpus_id,
                    "predecessor_queue_digest": self.predecessor_queue_digest,
                    "posts": [
                        {
                            "sequence": post.sequence,
                            "publication_id": post.publication_id,
                            "payload_sha256": post.payload_sha256,
                        }
                        for post in self.posts
                    ],
                }
            )
        )


class SuccessorCorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-successor-corpus-manifest"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    corpus_id: Literal["lordchrist-successor-quotes-v1"]
    predecessor_queue_digest: Literal[LEGACY_QUEUE_DIGEST]
    review_state: Literal["source_verified_staged"]
    shards: tuple[str, ...]

    @field_validator("shards")
    @classmethod
    def validate_shards(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != 12 or len(value) != len(set(value)):
            raise ValueError("successor manifest must bind exactly twelve unique author shards")
        for shard in value:
            candidate = Path(shard)
            if candidate.is_absolute() or ".." in candidate.parts or candidate.suffix != ".json":
                raise ValueError("successor shard paths must be relative JSON paths without traversal")
        return value


class SuccessorRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-successor-release"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-quotes-v1"]
    corpus_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    predecessor_queue_digest: Literal[LEGACY_QUEUE_DIGEST]
    activation_policy: Literal["after_predecessor_queue_complete"]
    release_state: Literal["staged_provider_inert"]
    provider_writes_authorized: Literal[False]


def _load_sharded_corpus(path: Path, manifest: SuccessorCorpusManifest) -> SuccessorQuoteCorpus:
    posts: list[dict[str, Any]] = []
    for shard_name in manifest.shards:
        shard_path = path.parent / shard_name
        try:
            payload = json.loads(shard_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid LordChrist successor shard {shard_path}: {exc}") from exc
        if not isinstance(payload, list):
            raise ValueError(f"successor shard {shard_path} must contain a JSON array")
        posts.extend(payload)
    return SuccessorQuoteCorpus.model_validate(
        {
            "schema_name": "video-channel-manager.telegram-quote-successor-corpus",
            "schema_version": 1,
            "project_key": manifest.project_key,
            "channel_username": manifest.channel_username,
            "corpus_id": manifest.corpus_id,
            "predecessor_queue_digest": manifest.predecessor_queue_digest,
            "review_state": manifest.review_state,
            "posts": posts,
        }
    )


def load_successor_corpus(path: Path) -> SuccessorQuoteCorpus:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid LordChrist successor quote corpus {path}: {exc}") from exc
    try:
        if data.get("schema_name") == "video-channel-manager.telegram-quote-successor-corpus-manifest":
            manifest = SuccessorCorpusManifest.model_validate(data)
            return _load_sharded_corpus(path, manifest)
        return SuccessorQuoteCorpus.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid LordChrist successor quote corpus {path}: {exc}") from exc


def load_successor_release(path: Path, corpus: SuccessorQuoteCorpus) -> SuccessorRelease:
    try:
        release = SuccessorRelease.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist successor release {path}: {exc}") from exc
    if release.corpus_digest != corpus.digest:
        raise ValueError("successor release digest does not match exact corpus")
    if release.predecessor_queue_digest != corpus.predecessor_queue_digest:
        raise ValueError("successor release predecessor binding differs from corpus")
    return release
