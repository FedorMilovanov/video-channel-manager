from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.lock import community_vk_write_lock_path, local_vk_write_lock
from video_channel_manager.platforms.vk.milovi_immediate_wall import MILOVI_COMMUNITY_ID
from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch import (
    PromotionDispatchBlockedBeforeProvider,
    PromotionDispatchResult,
    PromotionDispatchUnknown,
    execute_confirmed_promotion_dispatch,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch_envelope import (
    PromotionDispatchEnvelope,
    PromotionDispatchEnvelopeBlocked,
    build_confirmed_promotion_dispatch_envelope,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PromotionJournal,
    PromotionJournalOperation,
    PromotionRecoveryRequired,
    initialize_promotion_journal,
    load_promotion_journal,
    preflight_with_promotion_journal,
    record_promotion_dispatch_unknown,
    record_promotion_edit_intent,
    verify_promotion_dispatch_from_observation,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_observation import (
    PromotionObservationBatch,
    promotion_observation_from_mapping,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import PromotionDispatchStatus
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import (
    PromotionField,
    PromotionSpec,
    load_reviewed_promotion_spec,
)
from video_channel_manager.platforms.vk.milovi_issue323_status_probe import run_issue_323_status_probe
from video_channel_manager.platforms.vk.milovi_rollout_sources import write_json_atomic
from video_channel_manager.platforms.vk.store import VkTokenStore
from video_channel_manager.platforms.vk.video_description_writer import VkVideoDescriptionWriter
from video_channel_manager.platforms.vk.wall_text_writer import VkWallTextWriter
from video_channel_manager.platforms.vk.writer import VkWriteError

CONTINUE_PREVIEW_SCHEMA = "video-manager.milovi-issue-323-continue-preview"
CONTINUE_PREVIEW_VERSION = 6
PROMOTION_JOURNAL_INIT_CONFIRMATION = "INITIALIZE_REVIEWED_PROMOTION_JOURNAL"
_PROVIDER_DISPATCH_OPERATION = "milovi-issue-323-promotion-dispatch"


def _blocked_payload(
    *,
    status_output_path: Path,
    status_payload: Mapping[str, Any],
    blocker: str,
    spec_digest: str | None = None,
    observation_digest: str | None = None,
    provider_state_digest: str | None = None,
    supplied_preflight_digest_confirmation: str | None = None,
    supplied_provider_dispatch_confirmation: str | None = None,
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
        "promotion_dispatch_reconciled": False,
        "promotion_dispatch_unknown": False,
        "promotion_intent": None,
        "promotion_preflight": None,
        "promotion_preflight_digest": None,
        "promotion_preflight_evidence_digest": None,
        "promotion_preflight_confirmation_digest": None,
        "preflight_digest_confirmation_supplied": supplied_preflight_digest_confirmation is not None,
        "preflight_digest_confirmed": False,
        "provider_dispatch_confirmation_supplied": supplied_provider_dispatch_confirmation is not None,
        "provider_dispatch_confirmed": False,
        "provider_dispatch_confirmation_digest": None,
        "promotion_dispatch_envelope": None,
        "promotion_dispatch": None,
        "blockers": [blocker],
    }


def _single_unresolved_dispatch(journal: PromotionJournal) -> PromotionJournalOperation | None:
    unresolved = tuple(
        item
        for item in journal.operations
        if item.status
        in {
            PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
            PromotionDispatchStatus.UNKNOWN_REQUIRES_RECONCILIATION,
        }
    )
    if len(unresolved) > 1:
        raise PromotionRecoveryRequired(
            "Promotion journal contains multiple unresolved provider dispatches; do not infer a recovery order"
        )
    if unresolved and any(item.status is PromotionDispatchStatus.EDIT_INTENT for item in journal.operations):
        raise PromotionRecoveryRequired(
            "Promotion journal contains both unresolved dispatch and unstarted intent; do not infer a write order"
        )
    return unresolved[0] if unresolved else None


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
    provider_dispatch_confirmation_supplied: bool = False,
    provider_dispatch_confirmed: bool = False,
    provider_dispatch_confirmation_digest: str | None = None,
    provider_mutation_authorized: bool = False,
    provider_writes_executed: int = 0,
    intent_persisted: bool = False,
    intent_reconciled: bool = False,
    dispatch_reconciled: bool = False,
    dispatch_unknown: bool = False,
    intent: PromotionJournalOperation | None = None,
    envelope: PromotionDispatchEnvelope | None = None,
    dispatch: PromotionDispatchResult | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": CONTINUE_PREVIEW_SCHEMA,
        "schema_version": CONTINUE_PREVIEW_VERSION,
        "continuation_status": continuation_status,
        "provider_mutation_authorized": provider_mutation_authorized,
        "provider_writes_executed": provider_writes_executed,
        "status_evidence_path": str(status_output_path),
        "status_probe_status": status_payload.get("status"),
        "promotion_spec_digest": spec_digest,
        "promotion_observation_digest": observation_digest,
        "promotion_provider_state_digest": provider_state_digest,
        "promotion_journal_digest": journal.digest,
        "promotion_journal_initialized": journal_initialized,
        "promotion_intent_persisted": intent_persisted,
        "promotion_intent_reconciled": intent_reconciled,
        "promotion_dispatch_reconciled": dispatch_reconciled,
        "promotion_dispatch_unknown": dispatch_unknown,
        "promotion_intent": intent.as_dict() if intent is not None else None,
        "promotion_preflight": preflight.as_dict(),
        "promotion_preflight_digest": preflight.confirmation_digest,
        "promotion_preflight_evidence_digest": preflight.digest,
        "promotion_preflight_confirmation_digest": preflight.confirmation_digest,
        "preflight_digest_confirmation_supplied": digest_confirmation_supplied,
        "preflight_digest_confirmed": digest_confirmed,
        "provider_dispatch_confirmation_supplied": provider_dispatch_confirmation_supplied,
        "provider_dispatch_confirmed": provider_dispatch_confirmed,
        "provider_dispatch_confirmation_digest": provider_dispatch_confirmation_digest,
        "promotion_dispatch_envelope": envelope.as_dict() if envelope is not None else None,
        "promotion_dispatch": dispatch.as_dict() if dispatch is not None else None,
        "blockers": blockers or [],
    }


def _dispatch_existing_intent(
    *,
    status_payload: Mapping[str, Any],
    promotion_journal_path: Path,
    journal: PromotionJournal,
    envelope: PromotionDispatchEnvelope,
) -> PromotionDispatchResult:
    account_alias = status_payload.get("account_alias")
    if not isinstance(account_alias, str) or not account_alias.strip():
        raise PromotionDispatchBlockedBeforeProvider("Fresh status evidence lost the exact VK account alias")
    account_alias = account_alias.strip()
    community_id = status_payload.get("community_id")
    if community_id != MILOVI_COMMUNITY_ID:
        raise PromotionDispatchBlockedBeforeProvider(
            f"Fresh status evidence targets unexpected VK community: {community_id!r}"
        )

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    lock_path = community_vk_write_lock_path(settings.data_dir, community_id=MILOVI_COMMUNITY_ID)
    with local_vk_write_lock(
        lock_path,
        account=account_alias,
        community_id=MILOVI_COMMUNITY_ID,
        operation=_PROVIDER_DISPATCH_OPERATION,
    ):
        if envelope.field is PromotionField.CLIP_DESCRIPTION:
            clip_writer = VkVideoDescriptionWriter(
                token_store=store,
                account_alias=account_alias,
                api_version=settings.vk_api_version,
            )
            return execute_confirmed_promotion_dispatch(
                journal_path=promotion_journal_path,
                journal=journal,
                envelope=envelope,
                clip_writer=clip_writer,
            )
        wall_writer = VkWallTextWriter(
            token_store=store,
            account_alias=account_alias,
            api_version=settings.vk_api_version,
        )
        return execute_confirmed_promotion_dispatch(
            journal_path=promotion_journal_path,
            journal=journal,
            envelope=envelope,
            wall_writer=wall_writer,
        )


def _build_intent_envelope(
    *,
    spec: PromotionSpec,
    observation: PromotionObservationBatch,
    journal: PromotionJournal,
    intent: PromotionJournalOperation,
) -> PromotionDispatchEnvelope:
    return build_confirmed_promotion_dispatch_envelope(
        spec=spec,
        observation=observation,
        journal=journal,
        source_id=intent.source_id,
        field=intent.field,
    )


def run_issue_323_continue(
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
    provider_dispatch_confirmation: str | None = None,
) -> dict[str, Any]:
    """Advance exactly one durable Issue #323 continuation step from fresh provider evidence."""

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
            supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
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
            supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
        )
        write_json_atomic(output_path, payload)
        return payload

    if preflight_digest_confirmation is not None and provider_dispatch_confirmation is not None:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=(
                "Preflight confirmation and provider-dispatch confirmation must be separate invocations; "
                "a newly persisted intent can never dispatch in the same command"
            ),
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
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
                supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
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
                supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
            )
            write_json_atomic(output_path, payload)
            return payload
    else:
        if provider_dispatch_confirmation is not None:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker="Provider dispatch confirmation requires an existing durable promotion journal and edit intent",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
            )
            write_json_atomic(output_path, payload)
            return payload
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
        unresolved_dispatch = _single_unresolved_dispatch(journal)
    except PromotionRecoveryRequired as exc:
        payload = _blocked_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            blocker=str(exc),
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            supplied_preflight_digest_confirmation=preflight_digest_confirmation,
            supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
            journal_digest=journal.digest,
        )
        write_json_atomic(output_path, payload)
        return payload

    if unresolved_dispatch is not None:
        assert unresolved_dispatch.intent_preflight_digest is not None
        previous_status = unresolved_dispatch.status
        try:
            journal = verify_promotion_dispatch_from_observation(
                journal=journal,
                spec=spec,
                observation=observation,
                source_id=unresolved_dispatch.source_id,
                field=unresolved_dispatch.field,
                preflight_digest=unresolved_dispatch.intent_preflight_digest,
            )
        except PromotionRecoveryRequired as exc:
            if previous_status is PromotionDispatchStatus.EDIT_DISPATCH_STARTED:
                try:
                    journal = record_promotion_dispatch_unknown(
                        journal=journal,
                        source_id=unresolved_dispatch.source_id,
                        field=unresolved_dispatch.field,
                        preflight_digest=unresolved_dispatch.intent_preflight_digest,
                    )
                    write_json_atomic(promotion_journal_path, journal.as_dict())
                except (OSError, RuntimeError, ValueError) as persist_exc:
                    payload = _blocked_payload(
                        status_output_path=status_output_path,
                        status_payload=status_payload,
                        blocker=(
                            "Fresh dispatch reconciliation could not prove exact AFTER and UNKNOWN persistence failed; "
                            "durable STARTED remains the no-replay barrier: "
                            f"{persist_exc}"
                        ),
                        spec_digest=spec.digest,
                        observation_digest=observation.digest,
                        provider_state_digest=observation.provider_state_digest,
                        supplied_preflight_digest_confirmation=preflight_digest_confirmation,
                        supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
                        journal_digest=journal.digest,
                    )
                    write_json_atomic(output_path, payload)
                    return payload
            preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
            current = next(
                item
                for item in journal.operations
                if item.source_id == unresolved_dispatch.source_id and item.field is unresolved_dispatch.field
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
                continuation_status="dispatch_unknown_requires_reconciliation",
                digest_confirmation_supplied=preflight_digest_confirmation is not None,
                digest_confirmed=False,
                provider_dispatch_confirmation_supplied=provider_dispatch_confirmation is not None,
                dispatch_unknown=True,
                intent=current,
                blockers=[f"Persisted promotion dispatch remains unresolved: {exc}", *preflight.blockers],
            )
            write_json_atomic(output_path, payload)
            return payload
        except (RuntimeError, ValueError) as exc:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=f"Persisted promotion dispatch is internally inconsistent: {exc}",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_preflight_digest_confirmation=preflight_digest_confirmation,
                supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
                journal_digest=journal.digest,
            )
            write_json_atomic(output_path, payload)
            return payload

        write_json_atomic(promotion_journal_path, journal.as_dict())
        preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
        payload = _result_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            journal=journal,
            journal_initialized=journal_initialized,
            preflight=preflight,
            continuation_status="dispatch_reconciled_verified_ready_for_next_plan",
            digest_confirmation_supplied=preflight_digest_confirmation is not None,
            digest_confirmed=False,
            provider_dispatch_confirmation_supplied=provider_dispatch_confirmation is not None,
            dispatch_reconciled=True,
        )
        write_json_atomic(output_path, payload)
        return payload

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
            supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
            journal_digest=journal.digest,
        )
        write_json_atomic(output_path, payload)
        return payload

    if unstarted_intent is not None:
        try:
            envelope = _build_intent_envelope(
                spec=spec,
                observation=observation,
                journal=journal,
                intent=unstarted_intent,
            )
        except (PromotionDispatchEnvelopeBlocked, RuntimeError, ValueError) as exc:
            payload = _blocked_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                blocker=f"Persisted promotion intent cannot build a fresh exact dispatch envelope: {exc}",
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                supplied_preflight_digest_confirmation=preflight_digest_confirmation,
                supplied_provider_dispatch_confirmation=provider_dispatch_confirmation,
                journal_digest=journal.digest,
            )
            write_json_atomic(output_path, payload)
            return payload

        preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
        required_dispatch_digest = unstarted_intent.intent_confirmation_digest
        assert required_dispatch_digest is not None
        if provider_dispatch_confirmation is None:
            payload = _result_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                journal=journal,
                journal_initialized=journal_initialized,
                preflight=preflight,
                continuation_status="intent_ready_for_provider_dispatch_confirmation",
                digest_confirmation_supplied=preflight_digest_confirmation is not None,
                digest_confirmed=False,
                provider_dispatch_confirmation_digest=required_dispatch_digest,
                intent=unstarted_intent,
                envelope=envelope,
            )
            write_json_atomic(output_path, payload)
            return payload

        if provider_dispatch_confirmation != required_dispatch_digest:
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
                digest_confirmation_supplied=False,
                digest_confirmed=False,
                provider_dispatch_confirmation_supplied=True,
                provider_dispatch_confirmation_digest=required_dispatch_digest,
                intent=unstarted_intent,
                envelope=envelope,
                blockers=[
                    "Supplied provider-dispatch confirmation digest does not match the durable reviewed whole-batch confirmation"
                ],
            )
            write_json_atomic(output_path, payload)
            return payload

        try:
            dispatch = _dispatch_existing_intent(
                status_payload=status_payload,
                promotion_journal_path=promotion_journal_path,
                journal=journal,
                envelope=envelope,
            )
        except PromotionDispatchUnknown as exc:
            try:
                durable_journal = load_promotion_journal(promotion_journal_path)
            except (OSError, ValueError):
                durable_journal = journal
            preflight = preflight_with_promotion_journal(
                spec=spec,
                observation=observation,
                journal=durable_journal,
            )
            current = next(
                item
                for item in durable_journal.operations
                if item.source_id == unstarted_intent.source_id and item.field is unstarted_intent.field
            )
            payload = _result_payload(
                status_output_path=status_output_path,
                status_payload=status_payload,
                spec_digest=spec.digest,
                observation_digest=observation.digest,
                provider_state_digest=observation.provider_state_digest,
                journal=durable_journal,
                journal_initialized=journal_initialized,
                preflight=preflight,
                continuation_status="provider_dispatch_unknown_requires_fresh_reconciliation",
                digest_confirmation_supplied=False,
                digest_confirmed=False,
                provider_dispatch_confirmation_supplied=True,
                provider_dispatch_confirmed=True,
                provider_dispatch_confirmation_digest=required_dispatch_digest,
                provider_mutation_authorized=True,
                provider_writes_executed=1,
                dispatch_unknown=True,
                intent=current,
                envelope=envelope,
                blockers=[str(exc), *preflight.blockers],
            )
            write_json_atomic(output_path, payload)
            return payload
        except (PromotionDispatchBlockedBeforeProvider, VkWriteError, OSError, ValueError) as exc:
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
                digest_confirmation_supplied=False,
                digest_confirmed=False,
                provider_dispatch_confirmation_supplied=True,
                provider_dispatch_confirmed=True,
                provider_dispatch_confirmation_digest=required_dispatch_digest,
                intent=unstarted_intent,
                envelope=envelope,
                blockers=[f"Provider dispatch stopped before a provider mutation was proven: {exc}"],
            )
            write_json_atomic(output_path, payload)
            return payload

        durable_journal = load_promotion_journal(promotion_journal_path)
        durable_current = next(
            item
            for item in durable_journal.operations
            if item.source_id == unstarted_intent.source_id and item.field is unstarted_intent.field
        )
        durable_preflight = preflight_with_promotion_journal(
            spec=spec,
            observation=observation,
            journal=durable_journal,
        )
        payload = _result_payload(
            status_output_path=status_output_path,
            status_payload=status_payload,
            spec_digest=spec.digest,
            observation_digest=observation.digest,
            provider_state_digest=observation.provider_state_digest,
            journal=durable_journal,
            journal_initialized=journal_initialized,
            preflight=durable_preflight,
            continuation_status="provider_dispatch_started_requires_fresh_reconciliation",
            digest_confirmation_supplied=False,
            digest_confirmed=False,
            provider_dispatch_confirmation_supplied=True,
            provider_dispatch_confirmed=True,
            provider_dispatch_confirmation_digest=required_dispatch_digest,
            provider_mutation_authorized=True,
            provider_writes_executed=dispatch.provider_writes_executed,
            intent=durable_current,
            envelope=envelope,
            dispatch=dispatch,
        )
        write_json_atomic(output_path, payload)
        return payload

    if provider_dispatch_confirmation is not None:
        preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
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
            digest_confirmation_supplied=False,
            digest_confirmed=False,
            provider_dispatch_confirmation_supplied=True,
            blockers=["Provider dispatch confirmation was supplied but no durable unstarted EDIT_INTENT exists"],
        )
        write_json_atomic(output_path, payload)
        return payload

    try:
        preflight = preflight_with_promotion_journal(spec=spec, observation=observation, journal=journal)
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
        continuation_status="intent_persisted_requires_separate_provider_dispatch_confirmation",
        digest_confirmation_supplied=True,
        digest_confirmed=True,
        provider_dispatch_confirmation_digest=persisted_intent.intent_confirmation_digest,
        intent_persisted=True,
        intent=persisted_intent,
    )
    write_json_atomic(output_path, payload)
    return payload


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
    """Provider-inert compatibility entry point for the canonical continuation reducer."""

    return run_issue_323_continue(
        output_path=output_path,
        status_output_path=status_output_path,
        rollout_journal_path=rollout_journal_path,
        schedule_path=schedule_path,
        prepared_manifest_path=prepared_manifest_path,
        promotion_spec_path=promotion_spec_path,
        promotion_journal_path=promotion_journal_path,
        journal_init_confirmation=journal_init_confirmation,
        journal_created_at=journal_created_at,
        preflight_digest_confirmation=preflight_digest_confirmation,
        provider_dispatch_confirmation=None,
    )


__all__ = [
    "CONTINUE_PREVIEW_SCHEMA",
    "CONTINUE_PREVIEW_VERSION",
    "PROMOTION_JOURNAL_INIT_CONFIRMATION",
    "run_issue_323_continue",
    "run_issue_323_continue_preview",
]
