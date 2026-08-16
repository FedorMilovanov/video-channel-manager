from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch_envelope import (
    PromotionDispatchEnvelope,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PromotionJournal,
    PromotionJournalOperation,
    record_promotion_dispatch_started,
    record_promotion_dispatch_unknown,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import PromotionDispatchStatus
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import PromotionField
from video_channel_manager.platforms.vk.milovi_rollout_sources import write_json_atomic
from video_channel_manager.platforms.vk.video_description_writer import VkVideoDescriptionWriter
from video_channel_manager.platforms.vk.wall_text_writer import VkWallTextWriter


class PromotionDispatchBlockedBeforeProvider(RuntimeError):
    """Fresh primitive preflight stopped before the durable/provider mutation boundary."""


class PromotionDispatchUnknown(RuntimeError):
    """The provider boundary may have been crossed; exact read reconciliation is mandatory."""


@dataclass(frozen=True, slots=True)
class PromotionDispatchResult:
    source_id: str
    field: PromotionField
    remote_id: str
    envelope_digest: str
    durable_status: PromotionDispatchStatus
    provider_writes_executed: int
    primitive_postflight_verified: bool
    required_next_action: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "field": self.field.value,
            "remote_id": self.remote_id,
            "envelope_digest": self.envelope_digest,
            "durable_status": self.durable_status.value,
            "provider_writes_executed": self.provider_writes_executed,
            "primitive_postflight_verified": self.primitive_postflight_verified,
            "required_next_action": self.required_next_action,
        }


def _journal_operation(
    journal: PromotionJournal,
    *,
    source_id: str,
    field: PromotionField,
) -> PromotionJournalOperation:
    matches = tuple(item for item in journal.operations if item.source_id == source_id and item.field is field)
    if len(matches) != 1:
        raise PromotionDispatchBlockedBeforeProvider(
            f"Promotion journal operation is not unique: {source_id}:{field.value}"
        )
    return matches[0]


def _validate_binding(*, journal: PromotionJournal, envelope: PromotionDispatchEnvelope) -> PromotionJournalOperation:
    if journal.spec_digest != envelope.spec_digest:
        raise PromotionDispatchBlockedBeforeProvider("Frozen dispatch envelope is bound to a different PromotionSpec")
    operation = _journal_operation(journal, source_id=envelope.source_id, field=envelope.field)
    if operation.status is not PromotionDispatchStatus.EDIT_INTENT or operation.dispatch_started:
        raise PromotionDispatchBlockedBeforeProvider(
            "Frozen dispatch envelope requires one durable unstarted EDIT_INTENT"
        )
    if operation.intent_preflight_digest != envelope.intent_preflight_digest:
        raise PromotionDispatchBlockedBeforeProvider("Frozen envelope audit preflight differs from durable intent")
    if operation.intent_confirmation_digest != envelope.confirmation_digest:
        raise PromotionDispatchBlockedBeforeProvider(
            "Frozen envelope confirmation differs from durable operator intent"
        )
    if operation.intent_remote_id != envelope.remote_id:
        raise PromotionDispatchBlockedBeforeProvider("Frozen envelope provider identity differs from durable intent")
    return operation


def _parse_video_remote_id(remote_id: str) -> tuple[int, int]:
    owner_text, separator, video_text = remote_id.partition("_")
    if not separator:
        raise PromotionDispatchBlockedBeforeProvider("Clip dispatch remote_id is malformed")
    try:
        owner_id = int(owner_text)
        video_id = int(video_text)
    except ValueError as exc:
        raise PromotionDispatchBlockedBeforeProvider("Clip dispatch remote_id is malformed") from exc
    if owner_id == 0 or video_id <= 0:
        raise PromotionDispatchBlockedBeforeProvider("Clip dispatch remote_id is invalid")
    return owner_id, video_id


def execute_confirmed_promotion_dispatch(
    *,
    journal_path: Path,
    journal: PromotionJournal,
    envelope: PromotionDispatchEnvelope,
    clip_writer: VkVideoDescriptionWriter | None = None,
    wall_writer: VkWallTextWriter | None = None,
) -> PromotionDispatchResult:
    """Cross exactly one provider edit boundary after persisting STARTED at the last safe point.

    The primitive's provider acknowledgement/postflight is intentionally not enough to mark the
    durable operation VERIFIED. The journal remains EDIT_DISPATCH_STARTED after a successful call;
    a later fresh canonical Issue #323 observation must perform exact AFTER reconciliation.
    """

    _validate_binding(journal=journal, envelope=envelope)
    started_journal: PromotionJournal | None = None

    def persist_dispatch_started() -> None:
        nonlocal started_journal
        if started_journal is not None:
            raise RuntimeError("Promotion dispatch durability hook was invoked more than once")
        candidate = record_promotion_dispatch_started(
            journal=journal,
            source_id=envelope.source_id,
            field=envelope.field,
            preflight_digest=envelope.intent_preflight_digest,
        )
        write_json_atomic(journal_path, candidate.as_dict())
        started_journal = candidate

    try:
        if envelope.field is PromotionField.CLIP_DESCRIPTION:
            if clip_writer is None or wall_writer is not None:
                raise PromotionDispatchBlockedBeforeProvider("Clip dispatch requires only the exact Clip writer")
            owner_id, video_id = _parse_video_remote_id(envelope.remote_id)
            clip_result = clip_writer.replace_description_if_current(
                owner_id=owner_id,
                video_id=video_id,
                expected_description=envelope.before_text,
                new_description=envelope.after_text,
                before_dispatch=persist_dispatch_started,
            )
            result_remote_id = clip_result.remote_id
            result_provider_writes = clip_result.provider_writes_executed
            result_before_sha = clip_result.before_text_sha256
            result_after_sha = clip_result.after_text_sha256
        else:
            if wall_writer is None or clip_writer is not None:
                raise PromotionDispatchBlockedBeforeProvider("Wall dispatch requires only the exact wall writer")
            if envelope.wall_incarnation is None:
                raise PromotionDispatchBlockedBeforeProvider("Wall dispatch envelope lost exact wall incarnation")
            wall_result = wall_writer.replace_message_if_current(
                expected=envelope.wall_incarnation,
                before_text=envelope.before_text,
                after_text=envelope.after_text,
                before_dispatch=persist_dispatch_started,
            )
            result_remote_id = wall_result.remote_id
            result_provider_writes = wall_result.provider_writes_executed
            result_before_sha = wall_result.before_text_sha256
            result_after_sha = wall_result.after_text_sha256

        if started_journal is None:
            raise PromotionDispatchUnknown("Exact provider primitive returned without committing dispatch_started")
        if result_remote_id != envelope.remote_id or result_provider_writes != 1:
            raise PromotionDispatchUnknown("Exact provider primitive returned inconsistent mutation evidence")
        if result_before_sha != f"sha256:{envelope.before_sha256}":
            raise PromotionDispatchUnknown("Exact provider primitive BEFORE digest differs from frozen envelope")
        if result_after_sha != f"sha256:{envelope.after_sha256}":
            raise PromotionDispatchUnknown("Exact provider primitive AFTER digest differs from frozen envelope")
    except PromotionDispatchBlockedBeforeProvider as exc:
        if started_journal is not None:
            raise PromotionDispatchUnknown(
                "Dispatch was durably started before a later provider-bound validation failed; reconcile only"
            ) from exc
        raise
    except Exception as exc:
        if started_journal is None:
            raise PromotionDispatchBlockedBeforeProvider(
                f"Exact provider primitive stopped before dispatch_started was committed: {exc}"
            ) from exc
        try:
            unknown_journal = record_promotion_dispatch_unknown(
                journal=started_journal,
                source_id=envelope.source_id,
                field=envelope.field,
                preflight_digest=envelope.intent_preflight_digest,
            )
            write_json_atomic(journal_path, unknown_journal.as_dict())
        except Exception as persist_exc:
            raise PromotionDispatchUnknown(
                "Provider outcome is unknown and durable STARTED remains the replay barrier; "
                f"UNKNOWN persistence also failed: {persist_exc}"
            ) from exc
        raise PromotionDispatchUnknown(
            "Provider outcome is unknown; durable journal requires exact read reconciliation and forbids replay"
        ) from exc

    return PromotionDispatchResult(
        source_id=envelope.source_id,
        field=envelope.field,
        remote_id=envelope.remote_id,
        envelope_digest=envelope.digest,
        durable_status=PromotionDispatchStatus.EDIT_DISPATCH_STARTED,
        provider_writes_executed=1,
        primitive_postflight_verified=True,
        required_next_action="fresh_status_reconcile_exact_after",
    )


__all__ = [
    "PromotionDispatchBlockedBeforeProvider",
    "PromotionDispatchResult",
    "PromotionDispatchUnknown",
    "execute_confirmed_promotion_dispatch",
]
