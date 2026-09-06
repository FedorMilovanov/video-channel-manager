from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

LEGACY_QUEUE_DIGEST = "sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"
REVIEWED_CORPUS_CARD_COUNT = 60
BASE_CANDIDATE_FILENAME = "successor-quotes-v1.json"
TRANSLATION_LEDGER_FILENAME = "successor-translation-ledger-v1.json"

RawSourceTier = Literal["public_domain_primary_text", "official_author_or_ministry"]
RightsClass = Literal["public_domain_contiguous_excerpt", "modern_short_quote_editorial_context"]
SourceTier = Literal["public_domain_primary_text", "official_author_ministry_or_publisher"]
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


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def git_blob_sha1(value: bytes) -> str:
    header = f"blob {len(value)}\0".encode()
    return hashlib.sha1(header + value).hexdigest()


def word_count(value: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", value, flags=re.UNICODE))


def _validate_public_https_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("source proof must use a public HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credential-bearing source URLs are forbidden")
    try:
        literal_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise ValueError("private, loopback, link-local, reserved, or otherwise non-global literal IPs are forbidden")
    return value


class RawSuccessorSourceProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    author: str = Field(min_length=2, max_length=120)
    work: str = Field(min_length=2, max_length=240)
    location: str = Field(min_length=2, max_length=300)
    url: str = Field(pattern=r"^https://")
    publisher: str = Field(min_length=2, max_length=160)
    source_tier: RawSourceTier
    rights_class: RightsClass
    original_language: Literal["en"]
    exact_fragment: str = Field(min_length=20, max_length=1400)
    checked_on: date
    verification_status: Literal["accepted"]

    @field_validator("url")
    @classmethod
    def require_public_https_host(cls, value: str) -> str:
        return _validate_public_https_url(value)

    @model_validator(mode="after")
    def rights_match_source_tier(self) -> "RawSuccessorSourceProof":
        if self.rights_class == "modern_short_quote_editorial_context":
            if self.source_tier != "official_author_or_ministry":
                raise ValueError("modern candidate fragments require a reviewed author/ministry source tier")
            if word_count(self.exact_fragment) > 25:
                raise ValueError("modern candidate exact source fragments are limited to 25 words")
        elif self.source_tier != "public_domain_primary_text":
            raise ValueError("public-domain candidate excerpts require a public-domain primary-text source")
        return self


class RawSuccessorQuoteCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=REVIEWED_CORPUS_CARD_COUNT)
    publication_id: str = Field(pattern=r"^lordchrist-successor-[a-z0-9][a-z0-9-]{4,90}$")
    title: str = Field(min_length=2, max_length=160)
    theme: Theme
    candidate_quote_ru: str = Field(validation_alias="quote_ru", min_length=10, max_length=1800)
    editorial_context_ru: str | None = Field(default=None, max_length=1800)
    attribution_ru: str = Field(min_length=4, max_length=260)
    hashtags: tuple[str, ...]
    semantic_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{5,100}$")
    source: RawSuccessorSourceProof

    @field_validator("hashtags")
    @classmethod
    def validate_hashtags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 2 <= len(value) <= 6:
            raise ValueError("successor candidate cards require 2..6 hashtags")
        if len(value) != len(set(value)):
            raise ValueError("successor candidate hashtags must be unique")
        if any(not tag.startswith("#") or any(ch.isspace() for ch in tag) for tag in value):
            raise ValueError("hashtags must be compact #tokens")
        return value


class RawSuccessorCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-successor-corpus"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    corpus_id: Literal["lordchrist-successor-quotes-v1"]
    predecessor_queue_digest: Literal["sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"]
    review_state: Literal["source_verified_staged"]
    posts: tuple[RawSuccessorQuoteCard, ...]

    @model_validator(mode="after")
    def validate_candidate_inventory(self) -> "RawSuccessorCorpus":
        if len(self.posts) != REVIEWED_CORPUS_CARD_COUNT:
            raise ValueError("successor candidate inventory must contain exactly 60 cards")
        if [post.sequence for post in self.posts] != list(range(1, REVIEWED_CORPUS_CARD_COUNT + 1)):
            raise ValueError("successor candidate sequence must be exactly 1..60")
        ids = [post.publication_id for post in self.posts]
        keys = [post.semantic_key for post in self.posts]
        if len(ids) != len(set(ids)):
            raise ValueError("successor candidate publication_id values must be unique")
        if len(keys) != len(set(keys)):
            raise ValueError("successor candidate semantic keys must be unique")
        return self


class TranslationLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication_id: str = Field(pattern=r"^lordchrist-successor-[a-z0-9][a-z0-9-]{4,90}$")
    quote_ru: str = Field(min_length=10, max_length=1800)
    source_fragment_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    translation_binding_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    scope: Literal["exact_fragment_only"]
    review_state: Literal["reviewed"]
    exact_fragment_override: str | None = Field(default=None, min_length=20, max_length=1400)

    @model_validator(mode="after")
    def allow_only_reviewed_fragment_correction(self) -> "TranslationLedgerEntry":
        if (
            self.exact_fragment_override is not None
            and self.publication_id != "lordchrist-successor-piper-father-spirit-authority"
        ):
            raise ValueError("exact fragment override is only allowed for the reviewed Piper sequence-51 correction")
        return self


class TranslationLedger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-successor-translation-ledger"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    corpus_id: Literal["lordchrist-successor-quotes-v1"]
    entries: tuple[TranslationLedgerEntry, ...]

    @model_validator(mode="after")
    def validate_ledger(self) -> "TranslationLedger":
        if len(self.entries) != REVIEWED_CORPUS_CARD_COUNT:
            raise ValueError("reviewed translation ledger must contain exactly 60 entries")
        ids = [entry.publication_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("reviewed translation ledger publication_id values must be unique")
        return self


class SuccessorSourceProof(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    author: str = Field(min_length=2, max_length=120)
    work: str = Field(min_length=2, max_length=240)
    location: str = Field(min_length=2, max_length=300)
    url: str = Field(pattern=r"^https://")
    publisher: str = Field(min_length=2, max_length=160)
    source_tier: SourceTier
    rights_class: RightsClass
    fragment_language: Literal["en"]
    exact_fragment: str = Field(min_length=20, max_length=1400)
    checked_on: date
    verification_status: Literal["accepted_contiguous_fragment"]

    @field_validator("url")
    @classmethod
    def require_public_https_host(cls, value: str) -> str:
        return _validate_public_https_url(value)

    @model_validator(mode="after")
    def rights_match_source_tier(self) -> "SuccessorSourceProof":
        if self.rights_class == "modern_short_quote_editorial_context":
            if self.source_tier != "official_author_ministry_or_publisher":
                raise ValueError("modern fragments require a reviewed author/ministry/publisher source")
            if word_count(self.exact_fragment) > 25:
                raise ValueError("modern exact source fragments are limited to 25 words")
        elif self.source_tier != "public_domain_primary_text":
            raise ValueError("public-domain excerpts require a public-domain primary-text source")
        return self

    @property
    def fragment_sha256(self) -> str:
        return sha256_text(self.exact_fragment)


class ReviewedTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: Literal["ru"]
    scope: Literal["exact_fragment_only"]
    review_state: Literal["reviewed"]
    source_fragment_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    binding_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SuccessorQuoteCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=REVIEWED_CORPUS_CARD_COUNT)
    publication_id: str = Field(pattern=r"^lordchrist-successor-[a-z0-9][a-z0-9-]{4,90}$")
    title: str = Field(min_length=2, max_length=160)
    theme: Theme
    quote_ru: str = Field(min_length=10, max_length=1800)
    translation: ReviewedTranslation
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
    def bind_visible_translation_to_exact_fragment(self) -> "SuccessorQuoteCard":
        if self.translation.source_fragment_sha256 != self.source.fragment_sha256:
            raise ValueError("reviewed translation is not bound to this exact source fragment")
        expected_binding = sha256_text(
            canonical_json(
                {
                    "source_fragment": self.source.exact_fragment,
                    "quote_ru": self.quote_ru,
                    "language": self.translation.language,
                    "scope": self.translation.scope,
                }
            )
        )
        if self.translation.binding_sha256 != expected_binding:
            raise ValueError("visible translation does not match the reviewed source/translation binding")
        if self.source.rights_class == "modern_short_quote_editorial_context":
            if self.editorial_context_ru is None or len(self.editorial_context_ru.strip()) < 80:
                raise ValueError("modern cards require substantial Russian editorial context")
            if word_count(self.quote_ru) > 25:
                raise ValueError("modern visible translated quotation is limited to 25 words")
        return self

    @property
    def payload_sha256(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


class SuccessorQuoteCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    corpus_id: Literal["lordchrist-successor-quotes-v1"]
    predecessor_queue_digest: Literal["sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"]
    posts: tuple[SuccessorQuoteCard, ...]

    @model_validator(mode="after")
    def validate_corpus(self) -> "SuccessorQuoteCorpus":
        if len(self.posts) != REVIEWED_CORPUS_CARD_COUNT:
            raise ValueError("reviewed successor v1 corpus must contain exactly 60 source-verified cards")
        if [post.sequence for post in self.posts] != list(range(1, REVIEWED_CORPUS_CARD_COUNT + 1)):
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
        if len(authors) != 12:
            raise ValueError("reviewed successor v1 corpus must contain exactly 12 authors")
        if max(authors.values()) > 7:
            raise ValueError("no successor author may occupy more than 7 cards")

        rights = Counter(post.source.rights_class for post in self.posts)
        if rights["public_domain_contiguous_excerpt"] != 42:
            raise ValueError("reviewed successor v1 corpus requires exactly 42 public-domain cards")
        if rights["modern_short_quote_editorial_context"] != 18:
            raise ValueError("reviewed successor v1 corpus requires exactly 18 modern short-quote cards")

        themes = Counter(post.theme for post in self.posts)
        if len(themes) != 12:
            raise ValueError("reviewed successor v1 corpus must cover all 12 theological themes")
        return self

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.model_dump(mode="json")))


class SuccessorRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-quote-successor-release"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-quotes-v1"]
    base_candidate_git_blob_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")
    translation_ledger_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    normalized_corpus_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    predecessor_queue_digest: Literal["sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"]
    activation_policy: Literal["after_predecessor_queue_complete"]
    release_state: Literal["staged_provider_inert"]
    provider_writes_authorized: Literal[False]


def load_raw_successor_corpus(path: Path) -> RawSuccessorCorpus:
    try:
        return RawSuccessorCorpus.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist successor candidate corpus {path}: {exc}") from exc


def load_translation_ledger(path: Path) -> TranslationLedger:
    try:
        return TranslationLedger.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist successor translation ledger {path}: {exc}") from exc


def _normalize_source(raw: RawSuccessorSourceProof, fragment_override: str | None) -> SuccessorSourceProof:
    fragment = fragment_override or raw.exact_fragment
    normalized_tier: SourceTier
    if raw.rights_class == "public_domain_contiguous_excerpt":
        normalized_tier = "public_domain_primary_text"
    else:
        normalized_tier = "official_author_ministry_or_publisher"
    return SuccessorSourceProof(
        author=raw.author,
        work=raw.work,
        location=raw.location,
        url=raw.url,
        publisher=raw.publisher,
        source_tier=normalized_tier,
        rights_class=raw.rights_class,
        fragment_language=raw.original_language,
        exact_fragment=fragment,
        checked_on=raw.checked_on,
        verification_status="accepted_contiguous_fragment",
    )


def load_successor_corpus(candidate_path: Path, translation_ledger_path: Path) -> SuccessorQuoteCorpus:
    raw = load_raw_successor_corpus(candidate_path)
    ledger = load_translation_ledger(translation_ledger_path)
    by_id = {entry.publication_id: entry for entry in ledger.entries}
    raw_ids = {post.publication_id for post in raw.posts}
    if set(by_id) != raw_ids:
        raise ValueError("translation ledger must bind exactly the 60 candidate publication IDs")

    posts: list[SuccessorQuoteCard] = []
    for candidate in raw.posts:
        proof = by_id[candidate.publication_id]
        source = _normalize_source(candidate.source, proof.exact_fragment_override)
        translation = ReviewedTranslation(
            language="ru",
            scope=proof.scope,
            review_state=proof.review_state,
            source_fragment_sha256=proof.source_fragment_sha256,
            binding_sha256=proof.translation_binding_sha256,
        )
        posts.append(
            SuccessorQuoteCard(
                sequence=candidate.sequence,
                publication_id=candidate.publication_id,
                title=candidate.title,
                theme=candidate.theme,
                quote_ru=proof.quote_ru,
                translation=translation,
                editorial_context_ru=candidate.editorial_context_ru,
                attribution_ru=candidate.attribution_ru,
                hashtags=candidate.hashtags,
                semantic_key=candidate.semantic_key,
                source=source,
            )
        )

    return SuccessorQuoteCorpus(
        project_key=raw.project_key,
        channel_username=raw.channel_username,
        corpus_id=raw.corpus_id,
        predecessor_queue_digest=raw.predecessor_queue_digest,
        posts=tuple(posts),
    )


def load_successor_release(
    release_path: Path,
    candidate_path: Path,
    translation_ledger_path: Path,
) -> SuccessorRelease:
    try:
        release = SuccessorRelease.model_validate_json(release_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist successor release {release_path}: {exc}") from exc

    try:
        candidate_bytes = candidate_path.read_bytes()
        ledger_bytes = translation_ledger_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read successor release inputs: {exc}") from exc

    if release.base_candidate_git_blob_sha1 != git_blob_sha1(candidate_bytes):
        raise ValueError("successor release is not bound to the exact candidate Git blob")
    if release.translation_ledger_digest != sha256_bytes(ledger_bytes):
        raise ValueError("successor release is not bound to the exact translation ledger")

    corpus = load_successor_corpus(candidate_path, translation_ledger_path)
    if release.normalized_corpus_digest != corpus.digest:
        raise ValueError("successor release digest does not match the normalized reviewed corpus")
    if release.predecessor_queue_digest != corpus.predecessor_queue_digest:
        raise ValueError("successor release predecessor binding differs from corpus")
    return release
