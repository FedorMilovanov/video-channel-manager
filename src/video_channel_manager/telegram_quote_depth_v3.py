from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import (
    CHANNEL_USERNAME,
    PROJECT_KEY,
    SHA256_PATTERN,
    LedgerEntry,
    TelegramLedger,
    canonical_json,
    sha256_text,
)
from video_channel_manager.telegram_presentation import load_presentation_policy
from video_channel_manager.telegram_quote_depth import DEPTH_QUEUE_DIGEST, build_depth_runtime_queue
from video_channel_manager.telegram_quote_quality_v4 import semantic_blocks
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimePost
from video_channel_manager.telegram_quote_successor import LEGACY_QUEUE_DIGEST

DEPTH_V3_RELEASE_ID = "lordchrist-successor-depth-v3"
DEPTH_V3_QUEUE_DIGEST = "sha256:962ccf972de0b3205da26ffd28adedfebf1822f1b3267b0c7ba316cc16d8ee37"
DEPTH_V3_AMENDMENTS_FILENAME = "successor-depth-v3-context-amendments-v1.json"
DEPTH_V3_RELEASE_FILENAME = "successor-depth-v3-release-v1.json"
DEPTH_V3_POLICY_FILENAME = "presentation-policy-v4.json"
PUBLISHED_BOUNDARY = 15
TOTAL_POSTS = 60


class ContextAmendment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=16, le=60)
    parent_publication_id: str = Field(pattern=r"^lordchrist-successor-depth-v2-[a-z0-9-]+$")
    source_url: str = Field(pattern=r"^https://")
    source_location: str = Field(min_length=12, max_length=300)
    source_exact_fragment: str = Field(min_length=40, max_length=1500)
    source_fragment_sha256: str = Field(pattern=SHA256_PATTERN)
    quote_ru: str = Field(min_length=20, max_length=1800)
    translation_note: str = Field(min_length=80, max_length=800)
    translation_binding_sha256: str = Field(pattern=SHA256_PATTERN)
    checked_on: date
    review_state: Literal["reviewed"]

    @model_validator(mode="after")
    def verify_hashes(self) -> "ContextAmendment":
        if self.source_fragment_sha256 != sha256_text(self.source_exact_fragment):
            raise ValueError("context amendment source fragment hash mismatch")
        binding = sha256_text(
            canonical_json(
                {
                    "source_exact_fragment": self.source_exact_fragment,
                    "quote_ru": self.quote_ru,
                    "translation_note": self.translation_note,
                }
            )
        )
        if self.translation_binding_sha256 != binding:
            raise ValueError("context amendment translation binding mismatch")
        return self


class ContextAmendmentRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-v3-context-amendments"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v3"]
    parent_queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    review_state: Literal["source_verified"]
    entries: tuple[ContextAmendment, ...]

    @model_validator(mode="after")
    def exact_inventory(self) -> "ContextAmendmentRegistry":
        if self.parent_queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("depth-v3 amendments must bind to exact depth-v2 queue")
        if tuple(entry.sequence for entry in self.entries) != (17, 32):
            raise ValueError("depth-v3 context repair must contain exactly sequences 17 and 32")
        if len({entry.parent_publication_id for entry in self.entries}) != len(self.entries):
            raise ValueError("depth-v3 context repair parent publication IDs must be unique")
        return self


class DepthV3Release(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-v3-release"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v3"]
    parent_release_id: Literal["lordchrist-successor-depth-v2"]
    parent_queue_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    pending_suffix: Literal[45]
    amended_sequences: tuple[int, ...]
    presentation_policy_id: Literal["lordchrist-quote-v4"]
    presentation_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    normalized_queue_digest: str = Field(pattern=SHA256_PATTERN)
    release_state: Literal["staged_provider_inert"]
    provider_writes_authorized: Literal[False]
    migration_policy: Literal["copy_verified_prefix_rekey_pristine_suffix"]

    @model_validator(mode="after")
    def exact_boundary(self) -> "DepthV3Release":
        if self.parent_queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("depth-v3 release must bind to exact depth-v2 queue")
        if self.amended_sequences != (17, 32):
            raise ValueError("depth-v3 release must amend exactly sequences 17 and 32")
        if self.normalized_queue_digest != DEPTH_V3_QUEUE_DIGEST:
            raise ValueError("depth-v3 release queue digest differs from reviewed identity")
        return self


class DepthV3RuntimeQueue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-v3-runtime-queue"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v3"]
    predecessor_queue_digest: str = Field(pattern=SHA256_PATTERN)
    parent_queue_digest: str = Field(pattern=SHA256_PATTERN)
    normalized_corpus_digest: str = Field(pattern=SHA256_PATTERN)
    published_boundary: Literal[15]
    posts: tuple[SuccessorRuntimePost, ...]

    @model_validator(mode="after")
    def exact_inventory(self) -> "DepthV3RuntimeQueue":
        if self.predecessor_queue_digest != LEGACY_QUEUE_DIGEST:
            raise ValueError("depth-v3 predecessor lineage changed")
        if self.parent_queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("depth-v3 parent queue differs from sealed depth-v2")
        if self.normalized_corpus_digest != DEPTH_V3_QUEUE_DIGEST:
            raise ValueError("depth-v3 normalized digest mismatch")
        if len(self.posts) != TOTAL_POSTS:
            raise ValueError("depth-v3 runtime must contain exactly 60 posts")
        if [post.sequence for post in self.posts] != list(range(1, TOTAL_POSTS + 1)):
            raise ValueError("depth-v3 runtime sequences must be exactly 1..60")
        ids = [post.publication_id for post in self.posts]
        if len(ids) != len(set(ids)):
            raise ValueError("depth-v3 runtime publication IDs must be unique")
        return self

    @property
    def digest(self) -> str:
        return self.normalized_corpus_digest


def _load(path: Path, model: type[BaseModel], label: str) -> BaseModel:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist {label} {path}: {exc}") from exc


def load_context_amendments(path: Path) -> ContextAmendmentRegistry:
    return ContextAmendmentRegistry.model_validate(_load(path, ContextAmendmentRegistry, "depth-v3 amendments"))


def load_depth_v3_release(path: Path) -> DepthV3Release:
    return DepthV3Release.model_validate(_load(path, DepthV3Release, "depth-v3 release"))


def _release_identity(registry: ContextAmendmentRegistry, release: DepthV3Release) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "parent_queue_digest": release.parent_queue_digest,
        "published_boundary": release.published_boundary,
        "presentation_policy_id": release.presentation_policy_id,
        "presentation_policy_sha256": release.presentation_policy_sha256,
        "amendments": [
            {
                "sequence": entry.sequence,
                "parent_publication_id": entry.parent_publication_id,
                "source_fragment_sha256": entry.source_fragment_sha256,
                "translation_binding_sha256": entry.translation_binding_sha256,
            }
            for entry in registry.entries
        ],
    }


def _v3_publication_id(parent: SuccessorRuntimePost) -> str:
    marker = f"lordchrist-successor-depth-v2-{parent.sequence:02d}-"
    if not parent.publication_id.startswith(marker):
        raise ValueError(f"depth-v3 pending parent is not release-scoped: {parent.publication_id}")
    return f"lordchrist-successor-depth-v3-{parent.sequence:02d}-{parent.publication_id.removeprefix(marker)}"


def _v3_payload_sha256(
    *,
    parent: SuccessorRuntimePost,
    publication_id: str,
    quote_ru: str,
    context_ru: str,
    hashtags: str,
    amendment: ContextAmendment | None,
) -> str:
    return sha256_text(
        canonical_json(
            {
                "release_id": DEPTH_V3_RELEASE_ID,
                "parent_queue_digest": DEPTH_QUEUE_DIGEST,
                "parent_publication_id": parent.publication_id,
                "parent_payload_sha256": parent.payload_sha256,
                "publication_id": publication_id,
                "source_sequence": parent.source_sequence,
                "quote_ru": quote_ru,
                "editorial_context_ru": context_ru,
                "attribution": {"author": parent.source.author, "work": parent.source.work},
                "hashtags": hashtags.split(),
                "context_amendment_binding_sha256": amendment.translation_binding_sha256 if amendment else None,
            }
        )
    )


def build_depth_v3_runtime_queue(
    *,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    amendments_path: Path | None = None,
    release_path: Path | None = None,
    policy_path: Path | None = None,
) -> DepthV3RuntimeQueue:
    parent = build_depth_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
    )
    if parent.digest != DEPTH_QUEUE_DIGEST:
        raise ValueError("depth-v3 builder requires exact sealed depth-v2 parent queue")

    amendments_path = amendments_path or candidate_path.with_name(DEPTH_V3_AMENDMENTS_FILENAME)
    release_path = release_path or candidate_path.with_name(DEPTH_V3_RELEASE_FILENAME)
    policy_path = policy_path or candidate_path.with_name(DEPTH_V3_POLICY_FILENAME)
    registry = load_context_amendments(amendments_path)
    release = load_depth_v3_release(release_path)
    policy = load_presentation_policy(policy_path)

    if release.presentation_policy_id != policy.policy_id or release.presentation_policy_sha256 != policy.digest:
        raise ValueError("depth-v3 release presentation identity differs from quote-v4 policy")
    if sha256_text(canonical_json(_release_identity(registry, release))) != release.normalized_queue_digest:
        raise ValueError("depth-v3 release identity digest mismatch")

    amendment_by_sequence = {entry.sequence: entry for entry in registry.entries}
    posts: list[SuccessorRuntimePost] = []
    for parent_post in parent.posts:
        if parent_post.sequence <= PUBLISHED_BOUNDARY:
            posts.append(parent_post.model_copy(deep=True))
            continue

        quote, attribution, context, hashtags = semantic_blocks(parent_post)
        amendment = amendment_by_sequence.get(parent_post.sequence)
        if amendment is not None:
            if amendment.parent_publication_id != parent_post.publication_id:
                raise ValueError(f"depth-v3 amendment parent mismatch at sequence {parent_post.sequence}")
            quote = amendment.quote_ru
        publication_id = _v3_publication_id(parent_post)
        text = "\n\n".join([quote, attribution, context, hashtags])
        posts.append(
            SuccessorRuntimePost(
                sequence=parent_post.sequence,
                publication_id=publication_id,
                title=parent_post.title,
                text=text,
                source=parent_post.source,
                source_sequence=parent_post.source_sequence,
                source_payload_sha256=_v3_payload_sha256(
                    parent=parent_post,
                    publication_id=publication_id,
                    quote_ru=quote,
                    context_ru=context,
                    hashtags=hashtags,
                    amendment=amendment,
                ),
            )
        )

    return DepthV3RuntimeQueue(
        schema_name="video-channel-manager.telegram-successor-depth-v3-runtime-queue",
        schema_version=1,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        release_id=DEPTH_V3_RELEASE_ID,
        predecessor_queue_digest=LEGACY_QUEUE_DIGEST,
        parent_queue_digest=DEPTH_QUEUE_DIGEST,
        normalized_corpus_digest=release.normalized_queue_digest,
        published_boundary=PUBLISHED_BOUNDARY,
        posts=tuple(posts),
    )


def migrate_depth_v3_ledger(
    *,
    parent_queue: object,
    parent_ledger: TelegramLedger,
    depth_v3_queue: DepthV3RuntimeQueue,
) -> TelegramLedger:
    if getattr(parent_queue, "digest", None) != DEPTH_QUEUE_DIGEST or parent_ledger.queue_digest != DEPTH_QUEUE_DIGEST:
        raise ValueError("depth-v3 state migration requires exact depth-v2 queue and ledger")
    parent_posts = tuple(getattr(parent_queue, "posts", ()))
    if len(parent_posts) != TOTAL_POSTS:
        raise ValueError("depth-v3 state migration requires all 60 depth-v2 posts")

    entries: dict[str, LedgerEntry] = {}
    for parent_post, next_post in zip(parent_posts, depth_v3_queue.posts, strict=True):
        current = parent_ledger.entries[parent_post.publication_id]
        if parent_post.sequence <= PUBLISHED_BOUNDARY:
            if next_post.publication_id != parent_post.publication_id or next_post.payload_sha256 != parent_post.payload_sha256:
                raise ValueError("depth-v3 must copy published prefix without content or identity changes")
            if current.state != "published" or current.provider_effect != "verified" or current.message_id is None:
                raise ValueError(f"depth-v3 published prefix is not provider-verified: {parent_post.publication_id}")
            entries[next_post.publication_id] = current.model_copy(deep=True)
            continue

        if (
            current.state != "pending"
            or current.provider_effect not in {"impossible", "not_dispatched", "confirmed_absent"}
            or current.intent_id is not None
            or current.message_id is not None
        ):
            raise ValueError(f"depth-v3 future suffix is not pristine: {parent_post.publication_id}")
        entries[next_post.publication_id] = LedgerEntry(
            publication_id=next_post.publication_id,
            payload_sha256=next_post.payload_sha256,
        )

    return TelegramLedger(
        schema_name="video-channel-manager.telegram-publication-ledger",
        schema_version=3,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        queue_digest=depth_v3_queue.digest,
        entries=entries,
    )


def describe_release(queue: DepthV3RuntimeQueue) -> str:
    return json.dumps(
        {
            "release_id": queue.release_id,
            "queue_digest": queue.digest,
            "published_boundary": queue.published_boundary,
            "published_immutable": queue.published_boundary,
            "pending_rekeyed": TOTAL_POSTS - queue.published_boundary,
            "amended_sequences": [17, 32],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
