from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import (
    CHANNEL_USERNAME,
    PROJECT_KEY,
    SHA256_PATTERN,
    TelegramLedger,
    TelegramQueue,
)
from video_channel_manager.telegram_quote_successor import (
    LEGACY_QUEUE_DIGEST,
    SuccessorQuoteCard,
    SuccessorQuoteCorpus,
    SuccessorRelease,
    load_successor_corpus,
    load_successor_release,
)
from video_channel_manager.telegram_publisher import load_ledger
from video_channel_manager.telegram_state import initialize_ledger, strict_next_post

SUCCESSOR_RUNTIME_SCHEMA = "video-channel-manager.telegram-successor-runtime-queue"
SUCCESSOR_RUNTIME_SCHEMA_VERSION = 1
SUCCESSOR_ACTIVATION_SCHEMA = "video-channel-manager.telegram-successor-activation"
SUCCESSOR_ACTIVATION_SCHEMA_VERSION = 1
SUCCESSOR_RELEASE_ID = "lordchrist-successor-quotes-v1-integrity-v2"
SUCCESSOR_LEDGER_RELATIVE_PATH = "content/telegram/lordchrist/successor-publication-ledger.json"
ATTRIBUTION_QUOTED_RE = re.compile(r"^(?P<author>.+?),\s*«(?P<work>[^»]+)»(?P<suffix>.*)$")


class RuntimeSourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    author: str = Field(min_length=2, max_length=160)
    work: str = Field(min_length=2, max_length=320)


class SuccessorRuntimePost(BaseModel):
    """Provider-ready view of one sealed successor card.

    The visible text is deterministically materialized from the reviewed card. The
    payload fingerprint remains the normalized card fingerprint, so transport
    intent is still cryptographically bound to the complete reviewed evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=60)
    publication_id: str = Field(pattern=r"^lordchrist-successor-[a-z0-9][a-z0-9-]{4,90}$")
    title: str = Field(min_length=2, max_length=160)
    text: str = Field(min_length=100, max_length=4096)
    source: RuntimeSourceIdentity
    source_sequence: int = Field(ge=1, le=60)
    source_payload_sha256: str = Field(pattern=SHA256_PATTERN)

    @property
    def payload_sha256(self) -> str:
        return self.source_payload_sha256


class SuccessorRuntimeQueue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-runtime-queue"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    release_id: Literal["lordchrist-successor-quotes-v1-integrity-v2"]
    predecessor_queue_digest: Literal["sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"]
    normalized_corpus_digest: str = Field(pattern=SHA256_PATTERN)
    posts: tuple[SuccessorRuntimePost, ...]

    @model_validator(mode="after")
    def validate_runtime_queue(self) -> "SuccessorRuntimeQueue":
        if len(self.posts) != 60:
            raise ValueError("successor runtime queue must contain exactly 60 reviewed cards")
        if [post.source_sequence for post in self.posts] != list(range(1, 61)):
            raise ValueError("successor runtime source sequence must be exactly 1..60")
        if [post.sequence for post in self.posts] != list(range(1, 61)):
            raise ValueError("successor runtime dispatch sequence must be exactly 1..60")
        ids = [post.publication_id for post in self.posts]
        if len(ids) != len(set(ids)):
            raise ValueError("successor runtime publication IDs must be unique")
        return self

    @property
    def digest(self) -> str:
        # The reviewed normalized corpus is the release identity. Runtime text is
        # generated deterministically from those exact cards by current-main code.
        return self.normalized_corpus_digest


class SuccessorActivation(BaseModel):
    """Production authorization envelope layered over the immutable staged release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-successor-activation"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    owning_issue: Literal[582]
    release_id: Literal["lordchrist-successor-quotes-v1-integrity-v2"]
    predecessor_queue_digest: Literal["sha256:43518f50844b92230dd3854c363e86f0075347e31ed266f0ecad9c92b48d1b20"]
    successor_queue_digest: str = Field(pattern=SHA256_PATTERN)
    activation_policy: Literal["after_predecessor_queue_complete"]
    release_state: Literal["armed_after_predecessor_terminal"]
    provider_writes_authorized: Literal[True]
    chat_id: int = Field(lt=0)
    bot_id: int = Field(gt=0)
    bot_username: str = Field(min_length=2, max_length=64)
    presentation_policy_id: Literal["lordchrist-editorial-v2"]
    presentation_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    state_ledger_relative_path: Literal["content/telegram/lordchrist/successor-publication-ledger.json"]


class ActiveQuoteSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-active-quote-selection"]
    schema_version: Literal[1]
    active_release: Literal["predecessor", "successor"]
    queue_path: str
    ledger_path: str
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    predecessor_complete: bool
    needs_ledger_initialization: bool
    history_queue_path: str | None = None
    history_ledger_path: str | None = None


def _load_activation(path: Path) -> SuccessorActivation:
    try:
        return SuccessorActivation.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid LordChrist successor activation {path}: {exc}") from exc


def _presentation_identity(attribution_ru: str) -> RuntimeSourceIdentity:
    value = " ".join(attribution_ru.strip().split())
    quoted = ATTRIBUTION_QUOTED_RE.match(value)
    if quoted is not None:
        author = quoted.group("author").strip()
        work = quoted.group("work").strip()
        suffix = quoted.group("suffix").strip().lstrip(",").strip()
        if suffix:
            work = f"{work}, {suffix}"
        return RuntimeSourceIdentity(author=author, work=work)

    if "," not in value:
        raise ValueError(f"successor attribution has no author/work separator: {attribution_ru}")
    author, work = value.split(",", 1)
    work = work.strip()
    if work.startswith("«") and work.endswith("»"):
        work = work[1:-1].strip()
    return RuntimeSourceIdentity(author=author.strip(), work=work)


def _runtime_post(card: SuccessorQuoteCard) -> SuccessorRuntimePost:
    source = _presentation_identity(card.attribution_ru)
    body = [card.quote_ru.strip()]
    if card.editorial_context_ru is not None:
        body.append(card.editorial_context_ru.strip())
    hashtags = " ".join(card.hashtags)
    text = "\n\n".join([*body, f"© {source.author}, «{source.work}»", hashtags])
    return SuccessorRuntimePost(
        sequence=card.sequence,
        publication_id=card.publication_id,
        title=card.title,
        text=text,
        source=source,
        source_sequence=card.sequence,
        source_payload_sha256=card.payload_sha256,
    )


def build_successor_runtime_queue(
    *,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    release_path: Path,
    activation_path: Path,
    expected_chat_id: int,
    expected_bot_id: int,
    expected_bot_username: str,
    presentation_policy_id: str,
    presentation_policy_sha256: str,
) -> SuccessorRuntimeQueue:
    release = load_successor_release(
        release_path,
        candidate_path,
        translation_ledger_path,
        integrity_amendment_path,
    )
    if not isinstance(release, SuccessorRelease):
        raise ValueError("successor activation requires the sealed schema-v2 integrity release")
    corpus: SuccessorQuoteCorpus = load_successor_corpus(
        candidate_path,
        translation_ledger_path,
        integrity_amendment_path,
    )
    activation = _load_activation(activation_path)

    if release.release_id != activation.release_id:
        raise ValueError("successor activation release_id differs from the sealed staged release")
    if release.predecessor_queue_digest != activation.predecessor_queue_digest:
        raise ValueError("successor activation predecessor binding differs from the staged release")
    if release.normalized_corpus_digest != activation.successor_queue_digest:
        raise ValueError("successor activation queue digest differs from the staged release")
    if corpus.digest != activation.successor_queue_digest:
        raise ValueError("successor activation queue digest differs from the reviewed normalized corpus")
    if activation.chat_id != expected_chat_id:
        raise ValueError("successor activation chat_id differs from the exact LordChrist target")
    if activation.bot_id != expected_bot_id or activation.bot_username.casefold() != expected_bot_username.casefold():
        raise ValueError("successor activation bot identity differs from the exact LordChrist writer")
    if activation.presentation_policy_id != presentation_policy_id:
        raise ValueError("successor activation presentation policy id differs from production")
    if activation.presentation_policy_sha256 != presentation_policy_sha256:
        raise ValueError("successor activation presentation policy digest differs from production")

    return SuccessorRuntimeQueue(
        schema_name=SUCCESSOR_RUNTIME_SCHEMA,
        schema_version=SUCCESSOR_RUNTIME_SCHEMA_VERSION,
        project_key=PROJECT_KEY,
        channel_username=CHANNEL_USERNAME,
        release_id=SUCCESSOR_RELEASE_ID,
        predecessor_queue_digest=LEGACY_QUEUE_DIGEST,
        normalized_corpus_digest=corpus.digest,
        posts=tuple(_runtime_post(card) for card in corpus.posts),
    )


def load_active_queue(path: Path) -> TelegramQueue | SuccessorRuntimeQueue:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Telegram queue {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid Telegram queue {path}: root must be an object")
    try:
        if payload.get("schema_name") == SUCCESSOR_RUNTIME_SCHEMA:
            return SuccessorRuntimeQueue.model_validate(payload)
        return TelegramQueue.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid Telegram queue {path}: {exc}") from exc


def predecessor_is_complete(queue: TelegramQueue, ledger: TelegramLedger) -> bool:
    if queue.digest != LEGACY_QUEUE_DIGEST:
        raise ValueError("handoff predecessor is not the immutable reviewed 30-post queue")
    post, reason = strict_next_post(queue, ledger)
    if post is not None:
        return False
    if reason != "queue complete":
        raise ValueError(f"predecessor queue cannot hand off: {reason}")
    if any(entry.provider_effect == "may_exist" for entry in ledger.entries.values()):
        raise ValueError("predecessor queue has an unresolved provider effect")
    return True


def resolve_active_quote_release(
    *,
    predecessor_queue_path: Path,
    predecessor_ledger_path: Path,
    candidate_path: Path,
    translation_ledger_path: Path,
    integrity_amendment_path: Path,
    release_path: Path,
    activation_path: Path,
    runtime_queue_path: Path,
    successor_ledger_path: Path,
    expected_chat_id: int,
    expected_bot_id: int,
    expected_bot_username: str,
    presentation_policy_id: str,
    presentation_policy_sha256: str,
) -> ActiveQuoteSelection:
    predecessor_queue = load_active_queue(predecessor_queue_path)
    if not isinstance(predecessor_queue, TelegramQueue):
        raise ValueError("predecessor handoff input must be the immutable legacy TelegramQueue")
    predecessor_ledger = load_ledger(predecessor_ledger_path, predecessor_queue)
    complete = predecessor_is_complete(predecessor_queue, predecessor_ledger)
    if not complete:
        return ActiveQuoteSelection(
            schema_name="video-channel-manager.telegram-active-quote-selection",
            schema_version=1,
            active_release="predecessor",
            queue_path=str(predecessor_queue_path),
            ledger_path=str(predecessor_ledger_path),
            queue_digest=predecessor_queue.digest,
            predecessor_complete=False,
            needs_ledger_initialization=False,
        )

    runtime_queue = build_successor_runtime_queue(
        candidate_path=candidate_path,
        translation_ledger_path=translation_ledger_path,
        integrity_amendment_path=integrity_amendment_path,
        release_path=release_path,
        activation_path=activation_path,
        expected_chat_id=expected_chat_id,
        expected_bot_id=expected_bot_id,
        expected_bot_username=expected_bot_username,
        presentation_policy_id=presentation_policy_id,
        presentation_policy_sha256=presentation_policy_sha256,
    )
    runtime_queue_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_queue_path.write_text(runtime_queue.model_dump_json(indent=2) + "\n", encoding="utf-8")

    return ActiveQuoteSelection(
        schema_name="video-channel-manager.telegram-active-quote-selection",
        schema_version=1,
        active_release="successor",
        queue_path=str(runtime_queue_path),
        ledger_path=str(successor_ledger_path),
        queue_digest=runtime_queue.digest,
        predecessor_complete=True,
        needs_ledger_initialization=not successor_ledger_path.is_file(),
        history_queue_path=str(predecessor_queue_path),
        history_ledger_path=str(predecessor_ledger_path),
    )


def prepare_with_history(
    queue: Any,
    ledger: TelegramLedger,
    history_ledger: TelegramLedger,
    prepare_callable: Any,
    **kwargs: Any,
) -> Any:
    """Apply cross-release daily/canary policy without polluting successor state.

    A validated shadow ledger exposes predecessor verified publications to the
    existing safety policy. Only the selected successor entry is copied back.
    """

    overlap = set(ledger.entries).intersection(history_ledger.entries)
    if overlap:
        raise ValueError(f"active and history ledgers overlap publication IDs: {sorted(overlap)}")
    shadow = TelegramLedger(
        schema_name=ledger.schema_name,
        schema_version=ledger.schema_version,
        project_key=ledger.project_key,
        channel_username=ledger.channel_username,
        queue_digest=ledger.queue_digest,
        entries={
            **{key: value.model_copy(deep=True) for key, value in history_ledger.entries.items()},
            **{key: value.model_copy(deep=True) for key, value in ledger.entries.items()},
        },
    )
    prepared = prepare_callable(queue, shadow, **kwargs)
    if prepared.envelope is not None:
        publication_id = prepared.envelope.publication_id
        ledger.entries[publication_id] = shadow.entries[publication_id].model_copy(deep=True)
    return prepared


def initialize_successor_ledger(path: Path, runtime_queue_path: Path) -> TelegramLedger:
    if path.exists():
        raise ValueError(f"refusing to overwrite existing successor ledger: {path}")
    queue = load_active_queue(runtime_queue_path)
    if not isinstance(queue, SuccessorRuntimeQueue):
        raise ValueError("successor ledger initialization requires a successor runtime queue")
    ledger = initialize_ledger(queue)  # type: ignore[arg-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return ledger


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Resolve the single active LordChrist quote release")
    sub = root.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--predecessor-queue", type=Path, required=True)
    resolve.add_argument("--predecessor-ledger", type=Path, required=True)
    resolve.add_argument("--candidate", type=Path, required=True)
    resolve.add_argument("--translation-ledger", type=Path, required=True)
    resolve.add_argument("--integrity-amendments", type=Path, required=True)
    resolve.add_argument("--release", type=Path, required=True)
    resolve.add_argument("--activation", type=Path, required=True)
    resolve.add_argument("--runtime-queue", type=Path, required=True)
    resolve.add_argument("--successor-ledger", type=Path, required=True)
    resolve.add_argument("--expected-chat-id", type=int, required=True)
    resolve.add_argument("--expected-bot-id", type=int, required=True)
    resolve.add_argument("--expected-bot-username", required=True)
    resolve.add_argument("--presentation-policy-id", required=True)
    resolve.add_argument("--presentation-policy-sha256", required=True)
    resolve.add_argument("--output", type=Path, required=True)

    initialize = sub.add_parser("initialize-ledger")
    initialize.add_argument("--runtime-queue", type=Path, required=True)
    initialize.add_argument("--ledger", type=Path, required=True)
    initialize.add_argument("--confirm", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "initialize-ledger":
        if args.confirm != "INITIALIZE_REVIEWED_SUCCESSOR_LEDGER":
            raise RuntimeError("successor ledger initialization requires exact confirmation")
        ledger = initialize_successor_ledger(args.ledger, args.runtime_queue)
        print(json.dumps({"initialized": True, "queue_digest": ledger.queue_digest}, ensure_ascii=False))
        return 0

    selection = resolve_active_quote_release(
        predecessor_queue_path=args.predecessor_queue,
        predecessor_ledger_path=args.predecessor_ledger,
        candidate_path=args.candidate,
        translation_ledger_path=args.translation_ledger,
        integrity_amendment_path=args.integrity_amendments,
        release_path=args.release,
        activation_path=args.activation,
        runtime_queue_path=args.runtime_queue,
        successor_ledger_path=args.successor_ledger,
        expected_chat_id=args.expected_chat_id,
        expected_bot_id=args.expected_bot_id,
        expected_bot_username=args.expected_bot_username,
        presentation_policy_id=args.presentation_policy_id,
        presentation_policy_sha256=args.presentation_policy_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(selection.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(selection.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
