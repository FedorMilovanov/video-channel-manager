from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_multichannel_state import (
    GenericDispatchEnvelope,
    GenericLedgerEntry,
    GenericPublicationLedger,
    mark_published,
    mark_unknown,
)
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt

GenericSendProviderEffect = Literal["not_dispatched", "confirmed_absent", "may_exist", "verified"]


class GenericProviderOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-generic-provider-outcome"]
    schema_version: Literal[1]
    publication_id: str = Field(min_length=5, max_length=96)
    provider_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider_effect: GenericSendProviderEffect
    retryable: bool = False
    error: str | None = Field(default=None, max_length=1000)
    receipt: GenericSendReceipt | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "GenericProviderOutcome":
        if self.provider_effect == "verified":
            if self.receipt is None or self.error is not None or self.retryable:
                raise ValueError("verified provider outcome requires only an exact receipt")
        else:
            if self.receipt is not None or not self.error:
                raise ValueError("non-verified provider outcome requires an error and no receipt")
        if self.provider_effect == "may_exist" and self.retryable:
            raise ValueError("ambiguous provider outcome must never be marked retryable")
        return self


def _clear_dispatch_evidence(entry: GenericLedgerEntry) -> None:
    entry.intent_id = None
    entry.dispatch_mode = None
    entry.workflow_run_id = None
    entry.workflow_run_attempt = None
    entry.github_sha = None
    entry.github_workflow_sha = None
    entry.attempted_at_utc = None
    entry.published_at_utc = None
    entry.message_id = None
    entry.message_url = None
    entry.actual_chat_id = None
    entry.actual_chat_username = None
    entry.bot_id = None
    entry.bot_username = None


def _mark_proven_no_effect(
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
    outcome: GenericProviderOutcome,
) -> GenericLedgerEntry:
    entry = ledger.entries.get(envelope.publication_id)
    if entry is None or entry.intent_id != envelope.intent_id:
        raise ValueError("ledger does not contain the dispatch intent being resolved")
    if entry.state != "dispatching" or entry.provider_effect != "may_exist":
        raise ValueError("only a live dispatching intent can be resolved as no-effect")
    if outcome.provider_effect not in {"not_dispatched", "confirmed_absent"}:
        raise ValueError("no-effect transition requires provider absence evidence")

    _clear_dispatch_evidence(entry)
    entry.state = "pending" if outcome.retryable else "failed"
    entry.provider_effect = outcome.provider_effect
    entry.last_error = " ".join((outcome.error or "provider send failed").split())[:1000]
    return entry


def apply_provider_outcome(
    ledger: GenericPublicationLedger,
    envelope: GenericDispatchEnvelope,
    outcome: GenericProviderOutcome,
) -> GenericLedgerEntry:
    if outcome.publication_id != envelope.publication_id:
        raise ValueError("provider outcome publication differs from dispatch")
    if outcome.provider_payload_sha256 != envelope.provider_payload_sha256:
        raise ValueError("provider outcome payload digest differs from dispatch")

    if outcome.provider_effect == "verified":
        if outcome.receipt is None:
            raise ValueError("verified outcome is missing receipt")
        return mark_published(ledger, envelope, outcome.receipt)
    if outcome.provider_effect == "may_exist":
        return mark_unknown(ledger, envelope, error=outcome.error or "ambiguous provider outcome")
    return _mark_proven_no_effect(ledger, envelope, outcome)


__all__ = ["GenericProviderOutcome", "GenericSendProviderEffect", "apply_provider_outcome"]
