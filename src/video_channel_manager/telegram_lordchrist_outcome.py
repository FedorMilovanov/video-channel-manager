from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_models import (
    DispatchEnvelope,
    LedgerEntry,
    TelegramLedger,
    TelegramQueue,
)
from video_channel_manager.telegram_presentation import (
    PresentationPolicy,
    RenderedTelegramPost,
    verify_rendered_post,
)
from video_channel_manager.telegram_state import verify_dispatch_against_queue, verify_persisted_intent

SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
GITHUB_SHA_PATTERN = r"^[0-9a-f]{40}$"


class LordchristProviderOutcome(BaseModel):
    """Exact post-send state snapshot bound to one durable Lordchrist dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-lordchrist-provider-outcome"]
    schema_version: Literal[1]
    queue_digest: str = Field(pattern=SHA256_PATTERN)
    publication_id: str = Field(pattern=r"^lordchrist-[a-z0-9][a-z0-9-]{4,80}$")
    dispatch_intent_id: str = Field(min_length=16, max_length=128)
    workflow_run_id: str = Field(min_length=1, max_length=128)
    workflow_run_attempt: str = Field(pattern=r"^[1-9][0-9]*$")
    github_sha: str = Field(pattern=GITHUB_SHA_PATTERN)
    github_workflow_sha: str = Field(pattern=GITHUB_SHA_PATTERN)
    source_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    presentation_policy_id: str = Field(min_length=3, max_length=96)
    presentation_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    entry: LedgerEntry

    @model_validator(mode="after")
    def validate_exact_dispatch_result(self) -> "LordchristProviderOutcome":
        entry = self.entry
        if entry.publication_id != self.publication_id:
            raise ValueError("provider outcome entry publication differs from outcome identity")
        if entry.payload_sha256 != self.source_payload_sha256:
            raise ValueError("provider outcome source payload differs from outcome identity")
        if entry.workflow_run_id != self.workflow_run_id:
            raise ValueError("provider outcome entry run id differs from dispatch provenance")
        if entry.workflow_run_attempt != self.workflow_run_attempt:
            raise ValueError("provider outcome entry run attempt differs from dispatch provenance")
        if entry.github_sha != self.github_sha or entry.github_workflow_sha != self.github_workflow_sha:
            raise ValueError("provider outcome entry GitHub provenance differs from dispatch provenance")
        if entry.state == "dispatching" or entry.provider_effect == "impossible":
            raise ValueError("provider outcome must represent a completed provider attempt")
        return self


def _require_outcome_matches_dispatch(
    outcome: LordchristProviderOutcome,
    envelope: DispatchEnvelope,
    rendered: RenderedTelegramPost,
) -> None:
    if outcome.queue_digest != envelope.queue_digest:
        raise ValueError("provider outcome queue digest differs from durable dispatch")
    if outcome.publication_id != envelope.publication_id:
        raise ValueError("provider outcome publication differs from durable dispatch")
    if outcome.dispatch_intent_id != envelope.intent_id:
        raise ValueError("provider outcome intent differs from durable dispatch")
    if outcome.workflow_run_id != envelope.workflow_run_id:
        raise ValueError("provider outcome run id differs from durable dispatch")
    if outcome.workflow_run_attempt != envelope.workflow_run_attempt:
        raise ValueError("provider outcome run attempt differs from durable dispatch")
    if outcome.github_sha != envelope.github_sha or outcome.github_workflow_sha != envelope.github_workflow_sha:
        raise ValueError("provider outcome GitHub provenance differs from durable dispatch")
    if outcome.source_payload_sha256 != envelope.payload_sha256:
        raise ValueError("provider outcome source payload differs from durable dispatch")
    if rendered.publication_id != envelope.publication_id:
        raise ValueError("persisted rendered publication differs from durable dispatch")
    if rendered.source_payload_sha256 != envelope.payload_sha256:
        raise ValueError("persisted rendered source payload differs from durable dispatch")
    if outcome.provider_payload_sha256 != rendered.provider_payload_sha256:
        raise ValueError("provider outcome provider payload differs from persisted rendered payload")
    if outcome.presentation_policy_id != rendered.presentation_policy_id:
        raise ValueError("provider outcome presentation policy differs from persisted rendered payload")
    if outcome.presentation_policy_sha256 != rendered.presentation_policy_sha256:
        raise ValueError("provider outcome presentation digest differs from persisted rendered payload")

    entry = outcome.entry
    if entry.dispatch_mode != envelope.dispatch_mode:
        raise ValueError("provider outcome dispatch mode differs from durable dispatch")
    if entry.attempted_at_utc != envelope.prepared_at_utc:
        raise ValueError("provider outcome attempted timestamp differs from durable dispatch")
    if entry.actual_chat_id != envelope.target.chat_id:
        raise ValueError("provider outcome channel id differs from durable dispatch")
    if entry.actual_chat_username != envelope.target.chat_username:
        raise ValueError("provider outcome channel username differs from durable dispatch")
    if entry.bot_id != envelope.target.bot_id:
        raise ValueError("provider outcome bot id differs from durable dispatch")
    if (entry.bot_username or "").casefold() != envelope.target.bot_username.casefold():
        raise ValueError("provider outcome bot username differs from durable dispatch")


def capture_lordchrist_provider_outcome(
    queue: TelegramQueue,
    envelope: DispatchEnvelope,
    rendered: RenderedTelegramPost,
    presentation_policy: PresentationPolicy,
    entry: LedgerEntry,
) -> LordchristProviderOutcome:
    post = verify_dispatch_against_queue(queue, envelope)
    verify_rendered_post(post, presentation_policy, rendered)
    if rendered.source_payload_sha256 != envelope.payload_sha256:
        raise ValueError("persisted rendered source payload differs from durable dispatch")

    outcome = LordchristProviderOutcome(
        schema_name="video-channel-manager.telegram-lordchrist-provider-outcome",
        schema_version=1,
        queue_digest=envelope.queue_digest,
        publication_id=envelope.publication_id,
        dispatch_intent_id=envelope.intent_id,
        workflow_run_id=envelope.workflow_run_id,
        workflow_run_attempt=envelope.workflow_run_attempt,
        github_sha=envelope.github_sha,
        github_workflow_sha=envelope.github_workflow_sha,
        source_payload_sha256=envelope.payload_sha256,
        provider_payload_sha256=rendered.provider_payload_sha256,
        presentation_policy_id=rendered.presentation_policy_id,
        presentation_policy_sha256=rendered.presentation_policy_sha256,
        entry=entry.model_copy(deep=True),
    )
    _require_outcome_matches_dispatch(outcome, envelope, rendered)
    return outcome


def apply_lordchrist_provider_outcome(
    queue: TelegramQueue,
    ledger: TelegramLedger,
    envelope: DispatchEnvelope,
    rendered: RenderedTelegramPost,
    outcome: LordchristProviderOutcome,
) -> LedgerEntry:
    # Post-effect recovery must not depend on a later presentation-policy revision.
    # The source run already validated and durably persisted the rendered payload
    # before provider mutation. Recovery binds that exact persisted payload to the
    # exact dispatch and archived outcome instead of reinterpreting it under a new policy.
    verify_dispatch_against_queue(queue, envelope)
    verify_persisted_intent(queue, ledger, envelope)
    _require_outcome_matches_dispatch(outcome, envelope, rendered)

    recovered = outcome.entry.model_copy(deep=True)
    ledger.entries[envelope.publication_id] = recovered
    TelegramLedger.model_validate(ledger.model_dump(mode="json"))
    return recovered


def load_lordchrist_provider_outcome(path: Path) -> LordchristProviderOutcome:
    try:
        return LordchristProviderOutcome.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Lordchrist provider outcome {path}: {exc}") from exc


__all__ = [
    "LordchristProviderOutcome",
    "apply_lordchrist_provider_outcome",
    "capture_lordchrist_provider_outcome",
    "load_lordchrist_provider_outcome",
]
