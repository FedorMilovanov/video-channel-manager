from datetime import UTC, datetime

import pytest

from video_channel_manager.telegram_multichannel_recovery import resolve_confirmed_absent_before_send
from video_channel_manager.telegram_multichannel_state import (
    GenericDispatchEnvelope,
    GenericLedgerEntry,
    GenericPublicationLedger,
)
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof

RELEASE_DIGEST = "sha256:" + "b" * 64
PROFILE_DIGEST = "sha256:" + "c" * 64
PAYLOAD_DIGEST = "sha256:" + "d" * 64
GITHUB_SHA = "a" * 40
WORKFLOW_SHA = "e" * 40
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def dispatching_fixture() -> tuple[GenericPublicationLedger, GenericDispatchEnvelope]:
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        profile_sha256=PROFILE_DIGEST,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Lordchrist",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=NOW,
    )
    envelope = GenericDispatchEnvelope(
        schema_name="video-channel-manager.telegram-generic-dispatch",
        schema_version=1,
        release_digest=RELEASE_DIGEST,
        release_id="lordchrist-research-live-2026-08",
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        profile_sha256=PROFILE_DIGEST,
        publication_id="lordchrist-research-three-preachers-numbers",
        sequence=1,
        provider_payload_sha256=PAYLOAD_DIGEST,
        intent_id="intent-1234567890abcdef",
        dispatch_mode="manual",
        workflow_run_id="123456",
        workflow_run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        target=target,
        prepared_at_utc=NOW,
    )
    entry = GenericLedgerEntry(
        publication_id=envelope.publication_id,
        provider_payload_sha256=PAYLOAD_DIGEST,
        state="dispatching",
        provider_effect="may_exist",
        intent_id=envelope.intent_id,
        dispatch_mode="manual",
        workflow_run_id=envelope.workflow_run_id,
        workflow_run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        attempted_at_utc=NOW,
        actual_chat_id=target.chat_id,
        actual_chat_username=target.chat_username,
        bot_id=target.bot_id,
        bot_username=target.bot_username,
    )
    ledger = GenericPublicationLedger(
        schema_name="video-channel-manager.telegram-generic-publication-ledger",
        schema_version=1,
        release_digest=RELEASE_DIGEST,
        release_id=envelope.release_id,
        project_key=envelope.project_key,
        channel_username=envelope.channel_username,
        profile_sha256=PROFILE_DIGEST,
        entries={entry.publication_id: entry},
    )
    return ledger, envelope


def test_pre_send_confirmed_absent_recovery_restores_retryable_pending_state() -> None:
    ledger, envelope = dispatching_fixture()
    outcome = resolve_confirmed_absent_before_send(
        ledger,
        envelope,
        evidence_note="Final CI proof failed before Telegram send; no provider mutation was attempted.",
    )

    entry = ledger.entries[envelope.publication_id]
    assert outcome.provider_effect == "confirmed_absent"
    assert outcome.retryable is True
    assert outcome.receipt is None
    assert entry.state == "pending"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None
    assert entry.workflow_run_id is None
    assert entry.actual_chat_id is None
    assert "no provider mutation was attempted" in (entry.last_error or "")


def test_pre_send_recovery_cannot_erase_non_live_or_already_resolved_intent() -> None:
    ledger, envelope = dispatching_fixture()
    resolve_confirmed_absent_before_send(ledger, envelope, evidence_note="Provider was not called.")

    with pytest.raises(ValueError, match="dispatch intent"):
        resolve_confirmed_absent_before_send(ledger, envelope, evidence_note="Provider was not called.")
