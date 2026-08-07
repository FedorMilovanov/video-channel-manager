from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_multichannel_state import (
    initialize_ledger,
    mark_published,
    prepare_next,
    verify_persisted_intent,
)
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt, GenericTargetProof

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
GITHUB_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40


def _authorized_release() -> tuple[object, GenericReleaseQueue]:
    base_profile = load_channel_profile(PROFILE_PATH)
    profile = base_profile.model_copy(update={"provider_writes_authorized": True})
    draft = load_svodka_draft(QUEUE_PATH, profile)
    candidate = build_svodka_release_candidate(profile, draft, release_id="svodka-pilot-2026-08-release")
    payload = candidate.model_dump(mode="json")
    payload["release_authorized"] = True
    payload["reviewed_by"] = "test-reviewer"
    payload["reviewed_at"] = "2026-08-08T00:00:00+00:00"
    return profile, GenericReleaseQueue.model_validate(payload)


def _target(profile, now: datetime) -> GenericTargetProof:
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=42,
        bot_username="svodka_test_bot",
        chat_id=-1001234567890,
        chat_username="deep_info_life",
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )


def test_scheduled_dispatch_is_blocked_until_verified_manual_canary() -> None:
    profile, release = _authorized_release()
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
        target=_target(profile, now),
        now=now,
    )
    assert prepared.envelope is None
    assert prepared.reason == "scheduled execution requires a verified manual canary"
    assert ledger.entries[release.items[0].publication_id].state == "pending"


def test_manual_canary_unlocks_due_scheduled_item_without_blind_state_reset() -> None:
    profile, release = _authorized_release()
    ledger = initialize_ledger(release)

    manual_now = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
    manual_target = _target(profile, manual_now)
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
        target=_target(profile, scheduled_now),
        now=scheduled_now,
    )
    assert scheduled.envelope is not None
    assert scheduled.item is not None
    assert scheduled.item.publication_id == release.items[1].publication_id
    assert scheduled.envelope.dispatch_mode == "scheduled"
    assert ledger.entries[scheduled.item.publication_id].state == "dispatching"
    assert ledger.entries[scheduled.item.publication_id].provider_effect == "may_exist"
