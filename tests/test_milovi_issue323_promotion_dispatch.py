from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch as dispatch_module
from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch import (
    PromotionDispatchBlockedBeforeProvider,
    PromotionDispatchUnknown,
    execute_confirmed_promotion_dispatch,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_dispatch_envelope import PromotionDispatchEnvelope
from video_channel_manager.platforms.vk.milovi_issue323_promotion_journal import (
    PromotionJournal,
    PromotionJournalOperation,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_preflight import PromotionDispatchStatus
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import PromotionField, promotion_text_sha256
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.video_description_writer import VkVideoDescriptionEditResult
from video_channel_manager.platforms.vk.wall_safety import VkWallPostFingerprint, VkWallSurface
from video_channel_manager.platforms.vk.wall_text_writer import VkWallTextEditResult
from video_channel_manager.platforms.vk.writer import VkWriteError


SOURCE_ID = ROLL_OUT_IDS[0]
SPEC_DIGEST = "sha256:" + "1" * 64
INTENT_PREFLIGHT_DIGEST = "sha256:" + "2" * 64
CONFIRMATION_DIGEST = "sha256:" + "3" * 64
FRESH_PREFLIGHT_DIGEST = "sha256:" + "4" * 64
FRESH_OBSERVATION_DIGEST = "sha256:" + "5" * 64
PROVIDER_STATE_DIGEST = "sha256:" + "6" * 64
BASELINE_DIGEST = "sha256:" + "7" * 64
CLIP_REMOTE_ID = "-68859909_456239232"
WALL_REMOTE_ID = "-68859909_700"
BEFORE = "exact BEFORE\n"
AFTER = " exact AFTER\u200b "


def _journal(field: PromotionField, remote_id: str) -> PromotionJournal:
    operations: list[PromotionJournalOperation] = []
    for source_id in ROLL_OUT_IDS:
        for candidate_field in PromotionField:
            if (source_id, candidate_field) == (SOURCE_ID, field):
                operations.append(
                    PromotionJournalOperation(
                        source_id=source_id,
                        field=candidate_field,
                        status=PromotionDispatchStatus.EDIT_INTENT,
                        intent_preflight_digest=INTENT_PREFLIGHT_DIGEST,
                        intent_confirmation_digest=CONFIRMATION_DIGEST,
                        intent_remote_id=remote_id,
                    )
                )
            else:
                operations.append(
                    PromotionJournalOperation(
                        source_id=source_id,
                        field=candidate_field,
                        status=PromotionDispatchStatus.PENDING,
                    )
                )
    return PromotionJournal(
        spec_digest=SPEC_DIGEST,
        baseline_observation_digest=BASELINE_DIGEST,
        created_at="2026-08-16T18:55:00+00:00",
        operations=tuple(operations),
    )


def _envelope(field: PromotionField) -> PromotionDispatchEnvelope:
    remote_id = CLIP_REMOTE_ID if field is PromotionField.CLIP_DESCRIPTION else WALL_REMOTE_ID
    wall_incarnation = None
    if field is PromotionField.WALL_MESSAGE:
        wall_incarnation = VkWallPostFingerprint(
            owner_id=-68859909,
            post_id=700,
            surface=VkWallSurface.PUBLISHED,
            publish_date=1_786_900_000,
            text_sha256=f"sha256:{promotion_text_sha256(BEFORE)}",
            attachments=("video-68859909_456239232",),
        )
    return PromotionDispatchEnvelope(
        source_id=SOURCE_ID,
        field=field,
        remote_id=remote_id,
        before_text=BEFORE,
        before_sha256=promotion_text_sha256(BEFORE),
        after_text=AFTER,
        after_sha256=promotion_text_sha256(AFTER),
        spec_digest=SPEC_DIGEST,
        confirmation_digest=CONFIRMATION_DIGEST,
        intent_preflight_digest=INTENT_PREFLIGHT_DIGEST,
        fresh_preflight_digest=FRESH_PREFLIGHT_DIGEST,
        fresh_observation_digest=FRESH_OBSERVATION_DIGEST,
        provider_state_digest=PROVIDER_STATE_DIGEST,
        wall_incarnation=wall_incarnation,
    )


def _journal_status(path: Path, field: PromotionField) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    operation = next(
        item for item in payload["operations"] if item["source_id"] == SOURCE_ID and item["field"] == field.value
    )
    return str(operation["status"])


class _ClipWriter:
    def __init__(
        self,
        *,
        journal_path: Path,
        events: list[str],
        error: Exception | None = None,
    ) -> None:
        self.journal_path = journal_path
        self.events = events
        self.error = error
        self.provider_calls = 0

    def replace_description_if_current(
        self,
        *,
        owner_id: int,
        video_id: int,
        expected_description: str,
        new_description: str,
        verification_attempts: int = 5,
        verification_delay_seconds: float = 0.5,
        before_dispatch: Callable[[], None] | None = None,
    ) -> VkVideoDescriptionEditResult:
        assert (owner_id, video_id) == (-68859909, 456239232)
        assert expected_description == BEFORE
        assert new_description == AFTER
        assert before_dispatch is not None
        self.events.append("primitive_preflight")
        before_dispatch()
        assert _journal_status(self.journal_path, PromotionField.CLIP_DESCRIPTION) == "edit_dispatch_started"
        self.events.append("durable_started_visible")
        self.provider_calls += 1
        self.events.append("provider_write")
        if self.error is not None:
            raise self.error
        return VkVideoDescriptionEditResult(
            remote_id=CLIP_REMOTE_ID,
            title="Exact title",
            video_type="short_video",
            before_text_sha256=f"sha256:{promotion_text_sha256(BEFORE)}",
            after_text_sha256=f"sha256:{promotion_text_sha256(AFTER)}",
        )


class _WallWriter:
    def __init__(self, *, journal_path: Path, events: list[str]) -> None:
        self.journal_path = journal_path
        self.events = events
        self.provider_calls = 0

    def replace_message_if_current(
        self,
        *,
        expected: VkWallPostFingerprint,
        before_text: str,
        after_text: str,
        max_posts_per_surface: int = 10000,
        before_dispatch: Callable[[], None] | None = None,
    ) -> VkWallTextEditResult:
        assert expected.remote_id == WALL_REMOTE_ID
        assert before_text == BEFORE
        assert after_text == AFTER
        assert before_dispatch is not None
        self.events.append("primitive_preflight")
        before_dispatch()
        assert _journal_status(self.journal_path, PromotionField.WALL_MESSAGE) == "edit_dispatch_started"
        self.events.append("durable_started_visible")
        self.provider_calls += 1
        self.events.append("provider_write")
        return VkWallTextEditResult(
            remote_id=WALL_REMOTE_ID,
            surface=expected.surface,
            publish_date=expected.publish_date,
            attachments=expected.attachments,
            before_text_sha256=expected.text_sha256,
            after_text_sha256=f"sha256:{promotion_text_sha256(AFTER)}",
            before_snapshot_sha256="sha256:" + "8" * 64,
            after_snapshot_sha256="sha256:" + "9" * 64,
        )


def test_clip_dispatch_persists_started_before_exactly_one_provider_write(tmp_path: Path) -> None:
    journal_path = tmp_path / "promotion-journal.json"
    events: list[str] = []
    writer = _ClipWriter(journal_path=journal_path, events=events)

    result = execute_confirmed_promotion_dispatch(
        journal_path=journal_path,
        journal=_journal(PromotionField.CLIP_DESCRIPTION, CLIP_REMOTE_ID),
        envelope=_envelope(PromotionField.CLIP_DESCRIPTION),
        clip_writer=writer,  # type: ignore[arg-type]
    )

    assert writer.provider_calls == 1
    assert events == ["primitive_preflight", "durable_started_visible", "provider_write"]
    assert _journal_status(journal_path, PromotionField.CLIP_DESCRIPTION) == "edit_dispatch_started"
    assert result.durable_status is PromotionDispatchStatus.EDIT_DISPATCH_STARTED
    assert result.provider_writes_executed == 1
    assert result.required_next_action == "fresh_status_reconcile_exact_after"


def test_wall_dispatch_uses_same_durable_started_barrier(tmp_path: Path) -> None:
    journal_path = tmp_path / "promotion-journal.json"
    events: list[str] = []
    writer = _WallWriter(journal_path=journal_path, events=events)

    result = execute_confirmed_promotion_dispatch(
        journal_path=journal_path,
        journal=_journal(PromotionField.WALL_MESSAGE, WALL_REMOTE_ID),
        envelope=_envelope(PromotionField.WALL_MESSAGE),
        wall_writer=writer,  # type: ignore[arg-type]
    )

    assert writer.provider_calls == 1
    assert events == ["primitive_preflight", "durable_started_visible", "provider_write"]
    assert _journal_status(journal_path, PromotionField.WALL_MESSAGE) == "edit_dispatch_started"
    assert result.primitive_postflight_verified is True


def test_provider_exception_after_started_is_durable_unknown_and_never_replayed(tmp_path: Path) -> None:
    journal_path = tmp_path / "promotion-journal.json"
    writer = _ClipWriter(
        journal_path=journal_path,
        events=[],
        error=VkWriteError("lost video.edit response", method="video.edit"),
    )

    with pytest.raises(PromotionDispatchUnknown, match="forbids replay"):
        execute_confirmed_promotion_dispatch(
            journal_path=journal_path,
            journal=_journal(PromotionField.CLIP_DESCRIPTION, CLIP_REMOTE_ID),
            envelope=_envelope(PromotionField.CLIP_DESCRIPTION),
            clip_writer=writer,  # type: ignore[arg-type]
        )

    assert writer.provider_calls == 1
    assert _journal_status(journal_path, PromotionField.CLIP_DESCRIPTION) == "unknown_requires_reconciliation"


def test_unknown_persistence_failure_keeps_durable_started_as_replay_barrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal_path = tmp_path / "promotion-journal.json"
    writer = _ClipWriter(
        journal_path=journal_path,
        events=[],
        error=VkWriteError("lost video.edit response", method="video.edit"),
    )
    original_write = dispatch_module.write_json_atomic
    writes = 0

    def fail_second_write(path: Path, payload: object) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("cannot persist UNKNOWN")
        original_write(path, payload)  # type: ignore[arg-type]

    monkeypatch.setattr(dispatch_module, "write_json_atomic", fail_second_write)

    with pytest.raises(PromotionDispatchUnknown, match="UNKNOWN persistence also failed"):
        execute_confirmed_promotion_dispatch(
            journal_path=journal_path,
            journal=_journal(PromotionField.CLIP_DESCRIPTION, CLIP_REMOTE_ID),
            envelope=_envelope(PromotionField.CLIP_DESCRIPTION),
            clip_writer=writer,  # type: ignore[arg-type]
        )

    assert writes == 2
    assert writer.provider_calls == 1
    assert _journal_status(journal_path, PromotionField.CLIP_DESCRIPTION) == "edit_dispatch_started"


def test_durable_started_write_failure_prevents_provider_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    journal_path = tmp_path / "promotion-journal.json"
    writer = _ClipWriter(journal_path=journal_path, events=[])

    def fail_write(_path: Path, _payload: object) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(dispatch_module, "write_json_atomic", fail_write)

    with pytest.raises(PromotionDispatchBlockedBeforeProvider, match="before dispatch_started"):
        execute_confirmed_promotion_dispatch(
            journal_path=journal_path,
            journal=_journal(PromotionField.CLIP_DESCRIPTION, CLIP_REMOTE_ID),
            envelope=_envelope(PromotionField.CLIP_DESCRIPTION),
            clip_writer=writer,  # type: ignore[arg-type]
        )

    assert writer.provider_calls == 0
    assert not journal_path.exists()


def test_envelope_journal_binding_conflict_blocks_before_primitive(tmp_path: Path) -> None:
    journal_path = tmp_path / "promotion-journal.json"
    journal = _journal(PromotionField.CLIP_DESCRIPTION, CLIP_REMOTE_ID)
    envelope = _envelope(PromotionField.CLIP_DESCRIPTION)
    bad_envelope = PromotionDispatchEnvelope(
        source_id=envelope.source_id,
        field=envelope.field,
        remote_id=envelope.remote_id,
        before_text=envelope.before_text,
        before_sha256=envelope.before_sha256,
        after_text=envelope.after_text,
        after_sha256=envelope.after_sha256,
        spec_digest="sha256:" + "a" * 64,
        confirmation_digest=envelope.confirmation_digest,
        intent_preflight_digest=envelope.intent_preflight_digest,
        fresh_preflight_digest=envelope.fresh_preflight_digest,
        fresh_observation_digest=envelope.fresh_observation_digest,
        provider_state_digest=envelope.provider_state_digest,
    )
    writer = _ClipWriter(journal_path=journal_path, events=[])

    with pytest.raises(PromotionDispatchBlockedBeforeProvider, match="different PromotionSpec"):
        execute_confirmed_promotion_dispatch(
            journal_path=journal_path,
            journal=journal,
            envelope=bad_envelope,
            clip_writer=writer,  # type: ignore[arg-type]
        )

    assert writer.provider_calls == 0
