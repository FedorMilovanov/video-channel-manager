from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PromotionJournal,
    PromotionJournalOperation,
    PromotionRecoveryRequired,
    initialize_promotion_journal,
    load_promotion_journal,
    preflight_with_promotion_journal,
    reconcile_promotion_intent_before_dispatch,
    record_promotion_edit_intent,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    promotion_observation_from_mapping,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import PromotionDispatchStatus
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import load_reviewed_promotion_spec
from video_channel_manager.platforms.vk.milovi_issue323_status_probe import run_issue_323_status_probe
from video_channel_manager.platforms.vk.milovi_rollout_sources import write_json_atomic

CONTINUE_PREVIEW_SCHEMA = "video-manager.milovi-issue-323-continue-preview"
CONTINUE_PREVIEW_VERSION = 4
PROMOTION_JOURNAL_INIT_CONFIRMATION = "INITIALIZE_REVIEWED_PROMOTION_JOURNAL"


def _blocked_payload(
    *,
    status_output_path: Path,
    status_payload: Mapping[str, Any],
    blocker: str,
    spec_digest: str | None = None,
    observation_digest: str | None = None,
    provider_state_digest: str | None = None,
    supplied_preflight_digest_confirmation: str | None = None,
    journal_digest: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": CONTINUE_PREVIEW_SCHEMA,
        "schema_version": CONTINUE_PREVIEW_VERSION,
        "continuation_status": "blocked",
        "provider_mutation_authorized": False,
        "provider_writes_executed": 0,
        "status_evidence_path": str(status_output_path),
        "status_probe_status": status_payload.get("status"),
        "promotion_spec_digest": spec_digest,
        "promotion_observation_digest": observation_digest,
        "promotion_provider_state_digest": provider_state_digest,
        "promotion_journal_digest": journal_digest,
        "promotion_journal_initialized": False,
        "promotion_intent_persisted": False,
        "promotion_intent_reconciled": False,
        "promotion_intent": None,
        "promotion_preflight": None,
        "promotion_preflight_digest": None,
        "promotion_preflight_evidence_digest": None,
        "promotion_preflight_confirmation_digest": None,
        "preflight_digest_confirmation_supplied": supplied_preflight_digest_confirmation is not None,
        "preflight_digest_confirmed": False,
        "blockers": [blocker],
    }


def _single_unstarted_intent(journal: PromotionJournal) -> PromotionJournalOperation | None:
    intents = tuple(item for item in journal.operations if item.status is PromotionDispatchStatus.EDIT_INTENT)
    if len(intents) > 1:
        raise PromotionRecoveryRequired(
            "Promotion journal contains multiple unstarted edit intents; do not infer a dispatch order"
        )
    return intents[0] if intents else None


def _result_payload(
    *,
    status_output_path: Path,
    status_payload: Mapping[str, Any],
    spec_digest: str,
    observation_digest: str,
    provider_state_digest: str,
    journal: PromotionJournal,
    journal_initialized: bool,
    preflight: Any,
    continuation_status: str,
    digest_confirmation_supplied: bool,
    digest_confirmed: bool,
    intent_persisted: bool = False,
    intent_reconciled: bool = False,
    intent: PromotionJournalOperation | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": CONTINUE_PREVIEW_SCHEMA,
        "schema_version": CONTINUE_PREVIEW_VERSION,
        "continuation_status": continuation_status,
        "provider_mutation_authorized": False,
        "provider_writes_executed": 0,
        "status_evidence_path": str(status_output_path),
        "status_probe_status": status_payload.get("status"),
        "promotion_spec_digest": spec_digest,
        "promotion_observation_digest": observation_digest,
        "promotion_provider_state_digest": provider_state_digest,
        "promotion_journal_digest": journal.digest,
        "promotion_journal_initialized": journal_initialized,
        "promotion_intent_persisted": intent_persisted,
        "promotion_intent_reconciled": intent_reconciled,
        "promotion_intent": intent.as_dict() if intent is not None else None,
        "promotion_preflight": preflight.as_dict(),
        "promotion_preflight_digest": preflight.confirmation_digest,
        "promotion_preflight_evidence_digest": preflight.digest,
        "promotion_preflight_confirmation_digest": preflight.confirmation_digest,
        "preflight_digest_confirmation_supplied": digest_confirmation_supplied,
        "preflight_digest_confirmed": digest_confirmed,
        "blockers": blockers or [],
    }


def run_issue_323_continue_preview(
    *,
    output_path: Path,
    status_output_path: Path,
    rollout_journal_path: Path,
    schedule_path: Path,
    prepared_manifest_path: Path,
    promotion_spec_path: Path,
    promotion_journal_path: Path,
    journal_init_confirmation: str | None = None,
    journal_created_at: str | None = None,
    preflight_digest_confirmation: str | None = None,
) -> dict[str, Any]:
    """Build or persist one confirmed local intent; never cross the provider mutation boundary."""

    status_payload = run_issue_323_status_probe(
        output_path=status_output_path,
        journal_path=rollout_journal_path,
        schedule_path=schedule_path,
        prepared_manifest_path=prepared_manifest_path,
    )
    raw_observation = status_payload.get("promotion_observation")
    if not isinstance(raw_observation, Mapping):
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker="Status evidence lost typed promotion_observation",
            supplied_preflight_digest_confirmation=preflight_digest_confirmation,
        )
        write_json_atomic(output_path, payload)
        return payload

    try:
        observation = promotion_observation_from_mapping(raw_observation)
        spec = load_reviewed_promotion_spec(promotion_spec_path)
    except (OSError, ValueError) as exc:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=f"Reviewed promotion inputs are invalid: {exc}",
            supplied_preflight_digest_confirmation=preflight_digest_confirmation,
        )
        write_json_atomic(output_path, payload)
        return payload

    journal_initialized = False
    if promotion_journal_path.is_file():
        if journal_init_confirmation is not None:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker="Promotion journal already exists; initialization confirmation is not accepted for an existing journal",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            )
            write_json_atomic(output_path, payload)
            return payload
        try:
            journal = load_promotion_journal(promotion_journal_path)
        except (OSError, ValueError) as exc:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=f"Promotion journal is invalid: {exc}",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            )
            write_json_atomic(output_path, payload)
            return payload
    else:
        if journal_init_confirmation != PROMOTION_JOURNAL_INIT_CONFIRMATION:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=(
                    "Promotion journal is missing. Review the exact 12x2 PromotionSpec, then explicitly initialize "
                    f"with confirmation {PROMOTION_JOURNAL_INIT_CONFIRMATION!r}."
                ),
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            )
            write_json_atomic(output_path, payload)
            return payload
        try:
            journal = initialize_promotion_journal(
                spec=spec,
                observation=observation,
                created_at=journal_created_at or datetime.now(UTC).isoformat(),
            )
        except ValueError as exc:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=f"Promotion journal initialization refused: {exc}",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            )
            write_json_atomic(output_path, payload)
            return payload
        write_json_atomic(promotion_journal_path, journal.as_dict())
        journal_initialized = True

    try:
        unstarted_intent = _single_unstarted_intent(journal)
    except PromotionRecoveryRequired as exc:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=str(exc),
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            journal_digest=journal.digest,
        )
        write_json_atomic(output_path, payload)
        return payload

    if unstarted_intent is not None:
        assert unstarted_intent.intent_preflight_digest is not None
        try:
            journal = reconcile_promotion_intent_before_dispatch(
                journal=journal,
                spec=spec,
                observation=observation,
                source_id=unstarted_intent.source_id,
                field=unstarted_intent.field,
                preflight_digest=unstarted_intent.intent_preflight_digest,
            )
        except (PromotionRecoveryRequired, RuntimeError, ValueError) as exc:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=f"Persisted promotion intent requires recovery: {exc}",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_preflight_digest_confirmation=preflight_digest_confirmation,
                journal_digest=journal.digest,
            )
            write_json_atomic(output_path, payload)
            return payload
        write_json_atomic(promotion_journal_path, journal.as_dict())
        preflight = preflight_with_promotion_journal(
            spec=spec,
            observation=observation,
            journal=journal,
        )
        payload = _result_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            journal=journal,
            journal_initialized=journal_initialized,
            preflight=preflight,
            continuation_status="intent_reconciled_ready_for_digest_confirmation",
            digest_confirmation_supplied=preflight_digest_confirmation is not None,
            digest_confirmed=False,
            intent_reconciled=True,
        )
        write_json_atomic(output_path, payload)
        return payload

    try:
        preflight = preflight_with_promotion_journal(
            spec=spec,
            observation=observation,
            journal=journal,
        )
    except ValueError as exc:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=f"Promotion journal/spec binding is invalid: {exc}",
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            journal_digest=journal.digest,
        )
        write_json_atomic(output_path, payload)
        return payload

    blockers = list(preflight.blockers)
    digest_confirmed = False
    if preflight.executable and preflight_digest_confirmation is not None:
        if preflight_digest_confirmation == preflight.confirmation_digest:
            digest_confirmed = True
        else:
            blockers.append(
                "Supplied preflight confirmation digest does not match the fresh exact provider state and plan"
            )

    if blockers:
        payload = _result_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            journal=journal,
            journal_initialized=journal_initialized,
            preflight=preflight,
            continuation_status="blocked",
            digest_confirmation_supplied=preflight_digest_confirmation is not None,
            digest_confirmed=False,
            blockers=blockers,
        )
        write_json_atomic(output_path, payload)
        return payload

    if not preflight.planned_mutations:
        payload = _result_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            journal=journal,
            journal_initialized=journal_initialized,
            preflight=preflight,
            continuation_status="no_promotion_mutations_required",
            digest_confirmation_supplied=preflight_digest_confirmation is not None,
            digest_confirmed=digest_confirmed,
        )
        write_json_atomic(output_path, payload)
        return payload

    if not digest_confirmed:
        payload = _result_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            journal=journal,
            journal_initialized=journal_initialized,
            preflight=preflight,
            continuation_status="ready_for_digest_confirmation",
            digest_confirmation_supplied=preflight_digest_confirmation is not None,
            digest_confirmed=False,
        )
        write_json_atomic(output_path, payload)
        return payload

    first = preflight.planned_mutations[0]
    try:
        journal = record_promotion_edit_intent(
            journal=journal,
            preflight=preflight,
            source_id=first.source_id,
            field=first.field,
        )
    except (RuntimeError, ValueError) as exc:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=f"Confirmed promotion intent could not be persisted: {exc}",
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            journal_digest=journal.digest,
        )
        write_json_atomic(output_path, payload)
        return payload
    write_json_atomic(promotion_journal_path, journal.as_dict())
    persisted_intent = _single_unstarted_intent(journal)
    assert persisted_intent is not None
    payload = _result_payload(
        status_output_path=status_output_path,
        status_payload=status_payload,
        spec_digest=spec.digest,
        observation_digest=observation.digest,
        provider_state_digest=observation.provider_state_digest,
        journal=journal,
        journal_initialized=journal_initialized,
        preflight=preflight,
        continuation_status="intent_persisted_provider_dispatch_not_available",
        digest_confirmation_supplied=True,
        digest_confirmed=True,
        intent_persisted=True,
        intent=persisted_intent,
    )
    write_json_atomic(output_path, payload)
    return payload


__all__ = [
    "CONTINUE_PREVIEW_SCHEMA",
    "CONTINUE_PREVIEW_VERSION",
    "PROMOTION_JOURNAL_INIT_CONFIRMATION",
    "run_issue_323_continue_preview",
]
