from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from video_channel_manager.telegram_models import (
    CHANNEL_USERNAME,
    PROJECT_KEY,
    SHA256_PATTERN,
    LedgerEntry,
    TelegramLedger,
    canonical_json,
    sha256_text,
)
from video_channel_manager.telegram_publisher import load_ledger, save_ledger
from video_channel_manager.telegram_quote_runtime import (
    RuntimeSourceIdentity,
    SUCCESSOR_RUNTIME_SCHEMA,
    SUCCESSOR_RUNTIME_SCHEMA_VERSION,
    SuccessorRuntimePost,
    SuccessorRuntimeQueue,
    predecessor_is_complete,
)
from video_channel_manager.telegram_quote_successor import (
    LEGACY_QUEUE_DIGEST,
    RawSuccessorSourceProof,
    SuccessorQuoteCard,
    git_blob_sha1,
    load_successor_corpus,
)
from video_channel_manager.telegram_state import load_queue as load_predecessor_queue
from video_channel_manager.telegram_successor_editorial import (
    SUCCESSOR_EDITORIAL_FILENAME,
    resolve_successor_editorial_contexts,
)

DEPTH_AUDIT_FILENAME = "quote-depth-audit-v1.json"
DEPTH_REPLACEMENTS_FILENAME = "quote-depth-replacements-v1.json"
DEPTH_RELEASE_FILENAME = "successor-depth-release-v1.json"
DEPTH_ACTIVATION_FILENAME = "successor-depth-activation-v1.json"
DEPTH_PRESENTATION_FILENAME = "presentation-policy-v3.json"
DEPTH_RESTORE_FILENAME = "successor-depth-restore-v1.json"
DEPTH_RELEASE_ID = "lordchrist-successor-depth-v2"
DEPTH_V3_RELEASE_ID = "lordchrist-successor-depth-v3"
DEPTH_QUEUE_DIGEST = "sha256:c2ad28bb96e88a9e0633c4b7a55d6033bbf29c5a557e1aa4478cc2e0359e3441"
DEPTH_V3_QUEUE_DIGEST = "sha256:8d7dfd231908855894412b780a6c7a73840420ae03d931a0bfb49bac4e292913"
SOURCE_V1_QUEUE_DIGEST = "sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"
AUDIT_HISTORY_PREFIX = 10
REVIEWED_TOTAL = 60
REPLACEMENT_POOL_COUNT = 21
DEPTH_LEDGER_RELATIVE_PATH = "content/telegram/lordchrist/successor-depth-v2-publication-ledger.json"
DEPTH_V3_LEDGER_RELATIVE_PATH = "content/telegram/lordchrist/successor-depth-v3-publication-ledger.json"
V3_HANDOFF_PUBLISHED_PREFIX = 17
RESTORE_SEQUENCES = (32, 36)
ATTRIBUTION_QUOTED_RE = re.compile(r"^(?P<author>.+?),\s*«(?P<work>[^»]+)»(?P<suffix>.*)$")

# The depth-v3 restore standard: a reader-facing quotation must never open on a
# pronoun or demonstrative whose antecedent lives in the omitted source context.
# The quote-v4 era proved that a visible title cannot repair such an opening.
RESTORE_FORBIDDEN_OPENINGS = frozenset(
    {"они", "он", "она", "оно", "его", "её", "их", "этот", "эта", "это", "эти", "этих", "те", "всё", "все"}
)


class DepthAuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=REVIEWED_TOTAL)
    publication_id: str = Field(pattern=r"^lordchrist-successor-[a-z0-9][a-z0-9-]{4,90}$")
    verdict: Literal["history_locked", "keep", "replace"]
    score_10: int = Field(ge=1, le=10)
    rationale_ru: str = Field(min_length=20, max_length=1000)
    replacement_key: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{5,100}$")

    @model_validator(mode="after")
    def replacement_binding(self) -> "DepthAuditEntry":
        if self.verdict == "replace" and self.replacement_key is None:
            raise ValueError("replacement verdict requires replacement_key")
        if self.verdict != "replace" and self.replacement_key is not None:
            raise ValueError("only replacement verdicts may carry replacement_key")
        return self


class DepthAuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    history_locked: Literal[10]
    future_keep: Literal[29]
    future_replace: Literal[21]
    audited_total: Literal[60]


class DepthAudit(BaseModel):
    """Immutable audit snapshot.

    The audit happened when only sequences 1..10 were published. Later handoff
    boundaries are release metadata, never retroactive edits to this evidence.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-audit"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    source_corpus_id: Literal["lordchrist-successor-quotes-v1"]
    owning_issue: Literal[667]
    summary: DepthAuditSummary
    entries: tuple[DepthAuditEntry, ...]

    @model_validator(mode="after")
    def exact_inventory(self) -> "DepthAudit":
        if len(self.entries) != REVIEWED_TOTAL:
            raise ValueError("depth audit must cover exactly 60 source successor cards")
        if [entry.sequence for entry in self.entries] != list(range(1, REVIEWED_TOTAL + 1)):
            raise ValueError("depth audit must cover source successor sequences 1..60 exactly")
        if any(entry.verdict != "history_locked" for entry in self.entries[:AUDIT_HISTORY_PREFIX]):
            raise ValueError("depth audit must preserve its original 10-card history snapshot")
        audited_future = self.entries[AUDIT_HISTORY_PREFIX:]
        if sum(entry.verdict == "keep" for entry in audited_future) != self.summary.future_keep:
            raise ValueError("depth audit keep count differs from its immutable summary")
        if sum(entry.verdict == "replace" for entry in audited_future) != self.summary.future_replace:
            raise ValueError("depth audit replacement count differs from its immutable summary")
        return self


class DepthReplacementEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    replacement_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{5,100}$")
    title: str = Field(min_length=2, max_length=160)
    theme: str = Field(min_length=2, max_length=80)
    quote_ru: str = Field(min_length=10, max_length=1800)
    editorial_context_ru: str = Field(min_length=80, max_length=1800)
    attribution_ru: str = Field(min_length=4, max_length=260)
    hashtags: tuple[str, ...]
    source: RawSuccessorSourceProof

    @field_validator("hashtags")
    @classmethod
    def compact_hashtags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 2 <= len(value) <= 6 or len(value) != len(set(value)):
            raise ValueError("depth replacement requires 2..6 unique hashtags")
        if any(not tag.startswith("#") or any(ch.isspace() for ch in tag) for tag in value):
            raise ValueError("depth replacement hashtags must be compact #tokens")
        return value

    @model_validator(mode="after")
    def exact_quote_boundary(self) -> "DepthReplacementEntry":
        if self.editorial_context_ru.casefold().startswith("пояснение:"):
            raise ValueError("replacement editorial context must not embed a presentation label")
        if "© " in self.editorial_context_ru:
            raise ValueError("replacement editorial context must not embed attribution presentation")
        if self.source.rights_class == "modern_short_quote_editorial_context":
            words = re.findall(r"\b[\w’'-]+\b", self.quote_ru, flags=re.UNICODE)
            if len(words) > 25:
                raise ValueError("modern visible Russian replacement quotation exceeds 25 words")
        return self


class DepthReplacementRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-replacements"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    owning_issue: Literal[667]
    review_state: Literal["source_verified"]
    entries: tuple[DepthReplacementEntry, ...]

    @model_validator(mode="after")
    def exact_inventory(self) -> "DepthReplacementRegistry":
        if len(self.entries) != REPLACEMENT_POOL_COUNT:
            raise ValueError("depth replacement registry must preserve all 21 reviewed candidates")
        keys = [entry.replacement_key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("depth replacement keys must be unique")
        fragments = [sha256_text(entry.source.exact_fragment) for entry in self.entries]
        if len(fragments) != len(set(fragments)):
            raise ValueError("depth replacement source fragments must be unique")
        return self


class DepthRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-release"]
    schema_version: Literal[2]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v2"]
    owning_issue: Literal[667]
    source_v1_queue_digest: Literal["sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"]
    audit_git_blob_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")
    replacements_git_blob_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")
    transition_identity: str = Field(pattern=r"^after_v1_exactly_[0-9]+_published_[0-9]+_pending$")
    normalized_queue_digest: str = Field(pattern=SHA256_PATTERN)
    audit_history_locked_count: Literal[10]
    handoff_published_prefix: int = Field(ge=AUDIT_HISTORY_PREFIX, le=REVIEWED_TOTAL)
    future_post_count: int = Field(ge=0, le=REVIEWED_TOTAL)
    future_keep_count: int = Field(ge=0, le=REVIEWED_TOTAL)
    future_replace_count: int = Field(ge=0, le=REVIEWED_TOTAL)
    replacement_pool_count: Literal[21]
    superseded_replacement_count: int = Field(ge=0, le=21)
    release_state: Literal["staged_provider_inert"]
    provider_writes_authorized: Literal[False]

    @model_validator(mode="after")
    def migration_counts(self) -> "DepthRelease":
        expected_future = REVIEWED_TOTAL - self.handoff_published_prefix
        if self.future_post_count != expected_future:
            raise ValueError("depth release future count does not match its handoff prefix")
        if self.future_keep_count + self.future_replace_count != self.future_post_count:
            raise ValueError("depth release future keep/replace counts do not cover the future suffix")
        expected_transition = (
            f"after_v1_exactly_{self.handoff_published_prefix}_published_{self.future_post_count}_pending"
        )
        if self.transition_identity != expected_transition:
            raise ValueError("depth release transition identity does not match migration counts")
        return self


class DepthActivation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-activation"]
    schema_version: Literal[2]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v2"]
    owning_issue: Literal[667]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    source_v1_queue_digest: Literal["sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"]
    activation_policy: Literal["exact_published_prefix_and_pristine_suffix"]
    required_published_prefix: int = Field(ge=AUDIT_HISTORY_PREFIX, le=REVIEWED_TOTAL)
    required_pending_suffix: int = Field(ge=0, le=REVIEWED_TOTAL)
    presentation_policy_id: Literal["lordchrist-quote-v3"]
    presentation_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    state_ledger_relative_path: Literal["content/telegram/lordchrist/successor-depth-v2-publication-ledger.json"]
    provider_writes_authorized: bool

    @model_validator(mode="after")
    def exact_boundary(self) -> "DepthActivation":
        if self.required_published_prefix + self.required_pending_suffix != REVIEWED_TOTAL:
            raise ValueError("depth activation handoff must cover all 60 source slots")
        return self


class DepthRestoreEntry(BaseModel):
    """One pending slot restored to the complete source-v1 quotation.

    The depth-v2 translation pass replaced the original referent-naming
    translation with a literal ``exact_fragment_only`` rendering that opens on
    an unresolved anaphora. The restore binds the complete first sentence of
    the *sealed source-v1 corpus translation* verbatim, so no new translation
    is introduced: the reader-facing text returns to already-reviewed bytes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=18, le=60)
    publication_id: str = Field(pattern=r"^lordchrist-successor-depth-v2-[a-z0-9-]{4,100}$")
    base_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    restored_quote_ru: str = Field(min_length=40, max_length=1800)
    source_fragment_sha256: str = Field(pattern=SHA256_PATTERN)
    rationale_ru: str = Field(min_length=80, max_length=900)

    @model_validator(mode="after")
    def complete_opening(self) -> "DepthRestoreEntry":
        from video_channel_manager.telegram_presentation import _require_standalone_quotation

        quote = " ".join(self.restored_quote_ru.strip().split())
        if quote != self.restored_quote_ru:
            raise ValueError("restored quotation must be a normalized single-line sentence")
        _require_standalone_quotation(quote)
        first_word = quote.split(" ", 1)[0].rstrip(",;:").casefold()
        if first_word in RESTORE_FORBIDDEN_OPENINGS:
            raise ValueError(
                "restored quotation must name its own subject instead of opening on an unresolved reference"
            )
        return self


class DepthRestoreRelease(BaseModel):
    """Reader-driven restore release layered over the sealed depth-v2 queue.

    Sequence 17 was published under quote-v4 on 2026-10-17 (durable message
    1567) and is immutable history, so the restore covers only the two pending
    anaphora-fragment slots that remain. Depth-v3 keeps every payload of the
    accepted 1-17 history and every other pending card byte-identical to
    depth-v2. The queue identity digest binds the base release plus the exact
    restore entries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-depth-restore"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-depth-v3"]
    owning_issue: int = Field(ge=1)
    base_release_id: Literal["lordchrist-successor-depth-v2"]
    base_queue_digest: str = Field(pattern=SHA256_PATTERN)
    handoff_published_prefix: Literal[17]
    normalized_queue_digest: str = Field(pattern=SHA256_PATTERN)
    release_state: Literal["staged_provider_inert"]
    provider_writes_authorized: Literal[False]
    reason: str = Field(min_length=120, max_length=1500)
    restores: tuple[DepthRestoreEntry, ...]

    @model_validator(mode="after")
    def exact_restore_inventory(self) -> "DepthRestoreRelease":
        if self.base_release_id != DEPTH_RELEASE_ID or self.base_queue_digest != DEPTH_QUEUE_DIGEST:
            raise ValueError("depth restore must layer over the exact sealed depth-v2 release")
        if self.normalized_queue_digest == self.base_queue_digest:
            raise ValueError("depth restore must change the queue identity digest")
        if tuple(entry.sequence for entry in self.restores) != RESTORE_SEQUENCES:
            raise ValueError("depth restore must cover exactly the reviewed pending anaphora slots 32 and 36")
        if min(RESTORE_SEQUENCES) <= self.handoff_published_prefix:
            raise ValueError("depth restore slots must stay strictly inside the pending suffix")
        return self


class DepthActiveSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-active-quote-selection"]
    schema_version: Literal[2]
    active_release: Literal["depth-v2", "depth-v3"]
    release_id: Literal["lordchrist-successor-depth-v2", "lordchrist-successor-depth-v3"]
    queue_path: str
    ledger_path: str
    ledger_relative_path: str
    base_release_id: Literal["lordchrist-successor-depth-v2"]
    base_ledger_path: str
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    predecessor_complete: Literal[True]
    needs_ledger_initialization: bool
    history_queue_path: str
    history_ledger_path: str
    source_v1_ledger_path: str
    provider_writes_authorized: bool


def _load_model(path: Path, model: type[BaseModel], label: str) -> BaseModel:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist {label} {path}: {exc}") from exc


def load_depth_audit(path: Path) -> DepthAudit:
    return DepthAudit.model_validate(_load_model(path, DepthAudit, "depth audit"))


def load_depth_replacements(path: Path) -> DepthReplacementRegistry:
    return DepthReplacementRegistry.model_validate(_load_model(path, DepthReplacementRegistry, "depth replacements"))


def load_depth_release(path: Path) -> DepthRelease:
    return DepthRelease.model_validate(_load_model(path, DepthRelease, "depth release"))


def load_depth_activation(path: Path) -> DepthActivation:
    return DepthActivation.model_validate(_load_model(path, DepthActivation, "depth activation"))


def load_depth_restore(path: Path) -> DepthRestoreRelease:
    return DepthRestoreRelease.model_validate(_load_model(path, DepthRestoreRelease, "depth restore release"))


def _presentation_identity(attribution_ru: str) -> RuntimeSourceIdentity:
    value = " ".join(attribution_ru.strip().split())
    quoted = ATTRIBUTION_QUOTED_RE.match(value)
    if quoted is not None:
        work = quoted.group("work").strip()
        suffix = quoted.group("suffix").strip().lstrip(",").strip()
        if suffix:
            work = f"{work}, {suffix}"
        return RuntimeSourceIdentity(author=quoted.group("author").strip(), work=work)
    if "," not in value:
        raise ValueError(f"depth attribution has no author/work separator: {attribution_ru}")
    author, work = value.split(",", 1)
    work = work.strip()
    if work.startswith("«") and work.endswith("»"):
        work = work[1:-1].strip()
    return RuntimeSourceIdentity(author=author.strip(), work=work)


def _render_legacy_text(
    *, quote_ru: str, context_ru: str, source: RuntimeSourceIdentity, hashtags: tuple[str, ...]
) -> str:
    """Reproduce already-published v1 runtime text only for immutable history."""
    return "\n\n".join(
        [
            quote_ru.strip(),
            f"Пояснение: {context_ru.strip()}",
            f"© {source.author}, «{source.work}»",
            " ".join(hashtags),
        ]
    )


def _render_depth_text(*, quote_ru: str, attribution_ru: str, context_ru: str, hashtags: tuple[str, ...]) -> str:
    """Canonical semantic text for the depth-v2 future suffix.

    Formatting belongs to telegram_presentation; this transport text contains no
    presentation labels and no copyright marker. The source line is the reviewed
    attribution verbatim: re-deriving it from the normalized evidence identity
    would nest quotation marks and silently drop reviewed wording.
    """
    quote = quote_ru.strip()
    context = context_ru.strip()
    attribution = " ".join(attribution_ru.strip().split())
    if "Пояснение:" in quote or "Пояснение:" in context or "© " in quote or "© " in context:
        raise ValueError("depth-v2 semantic text cannot contain legacy presentation labels")
    if "Пояснение:" in attribution or "© " in attribution:
        raise ValueError("depth-v2 reviewed attribution cannot contain legacy presentation labels")
    return "\n\n".join(
        [
            quote,
            f"— {attribution}",
            context,
            " ".join(hashtags),
        ]
    )


def _depth_publication_id(source_sequence: int, semantic_key: str) -> str:
    return f"lordchrist-successor-depth-v2-{source_sequence:02d}-{semantic_key}"


def _future_payload_sha256(
    *,
    publication_id: str,
    source_sequence: int,
    quote_ru: str,
    context_ru: str,
    attribution_ru: str,
    hashtags: tuple[str, ...],
    source: dict[str, object],
    provenance: dict[str, object],
) -> str:
    return sha256_text(
        canonical_json(
            {
                "publication_id": publication_id,
                "source_sequence": source_sequence,
                "quote_ru": quote_ru,
                "editorial_context_ru": context_ru,
                "attribution_ru": attribution_ru,
                "hashtags": list(hashtags),
                "source": source,
                "provenance": provenance,
            }
        )
    )


def _history_runtime_post(card: SuccessorQuoteCard, context_ru: str) -> SuccessorRuntimePost:
    source = _presentation_identity(card.attribution_ru)
    return SuccessorRuntimePost(
        sequence=card.sequence,
        publication_id=card.publication_id,
        title=card.title,
        text=_render_legacy_text(
            quote_ru=card.quote_ru,
            context_ru=context_ru,
            source=source,
            hashtags=card.hashtags,
        ),
        source=source,
        attribution_text=" ".join(card.attribution_ru.strip().split()),
        source_sequence=card.sequence,
        source_payload_sha256=card.payload_sha256,
    )


def _future_keep_runtime_post(card: SuccessorQuoteCard, context_ru: str) -> SuccessorRuntimePost:
    publication_id = _depth_publication_id(card.sequence, card.semantic_key)
    source = _presentation_identity(card.attribution_ru)
    payload_sha256 = _future_payload_sha256(
        publication_id=publication_id,
        source_sequence=card.sequence,
        quote_ru=card.quote_ru,
        context_ru=context_ru,
        attribution_ru=card.attribution_ru,
        hashtags=card.hashtags,
        source=card.source.model_dump(mode="json"),
        provenance={"verdict": "keep", "source_v1_publication_id": card.publication_id},
    )
    return SuccessorRuntimePost(
        sequence=card.sequence,
        publication_id=publication_id,
        title=card.title,
        text=_render_depth_text(
            quote_ru=card.quote_ru,
            attribution_ru=card.attribution_ru,
            context_ru=context_ru,
            hashtags=card.hashtags,
        ),
        source=source,
        attribution_text=card.attribution_ru,
        source_sequence=card.sequence,
        source_payload_sha256=payload_sha256,
    )


def _future_replacement_runtime_post(
    *, source_sequence: int, replacement: DepthReplacementEntry
) -> SuccessorRuntimePost:
    publication_id = _depth_publication_id(source_sequence, replacement.replacement_key)
    source = _presentation_identity(replacement.attribution_ru)
    payload_sha256 = _future_payload_sha256(
        publication_id=publication_id,
        source_sequence=source_sequence,
        quote_ru=replacement.quote_ru,
        context_ru=replacement.editorial_context_ru,
        attribution_ru=replacement.attribution_ru,
        hashtags=replacement.hashtags,
        source=replacement.source.model_dump(mode="json"),
        provenance={"verdict": "replace", "replacement_key": replacement.replacement_key},
    )
    return SuccessorRuntimePost(
        sequence=source_sequence,
        publication_id=publication_id,
        title=replacement.title,
        text=_render_depth_text(
            quote_ru=replacement.quote_ru,
            attribution_ru=replacement.attribution_ru,
            context_ru=replacement.editorial_context_ru,
            hashtags=replacement.hashtags,
        ),
        source=source,
        attribution_text=replacement.attribution_ru,
        source_sequence=source_sequence,
        source_payload_sha256=payload_sha256,
    )


def _verify_release_identity(
    *,
    source_digest: str,
    audit_path: Path,
    replacements_path: Path,
    release: DepthRelease,
    activation: DepthActivation,
) -> None:
    if source_digest != release.source_v1_queue_digest or source_digest != activation.source_v1_queue_digest:
        raise ValueError("depth-v2 source successor digest differs from the sealed v1 release")
    if git_blob_sha1(audit_path.read_bytes()) != release.audit_git_blob_sha1:
        raise ValueError("depth-v2 audit Git blob differs from the sealed release")
    if git_blob_sha1(replacements_path.read_bytes()) != release.replacements_git_blob_sha1:
        raise ValueError("depth-v2 replacement Git blob differs from the sealed release")
    identity = {
        "source_v1_digest": source_digest,
        "audit_git_blob_sha1": release.audit_git_blob_sha1,
        "replacements_git_blob_sha1": release.replacements_git_blob_sha1,
        "transition": release.transition_identity,
        "release_id": release.release_id,
    }
    if sha256_text(canonical_json(identity)) != release.normalized_queue_digest:
        raise ValueError("depth-v2 release identity digest mismatch")
    if activation.queue_digest != release.normalized_queue_digest or activation.release_id != release.release_id:
        raise ValueError("depth-v2 activation differs from the sealed release")
    if activation.required_published_prefix != release.handoff_published_prefix:
        raise ValueError("depth-v2 activation published prefix differs from the release")
    if activation.required_pending_suffix != release.future_post_count:
        raise ValueError("depth-v2 activation pending suffix differs from the release")

    from video_channel_manager.telegram_presentation import load_presentation_policy

    policy = load_presentation_policy(audit_path.with_name(DEPTH_PRESENTATION_FILENAME))
    if activation.presentation_policy_id != policy.policy_id:
        raise ValueError("depth-v2 activation presentation policy id differs from quote-v3")
    if activation.presentation_policy_sha256 != policy.digest:
        raise ValueError("depth-v2 activation presentation policy digest differs from quote-v3")


def _reviewed_partition(
    audit: DepthAudit,
    replacements: DepthReplacementRegistry,
    release: DepthRelease,
) -> tuple[dict[int, DepthAuditEntry], dict[str, DepthReplacementEntry]]:
    audit_by_sequence = {entry.sequence: entry for entry in audit.entries}
    replacements_by_key = {entry.replacement_key: entry for entry in replacements.entries}
    audited_replacement_keys = {
        entry.replacement_key
        for entry in audit.entries
        if entry.verdict == "replace" and entry.replacement_key is not None
    }
    if audited_replacement_keys != set(replacements_by_key):
        raise ValueError("depth-v2 audit replacement keys differ from the reviewed replacement registry")

    handoff = release.handoff_published_prefix
    future = audit.entries[handoff:]
    future_keep = sum(entry.verdict == "keep" for entry in future)
    future_replace = sum(entry.verdict == "replace" for entry in future)
    superseded = sum(entry.verdict == "replace" for entry in audit.entries[AUDIT_HISTORY_PREFIX:handoff])
    if future_keep != release.future_keep_count:
        raise ValueError("depth-v2 future keep count differs from the release")
    if future_replace != release.future_replace_count:
        raise ValueError("depth-v2 future replacement count differs from the release")
    if superseded != release.superseded_replacement_count:
        raise ValueError("depth-v2 superseded replacement count differs from published history")
    if future_replace + superseded != REPLACEMENT_POOL_COUNT:
        raise ValueError("every reviewed replacement must be selected or explicitly superseded by published history")
    return audit_by_sequence, replacements_by_key


def build_depth_runtime_queue(
    *,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    audit_path: Path | None = None,
    replacements_path: Path | None = None,
    release_path: Path | None = None,
    activation_path: Path | None = None,
) -> SuccessorRuntimeQueue:
    audit_path = audit_path or candidate_path.with_name(DEPTH_AUDIT_FILENAME)
    replacements_path = replacements_path or candidate_path.with_name(DEPTH_REPLACEMENTS_FILENAME)
    release_path = release_path or candidate_path.with_name(DEPTH_RELEASE_FILENAME)
    activation_path = activation_path or candidate_path.with_name(DEPTH_ACTIVATION_FILENAME)

    corpus = load_successor_corpus(candidate_path, translation_ledger_path, integrity_amendment_path)
    if corpus.digest != SOURCE_V1_QUEUE_DIGEST:
        raise ValueError("depth-v2 builder requires the exact sealed source-v1 corpus")
    audit = load_depth_audit(audit_path)
    replacements = load_depth_replacements(replacements_path)
    release = load_depth_release(release_path)
    activation = load_depth_activation(activation_path)
    _verify_release_identity(
        source_digest=corpus.digest,
        audit_path=audit_path,
        replacements_path=replacements_path,
        release=release,
        activation=activation,
    )
    audit_by_sequence, replacements_by_key = _reviewed_partition(audit, replacements, release)

    cards_by_sequence = {card.sequence: card for card in corpus.posts}
    contexts = resolve_successor_editorial_contexts(
        corpus,
        candidate_path.with_name(SUCCESSOR_EDITORIAL_FILENAME),
    )
    posts: list[SuccessorRuntimePost] = []
    themes: list[str] = []
    handoff = release.handoff_published_prefix
    for sequence in range(1, REVIEWED_TOTAL + 1):
        card = cards_by_sequence[sequence]
        verdict = audit_by_sequence[sequence]
        if verdict.publication_id != card.publication_id:
            raise ValueError(f"depth-v2 audit publication mismatch at source sequence {sequence}")
        if sequence <= handoff:
            posts.append(_history_runtime_post(card, contexts[card.publication_id]))
            continue
        if verdict.verdict == "keep":
            posts.append(_future_keep_runtime_post(card, contexts[card.publication_id]))
            themes.append(card.theme)
            continue
        if verdict.verdict != "replace" or verdict.replacement_key is None:
            raise ValueError(f"depth-v2 future source sequence {sequence} is neither keep nor replace")
        replacement = replacements_by_key[verdict.replacement_key]
        posts.append(_future_replacement_runtime_post(source_sequence=sequence, replacement=replacement))
        themes.append(replacement.theme)

    if len(posts) != REVIEWED_TOTAL:
        raise ValueError("depth-v2 runtime must preserve all 60 positional slots")
    future_ids = [post.publication_id for post in posts[handoff:]]
    if len(future_ids) != release.future_post_count or len(future_ids) != len(set(future_ids)):
        raise ValueError("depth-v2 future publication IDs must exactly match the reviewed future suffix")
    if any(not publication_id.startswith("lordchrist-successor-depth-v2-") for publication_id in future_ids):
        raise ValueError("depth-v2 future publication IDs must be release-scoped")
    theme_counts = {theme: themes.count(theme) for theme in set(themes)}
    if len(theme_counts) != 12:
        raise ValueError("depth-v2 future corpus must deliberately cover all 12 theological themes")
    if max(theme_counts.values()) > 8:
        raise ValueError("depth-v2 future corpus is too concentrated in one theological theme")

    return SuccessorRuntimeQueue(
        schema_name=SUCCESSOR_RUNTIME_SCHEMA,
        schema_version=SUCCESSOR_RUNTIME_SCHEMA_VERSION,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        release_id=DEPTH_RELEASE_ID,
        predecessor_queue_digest=LEGACY_QUEUE_DIGEST,
        normalized_corpus_digest=release.normalized_queue_digest,
        posts=tuple(posts),
    )


def _raw_source_first_sentence(candidate_path: Path, sequence: int) -> tuple[str, str]:
    """Return the first sentence and exact fragment of the sealed raw source-v1 card."""

    try:
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid successor source corpus {candidate_path}: {exc}") from exc
    posts = payload.get("posts") if isinstance(payload, dict) else None
    if not isinstance(posts, list):
        raise ValueError("successor source corpus has no posts")
    for card in posts:
        if isinstance(card, dict) and card.get("sequence") == sequence:
            quote = str(card.get("quote_ru", "")).strip()
            source = card.get("source")
            fragment = str(source.get("exact_fragment", "")) if isinstance(source, dict) else ""
            if not quote or not fragment:
                raise ValueError(f"raw source card {sequence} lacks the quotation or the exact fragment")
            boundary = quote.find(". ")
            return (quote if boundary == -1 else quote[: boundary + 1]), fragment
    raise ValueError(f"raw source corpus has no card for sequence {sequence}")


def build_depth_v3_runtime_queue(
    *,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    restore_path: Path | None = None,
) -> SuccessorRuntimeQueue:
    """Build the depth-v3 restore queue over the sealed depth-v2 runtime.

    Only the reviewed anaphora slots are restored, each to the verbatim first
    sentence of the sealed source-v1 translation. Everything else — including
    the whole accepted published history — stays byte-identical to depth-v2.
    """

    restore_path = restore_path or candidate_path.with_name(DEPTH_RESTORE_FILENAME)
    base = build_depth_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
    )
    restore = load_depth_restore(restore_path)
    identity = {
        "release_id": restore.release_id,
        "base_release_id": restore.base_release_id,
        "base_queue_digest": restore.base_queue_digest,
        "restores": [entry.model_dump(mode="json") for entry in restore.restores],
    }
    if sha256_text(canonical_json(identity)) != restore.normalized_queue_digest:
        raise ValueError("depth-v3 restore identity digest mismatch")
    if restore.normalized_queue_digest != DEPTH_V3_QUEUE_DIGEST:
        raise ValueError("depth-v3 restore differs from the reviewed restore release identity")

    restore_by_sequence = {entry.sequence: entry for entry in restore.restores}
    posts: list[SuccessorRuntimePost] = []
    for post in base.posts:
        entry = restore_by_sequence.get(post.sequence)
        if entry is None:
            posts.append(post)
            continue
        if entry.publication_id != post.publication_id or entry.base_payload_sha256 != post.payload_sha256:
            raise ValueError(f"depth-v3 restore base payload drifted for sequence {post.sequence}")
        first_sentence, fragment = _raw_source_first_sentence(candidate_path, post.source_sequence)
        if entry.restored_quote_ru != first_sentence:
            raise ValueError(
                f"depth-v3 restore must quote the sealed source first sentence verbatim: {post.publication_id}"
            )
        if entry.source_fragment_sha256 != sha256_text(fragment):
            raise ValueError(f"depth-v3 restore fragment binding differs for sequence {post.sequence}")

        blocks = post.text.split("\n\n")
        hashtags = tuple(blocks[-1].split())
        context = "\n\n".join(blocks[2:-1])
        payload_sha256 = _future_payload_sha256(
            publication_id=post.publication_id,
            source_sequence=post.source_sequence,
            quote_ru=entry.restored_quote_ru,
            context_ru=context,
            attribution_ru=post.attribution_text,
            hashtags=hashtags,
            source=post.source.model_dump(mode="json"),
            provenance={
                "verdict": "depth_v3_restore",
                "base_payload_sha256": entry.base_payload_sha256,
                "restored_from": "source_v1_original_translation_first_sentence",
                "source_fragment_sha256": entry.source_fragment_sha256,
            },
        )
        posts.append(
            SuccessorRuntimePost(
                sequence=post.sequence,
                publication_id=post.publication_id,
                title=post.title,
                text=_render_depth_text(
                    quote_ru=entry.restored_quote_ru,
                    attribution_ru=post.attribution_text,
                    context_ru=context,
                    hashtags=hashtags,
                ),
                source=post.source,
                attribution_text=post.attribution_text,
                source_sequence=post.source_sequence,
                source_payload_sha256=payload_sha256,
            )
        )

    return SuccessorRuntimeQueue(
        schema_name=SUCCESSOR_RUNTIME_SCHEMA,
        schema_version=SUCCESSOR_RUNTIME_SCHEMA_VERSION,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        release_id=DEPTH_V3_RELEASE_ID,
        predecessor_queue_digest=LEGACY_QUEUE_DIGEST,
        normalized_corpus_digest=restore.normalized_queue_digest,
        posts=tuple(posts),
    )


def require_exact_depth_v2_handoff(
    depth_v2_queue: SuccessorRuntimeQueue,
    depth_v2_ledger: TelegramLedger,
    *,
    published_prefix: int,
) -> None:
    if depth_v2_queue.digest != DEPTH_QUEUE_DIGEST or depth_v2_ledger.queue_digest != DEPTH_QUEUE_DIGEST:
        raise ValueError("depth-v3 handoff requires the exact sealed depth-v2 queue and ledger")
    if not V3_HANDOFF_PUBLISHED_PREFIX <= published_prefix <= REVIEWED_TOTAL:
        raise ValueError("depth-v3 handoff prefix is outside the sealed depth-v2 release")

    for post in depth_v2_queue.posts[:published_prefix]:
        entry = depth_v2_ledger.entries[post.publication_id]
        if entry.state != "published" or entry.provider_effect != "verified" or not entry.message_id:
            raise ValueError(f"depth-v3 handoff requires verified depth-v2 history: {post.publication_id}")
    for post in depth_v2_queue.posts[published_prefix:]:
        entry = depth_v2_ledger.entries[post.publication_id]
        if (
            entry.state != "pending"
            or entry.provider_effect != "impossible"
            or entry.intent_id is not None
            or entry.attempted_at_utc is not None
            or entry.message_id is not None
        ):
            raise ValueError(f"depth-v3 handoff requires pristine unpublished suffix: {post.publication_id}")


def initialize_depth_v3_ledger(
    *,
    path: Path,
    depth_v3_queue: SuccessorRuntimeQueue,
    depth_v2_queue: SuccessorRuntimeQueue,
    depth_v2_ledger: TelegramLedger,
    restore: DepthRestoreRelease,
) -> TelegramLedger:
    if path.exists():
        raise ValueError(f"refusing to overwrite existing depth-v3 ledger: {path}")
    if depth_v3_queue.digest != DEPTH_V3_QUEUE_DIGEST or restore.normalized_queue_digest != DEPTH_V3_QUEUE_DIGEST:
        raise ValueError("depth-v3 ledger initialization requires the sealed depth-v3 restore queue")
    handoff = restore.handoff_published_prefix
    require_exact_depth_v2_handoff(depth_v2_queue, depth_v2_ledger, published_prefix=handoff)

    entries: dict[str, LedgerEntry] = {}
    for post in depth_v3_queue.posts[:handoff]:
        historical = depth_v2_ledger.entries[post.publication_id].model_copy(deep=True)
        if historical.payload_sha256 != post.payload_sha256:
            raise ValueError(f"depth-v3 locked history payload differs for {post.publication_id}")
        entries[post.publication_id] = historical
    for post in depth_v3_queue.posts[handoff:]:
        entries[post.publication_id] = LedgerEntry(
            publication_id=post.publication_id,
            payload_sha256=post.payload_sha256,
        )

    ledger = TelegramLedger(
        schema_name="video-channel-manager.telegram-publication-ledger",
        schema_version=3,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        queue_digest=depth_v3_queue.digest,
        entries=entries,
    )
    save_ledger(path, ledger)
    return ledger


def require_exact_v1_handoff(
    source_v1_queue: SuccessorRuntimeQueue,
    source_v1_ledger: TelegramLedger,
    *,
    published_prefix: int,
) -> None:
    if source_v1_queue.digest != SOURCE_V1_QUEUE_DIGEST or source_v1_ledger.queue_digest != SOURCE_V1_QUEUE_DIGEST:
        raise ValueError("depth-v2 handoff requires the exact sealed source-v1 queue and ledger")
    if not AUDIT_HISTORY_PREFIX <= published_prefix <= REVIEWED_TOTAL:
        raise ValueError("depth-v2 handoff prefix is outside the reviewed source corpus")

    for post in source_v1_queue.posts[:published_prefix]:
        entry = source_v1_ledger.entries[post.publication_id]
        if entry.state != "published" or entry.provider_effect != "verified" or not entry.message_id:
            raise ValueError(f"depth-v2 handoff requires verified published history: {post.publication_id}")
    for post in source_v1_queue.posts[published_prefix:]:
        entry = source_v1_ledger.entries[post.publication_id]
        if (
            entry.state != "pending"
            or entry.provider_effect != "impossible"
            or entry.intent_id is not None
            or entry.attempted_at_utc is not None
            or entry.message_id is not None
        ):
            raise ValueError(f"depth-v2 handoff requires pristine unpublished suffix: {post.publication_id}")


def initialize_depth_ledger(
    *,
    path: Path,
    depth_queue: SuccessorRuntimeQueue,
    source_v1_queue: SuccessorRuntimeQueue,
    source_v1_ledger: TelegramLedger,
    release: DepthRelease,
) -> TelegramLedger:
    if path.exists():
        raise ValueError(f"refusing to overwrite existing depth-v2 ledger: {path}")
    if depth_queue.digest != release.normalized_queue_digest:
        raise ValueError("depth-v2 ledger initialization requires the sealed depth-v2 queue")
    handoff = release.handoff_published_prefix
    require_exact_v1_handoff(source_v1_queue, source_v1_ledger, published_prefix=handoff)

    entries: dict[str, LedgerEntry] = {}
    for post in depth_queue.posts[:handoff]:
        historical = source_v1_ledger.entries[post.publication_id].model_copy(deep=True)
        if historical.payload_sha256 != post.payload_sha256:
            raise ValueError(f"depth-v2 locked history payload differs for {post.publication_id}")
        entries[post.publication_id] = historical
    for post in depth_queue.posts[handoff:]:
        entries[post.publication_id] = LedgerEntry(
            publication_id=post.publication_id,
            payload_sha256=post.payload_sha256,
        )

    ledger = TelegramLedger(
        schema_name="video-channel-manager.telegram-publication-ledger",
        schema_version=3,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        queue_digest=depth_queue.digest,
        entries=entries,
    )
    save_ledger(path, ledger)
    return ledger


def resolve_depth_release(
    *,
    predecessor_queue_path: Path,
    predecessor_ledger_path: Path,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    source_v1_runtime_queue_path: Path,
    source_v1_ledger_path: Path,
    depth_v2_runtime_queue_path: Path,
    depth_v2_ledger_path: Path,
    runtime_queue_path: Path,
    depth_ledger_path: Path,
    require_provider_writes: bool = False,
) -> DepthActiveSelection:
    predecessor_queue = load_predecessor_queue(predecessor_queue_path)
    predecessor_ledger = load_ledger(predecessor_ledger_path, predecessor_queue)
    if not predecessor_is_complete(predecessor_queue, predecessor_ledger):
        raise ValueError("depth-v2 activation requires the predecessor 30-post queue to be terminal")

    from video_channel_manager.telegram_presentation import load_presentation_policy
    from video_channel_manager.telegram_quote_runtime import build_successor_runtime_queue

    source_policy = load_presentation_policy(candidate_path.with_name("presentation-policy.json"))
    source_v1_queue = build_successor_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
        release_path=candidate_path.with_name("successor-release-v2.json"),
        activation_path=candidate_path.with_name("successor-activation-v1.json"),
        expected_chat_id=-1001295216957,
        expected_bot_id=8716602202,
        expected_bot_username="preaching_mp3_bot",
        presentation_policy_id=source_policy.policy_id,
        presentation_policy_sha256=source_policy.digest,
    )
    source_v1_runtime_queue_path.parent.mkdir(parents=True, exist_ok=True)
    source_v1_runtime_queue_path.write_text(source_v1_queue.model_dump_json(indent=2) + "\n", encoding="utf-8")
    source_v1_ledger = load_ledger(source_v1_ledger_path, source_v1_queue)

    release = load_depth_release(candidate_path.with_name(DEPTH_RELEASE_FILENAME))
    activation = load_depth_activation(candidate_path.with_name(DEPTH_ACTIVATION_FILENAME))
    require_exact_v1_handoff(
        source_v1_queue,
        source_v1_ledger,
        published_prefix=release.handoff_published_prefix,
    )
    if require_provider_writes and not activation.provider_writes_authorized:
        raise ValueError("depth-v2 provider writes are not authorized by the activation artifact")

    depth_v2_queue = build_depth_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
    )
    depth_v2_runtime_queue_path.parent.mkdir(parents=True, exist_ok=True)
    depth_v2_runtime_queue_path.write_text(depth_v2_queue.model_dump_json(indent=2) + "\n", encoding="utf-8")

    if not depth_ledger_path.is_file() and not depth_v2_ledger_path.is_file():
        raise ValueError(
            "depth-v3 resolution requires either the durable depth-v3 ledger or the sealed depth-v2 handoff ledger"
        )

    depth_v3_queue = build_depth_v3_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
    )
    runtime_queue_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_queue_path.write_text(depth_v3_queue.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return DepthActiveSelection(
        schema_name="video-channel-manager.telegram-active-quote-selection",
        schema_version=2,
        active_release="depth-v3",
        release_id=DEPTH_V3_RELEASE_ID,
        queue_path=str(runtime_queue_path),
        ledger_path=str(depth_ledger_path),
        ledger_relative_path=DEPTH_V3_LEDGER_RELATIVE_PATH,
        base_release_id=DEPTH_RELEASE_ID,
        base_ledger_path=str(depth_v2_ledger_path),
        queue_digest=depth_v3_queue.digest,
        predecessor_complete=True,
        needs_ledger_initialization=not depth_ledger_path.is_file(),
        history_queue_path=str(predecessor_queue_path),
        history_ledger_path=str(predecessor_ledger_path),
        source_v1_ledger_path=str(source_v1_ledger_path),
        provider_writes_authorized=activation.provider_writes_authorized,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Resolve the quality-audited LordChrist successor depth-v2 release")
    sub = root.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--predecessor-queue", type=Path, required=True)
    resolve.add_argument("--predecessor-ledger", type=Path, required=True)
    resolve.add_argument("--candidate", type=Path, required=True)
    resolve.add_argument("--translation-ledger", type=Path, required=True)
    resolve.add_argument("--integrity-amendments", type=Path, required=True)
    resolve.add_argument("--source-v1-runtime-queue", type=Path, required=True)
    resolve.add_argument("--source-v1-ledger", type=Path, required=True)
    resolve.add_argument("--depth-v2-runtime-queue", type=Path, required=True)
    resolve.add_argument("--depth-v2-ledger", type=Path, required=True)
    resolve.add_argument("--runtime-queue", type=Path, required=True)
    resolve.add_argument("--depth-ledger", type=Path, required=True)
    resolve.add_argument("--require-provider-writes", action="store_true")
    resolve.add_argument("--output", type=Path, required=True)

    initialize_v3 = sub.add_parser("initialize-v3-ledger")
    initialize_v3.add_argument("--runtime-queue", type=Path, required=True)
    initialize_v3.add_argument("--depth-v2-runtime-queue", type=Path, required=True)
    initialize_v3.add_argument("--depth-v2-ledger", type=Path, required=True)
    initialize_v3.add_argument("--restore", type=Path, required=True)
    initialize_v3.add_argument("--ledger", type=Path, required=True)
    initialize_v3.add_argument("--confirm", required=True)

    initialize = sub.add_parser("initialize-ledger")
    initialize.add_argument("--runtime-queue", type=Path, required=True)
    initialize.add_argument("--source-v1-runtime-queue", type=Path, required=True)
    initialize.add_argument("--source-v1-ledger", type=Path, required=True)
    initialize.add_argument("--release", type=Path, required=True)
    initialize.add_argument("--ledger", type=Path, required=True)
    initialize.add_argument("--confirm", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "initialize-v3-ledger":
        if args.confirm != "INITIALIZE_REVIEWED_DEPTH_V3_LEDGER":
            raise RuntimeError("depth-v3 ledger initialization requires exact confirmation")
        from video_channel_manager.telegram_quote_runtime import load_active_queue

        depth_v3_queue = load_active_queue(args.runtime_queue)
        depth_v2_queue = load_active_queue(args.depth_v2_runtime_queue)
        if not isinstance(depth_v3_queue, SuccessorRuntimeQueue) or not isinstance(
            depth_v2_queue, SuccessorRuntimeQueue
        ):
            raise ValueError("depth-v3 initialization requires successor runtime queue artifacts")
        depth_v2_ledger = load_ledger(args.depth_v2_ledger, depth_v2_queue)
        restore = load_depth_restore(args.restore)
        ledger = initialize_depth_v3_ledger(
            path=args.ledger,
            depth_v3_queue=depth_v3_queue,
            depth_v2_queue=depth_v2_queue,
            depth_v2_ledger=depth_v2_ledger,
            restore=restore,
        )
        print(json.dumps({"initialized": True, "queue_digest": ledger.queue_digest}, ensure_ascii=False))
        return 0
    if args.command == "initialize-ledger":
        if args.confirm != "INITIALIZE_REVIEWED_DEPTH_V2_LEDGER":
            raise RuntimeError("depth-v2 ledger initialization requires exact confirmation")
        from video_channel_manager.telegram_quote_runtime import load_active_queue

        depth_queue = load_active_queue(args.runtime_queue)
        source_v1_queue = load_active_queue(args.source_v1_runtime_queue)
        if not isinstance(depth_queue, SuccessorRuntimeQueue) or not isinstance(source_v1_queue, SuccessorRuntimeQueue):
            raise ValueError("depth-v2 initialization requires successor runtime queue artifacts")
        source_v1_ledger = load_ledger(args.source_v1_ledger, source_v1_queue)
        release = load_depth_release(args.release)
        ledger = initialize_depth_ledger(
            path=args.ledger,
            depth_queue=depth_queue,
            source_v1_queue=source_v1_queue,
            source_v1_ledger=source_v1_ledger,
            release=release,
        )
        print(json.dumps({"initialized": True, "queue_digest": ledger.queue_digest}, ensure_ascii=False))
        return 0

    selection = resolve_depth_release(
        predecessor_queue_path=args.predecessor_queue,
        predecessor_ledger_path=args.predecessor_ledger,
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendments,
        source_v1_runtime_queue_path=args.source_v1_runtime_queue,
        depth_v2_runtime_queue_path=args.depth_v2_runtime_queue,
        depth_v2_ledger_path=args.depth_v2_ledger,
        source_v1_ledger_path=args.source_v1_ledger,
        runtime_queue_path=args.runtime_queue,
        depth_ledger_path=args.depth_ledger,
        require_provider_writes=args.require_provider_writes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(selection.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(selection.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
