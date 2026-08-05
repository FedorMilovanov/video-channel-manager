from __future__ import annotations

import pytest

from video_channel_manager.application.operation_reasoning import (
    OperationReasoningState,
    decide_next_action,
)


def test_unknown_provider_effect_never_allows_blind_retry() -> None:
    decision = decide_next_action(
        OperationReasoningState(
            transport="browser_ui_write",
            phase="unknown",
            provider_effect="may_exist",
            browser_state_bound=True,
        )
    )

    assert decision.action == "reconcile_without_retry"
    assert decision.blind_retry_allowed is False


def test_accepted_item_with_exact_id_waits_for_postflight() -> None:
    decision = decide_next_action(
        OperationReasoningState(
            transport="official_api_write",
            phase="processing",
            provider_effect="may_exist",
            exact_remote_id="-60805374_12512",
        )
    )

    assert decision.action == "wait_and_postflight"
    assert decision.blind_retry_allowed is False


def test_unbound_browser_surface_requires_observation_before_click() -> None:
    decision = decide_next_action(
        OperationReasoningState(
            transport="browser_ui_write",
            phase="preflight",
            provider_effect="not_dispatched",
            browser_state_bound=False,
        )
    )

    assert decision.action == "observe_before_action"
    assert decision.reason == "active_browser_surface_not_proved"


def test_confirmed_absence_allows_one_corrected_retry() -> None:
    decision = decide_next_action(
        OperationReasoningState(
            transport="official_api_write",
            phase="rejected",
            provider_effect="confirmed_absent",
        )
    )

    assert decision.action == "fix_local_and_retry"
    assert decision.blind_retry_allowed is True


def test_local_only_failure_is_safe_to_fix_and_retry() -> None:
    decision = decide_next_action(
        OperationReasoningState(
            transport="local_only",
            phase="preflight",
            provider_effect="impossible",
        )
    )

    assert decision.action == "fix_local_and_retry"
    assert decision.blind_retry_allowed is True


def test_contradiction_wins_over_apparent_pre_dispatch_state() -> None:
    decision = decide_next_action(
        OperationReasoningState(
            transport="browser_ui_write",
            phase="preflight",
            provider_effect="not_dispatched",
            browser_state_bound=True,
            contradiction_present=True,
        )
    )

    assert decision.action == "reconcile_without_retry"
    assert decision.blind_retry_allowed is False


def test_unsupported_internal_surface_stops_instead_of_becoming_adapter() -> None:
    decision = decide_next_action(
        OperationReasoningState(
            transport="internal_web_read",
            phase="preflight",
            provider_effect="not_dispatched",
            surface_supported=False,
        )
    )

    assert decision.action == "stop_unsupported"


def test_verified_phase_requires_exact_postcondition() -> None:
    with pytest.raises(ValueError, match="verified phase"):
        OperationReasoningState(
            transport="official_api_write",
            phase="verified",
            provider_effect="verified",
            postcondition_verified=False,
        )


def test_read_only_transport_cannot_claim_provider_mutation() -> None:
    with pytest.raises(ValueError, match="read-only transport"):
        OperationReasoningState(
            transport="internal_web_read",
            phase="accepted",
            provider_effect="may_exist",
        )
