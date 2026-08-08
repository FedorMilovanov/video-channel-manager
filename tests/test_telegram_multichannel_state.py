from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_multichannel_state import (
    initialize_ledger,
    mark_published,
    prepare_next,
    publication_window,
    skip_expired_pending,
    strict_next_item,
    verify_persisted_intent,
)
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt, GenericTargetProof
from video_channel_manager.telegram_target_binding import TelegramTargetBinding, load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
GITHUB_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40


def _authorized_release() -> tuple[TelegramChannelProfile, TelegramTargetBinding, GenericReleaseQueue]:
    base_profile = load_channel_profile(PROFILE_PATH)
    profile = base_profile.model_copy(update={"provider_writes_authorized": True})
    binding = load_target_binding(BINDING_PATH, base_profile)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-release",
        binding=binding.model_copy(update={"profile_sha256": profile.digest}),
    )
    release = authorize_svodka_release(
        candidate,
        reviewed_by="test-reviewer",
        reviewed_at=datetime(2026, 8, 8, tzinfo=UTC),
    )
    return profile, binding, release


def _target(
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    now: datetime,
    *,
    chat_id: int | None = None,
    bot_id: int | None = None,
    bot_username: str | None = None,
) -> GenericTargetProof:
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=bot_id if bot_id is not None else binding.bot_id,
        bot_username=bot_username if bot_username is not None else binding.bot_username,
        chat_id=chat_id if chat_id is not None else binding.chat_id,
        chat_username=binding.chat_username,
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )


def test_scheduled_dispatch_is_blocked_until_verified_manual_canary() -> None:
    profile, binding, release = _authorized_release()
    ledger = initialize_ledger(release)
    now = datetime(2026, 8, 9, 17, 0, tzinfo=UTC)
    prepared = prepare_next(
        profile,
        release,
        ledger,
        run_id="100",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=_target(profile, binding, now),
        now=now,
    )
    assert prepared.envelope is None
    assert prepared.reason == "scheduled execution requires a verified manual canary"
    assert ledger.entries[release.items[0].publication_id].state == "pending"


def test_release_bound_state_rejects_wrong_numeric_channel_or_bot() -> None:
    profile, binding, release = _authorized_release()
    now = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="release-bound Telegram target"):
        prepare_next(
            profile,
            release,
            initialize_ledger(release),
            run_id="103",
            run_attempt="1",
            github_sha=GITHUB_SHA,
            github_workflow_sha=WORKFLOW_SHA,
            mode="manual",
            target=_target(profile, binding, now, chat_id=-1009999999999),
            expected_publication_id=release.items[0].publication_id,
            now=now,
        )

    with pytest.raises(ValueError, match="release-bound Telegram target"):
        prepare_next(
            profile,
            release,
            initialize_ledger(release),
            run_id="104",
            run_attempt="1",
            github_sha=GITHUB_SHA,
            github_workflow_sha=WORKFLOW_SHA,
            mode="manual",
            target=_target(profile, binding, now, bot_id=binding.bot_id + 1),
            expected_publication_id=release.items[0].publication_id,
            now=now,
        )


def test_manual_canary_cannot_publish_before_or_after_exact_release_window() -> None:
    profile, binding, release = _authorized_release()
    first_id = release.items[0].publication_id
    window_start, window_end = publication_window(release, first_id)
    assert window_start == datetime(2026, 8, 9, 7, 30, tzinfo=UTC)
    assert window_end == datetime(2026, 8, 9, 16, 30, tzinfo=UTC)

    before = datetime(2026, 8, 9, 7, 0, tzinfo=UTC)
    too_early = prepare_next(
        profile,
        release,
        initialize_ledger(release),
        run_id="105",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=_target(profile, binding, before),
        expected_publication_id=first_id,
        now=before,
    )
    assert too_early.envelope is None
    assert "does not open until" in too_early.reason

    expired = datetime(2026, 8, 9, 16, 30, tzinfo=UTC)
    too_late = prepare_next(
        profile,
        release,
        initialize_ledger(release),
        run_id="106",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=_target(profile, binding, expired),
        expected_publication_id=first_id,
        now=expired,
    )
    assert too_late.envelope is None
    assert "publication window expired" in too_late.reason


def test_stale_pending_items_can_be_skipped_without_provider_effect() -> None:
    _, _, release = _authorized_release()
    ledger = initialize_ledger(release)
    now = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)

    skipped = skip_expired_pending(release, ledger, now=now)

    assert skipped == (release.items[0].publication_id, release.items[1].publication_id)
    for publication_id in skipped:
        entry = ledger.entries[publication_id]
        assert entry.state == "skipped"
        assert entry.provider_effect == "impossible"
        assert entry.intent_id is None
        assert "publication window expired" in (entry.last_error or "")

    next_item, reason = strict_next_item(release, ledger)
    assert next_item is not None
    assert next_item.publication_id == release.items[2].publication_id
    assert reason == "next pending publication"


def test_manual_canary_unlocks_due_scheduled_item_without_blind_state_reset() -> None:
    profile, binding, release = _authorized_release()
    ledger = initialize_ledger(release)

    manual_now = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
    manual_target = _target(profile, binding, manual_now)
    first_id = release.items[0].publication_id
    manual = prepare_next(
        profile,
        release,
        ledger,
        run_id="101",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=manual_target,
        expected_publication_id=first_id,
        now=manual_now,
    )
    assert manual.envelope is not None
    assert manual.reason == "prepared"
    verify_persisted_intent(release, ledger, manual.envelope)

    receipt = GenericSendReceipt(
        schema_name="video-channel-manager.telegram-generic-send-receipt",
        schema_version=1,
        project_key=profile.project_key,
        publication_id=first_id,
        provider_payload_sha256=manual.envelope.provider_payload_sha256,
        chat_id=manual_target.chat_id,
        chat_username=manual_target.chat_username,
        message_id=7001,
        message_url="https://t.me/deep_info_life/7001",
        verified_at_utc=manual_now,
    )
    entry = mark_published(ledger, manual.envelope, receipt)
    assert entry.state == "published"
    assert entry.provider_effect == "verified"
    assert entry.dispatch_mode == "manual"

    scheduled_now = datetime(2026, 8, 9, 17, 0, tzinfo=UTC)
    scheduled = prepare_next(
        profile,
        release,
        ledger,
        run_id="102",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=_target(profile, binding, scheduled_now),
        now=scheduled_now,
    )
    assert scheduled.envelope is not None
    assert scheduled.item is not None
    assert scheduled.item.publication_id == release.items[1].publication_id
    assert scheduled.envelope.dispatch_mode == "scheduled"
    assert ledger.entries[scheduled.item.publication_id].state == "dispatching"
    assert ledger.entries[scheduled.item.publication_id].provider_effect == "may_exist"
