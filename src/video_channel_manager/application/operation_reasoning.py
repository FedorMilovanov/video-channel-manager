from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


TransportMode = Literal[
    "local_only",
    "official_api_read",
    "official_api_write",
    "internal_web_read",
    "browser_ui_read",
    "browser_ui_write",
]
OperationPhase = Literal[
    "planned",
    "preflight",
    "intent_persisted",
    "dispatched",
    "accepted",
    "processing",
    "verified",
    "rejected",
    "unknown",
]
ProviderEffect = Literal["impossible", "not_dispatched", "confirmed_absent", "may_exist", "verified"]
NextAction = Literal[
    "continue_bounded_probe",
    "fix_local_and_retry",
    "observe_before_action",
    "wait_and_postflight",
    "reconcile_without_retry",
    "complete",
    "stop_unsupported",
]

_BROWSER_TRANSPORTS = frozenset({"browser_ui_read", "browser_ui_write"})
_WRITE_TRANSPORTS = frozenset({"official_api_write", "browser_ui_write"})


@dataclass(frozen=True, slots=True)
class OperationReasoningState:
    """Transport-aware facts used to choose a safe next action without pattern copying."""

    transport: TransportMode
    phase: OperationPhase
    provider_effect: ProviderEffect
    exact_remote_id: str | None = None
    postcondition_verified: bool = False
    browser_state_bound: bool = False
    surface_supported: bool = True
    contradiction_present: bool = False

    def __post_init__(self) -> None:
        if self.transport == "local_only" and self.provider_effect != "impossible":
            raise ValueError("local_only transport requires provider_effect='impossible'")
        if self.transport not in _WRITE_TRANSPORTS and self.provider_effect in {"may_exist", "verified"}:
            raise ValueError("read-only transport cannot claim a provider mutation")
        if self.phase == "verified" and not self.postcondition_verified:
            raise ValueError("verified phase requires an exact postcondition")
        if self.postcondition_verified and self.provider_effect != "verified":
            raise ValueError("verified postcondition requires provider_effect='verified'")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OperationReasoningDecision:
    action: NextAction
    blind_retry_allowed: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def decide_next_action(state: OperationReasoningState) -> OperationReasoningDecision:
    """Choose from observable invariants; never infer success from UI shape or HTTP return alone."""

    if not state.surface_supported:
        return OperationReasoningDecision(
            action="stop_unsupported",
            blind_retry_allowed=False,
            reason="surface_or_transport_not_supported",
        )
    if state.contradiction_present:
        return OperationReasoningDecision(
            action="reconcile_without_retry",
            blind_retry_allowed=False,
            reason="evidence_contradiction_requires_reconciliation",
        )
    if state.postcondition_verified:
        return OperationReasoningDecision(
            action="complete",
            blind_retry_allowed=False,
            reason="exact_postcondition_verified",
        )
    if state.phase in {"accepted", "processing"}:
        if state.exact_remote_id is None:
            return OperationReasoningDecision(
                action="reconcile_without_retry",
                blind_retry_allowed=False,
                reason="accepted_or_processing_without_exact_remote_id",
            )
        return OperationReasoningDecision(
            action="wait_and_postflight",
            blind_retry_allowed=False,
            reason="accepted_or_processing_with_exact_remote_id",
        )
    if state.provider_effect == "may_exist" or state.phase == "unknown":
        return OperationReasoningDecision(
            action="reconcile_without_retry",
            blind_retry_allowed=False,
            reason="provider_effect_may_exist",
        )
    if state.transport in _BROWSER_TRANSPORTS and not state.browser_state_bound:
        return OperationReasoningDecision(
            action="observe_before_action",
            blind_retry_allowed=False,
            reason="active_browser_surface_not_proved",
        )
    if state.provider_effect == "confirmed_absent":
        return OperationReasoningDecision(
            action="fix_local_and_retry",
            blind_retry_allowed=True,
            reason="provider_postflight_proves_no_remote_effect",
        )
    if state.phase == "rejected":
        return OperationReasoningDecision(
            action="fix_local_and_retry",
            blind_retry_allowed=True,
            reason="provider_rejected_before_acceptance",
        )
    if state.transport == "local_only" or state.provider_effect in {"impossible", "not_dispatched"}:
        return OperationReasoningDecision(
            action="fix_local_and_retry",
            blind_retry_allowed=True,
            reason="failure_is_local_or_pre_dispatch",
        )
    return OperationReasoningDecision(
        action="continue_bounded_probe",
        blind_retry_allowed=False,
        reason="more_bounded_evidence_required",
    )


__all__ = [
    "OperationReasoningDecision",
    "OperationReasoningState",
    "decide_next_action",
]
