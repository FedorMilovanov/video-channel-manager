from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_outcome import GenericProviderOutcome, apply_provider_outcome
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue
from video_channel_manager.telegram_multichannel_state import (
    GenericDispatchEnvelope,
    GenericPublicationLedger,
    initialize_ledger,
    prepare_next,
)
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt, GenericTargetProof
from video_channel_manager.telegram_target_binding import TelegramTargetBinding, load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
GITHUB_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40


def _runtime() -> tuple[
    TelegramChannelProfile,
    TelegramTargetBinding,
    GenericReleaseQueue,
    GenericPublicationLedger,
    GenericDispatchEnvelope,
]:
    base_profile = load_channel_profile(PROFILE_PATH)
    profile = base_profile.model_copy(update={"provider_writes_authorized": True})
    binding = load_target_binding(BINDING_PATH, base_profile).model_copy(update={"profile_sha256": profile.digest})
    draft = load_svodka_draft(QUEUE_PATH, profile)
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-release",
        binding=binding,
    )
    release = authorize_svodka_release(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="test-reviewer",
        reviewed_at=datetime(2026, 8, 8, tzinfo=UTC),
    )
    ledger = initialize_ledger(release)
    now = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    first_id = release.items[0].publication_id
    prepared = prepare_next(
        profile,
        release,
        ledger,
        run_id="200",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target,
        expected_publication_id=first_id,
        now=now,
    )
    assert prepared.envelope is not None
    return profile, binding, release, ledger, prepared.envelope


def _failure(
    envelope: GenericDispatchEnvelope,
    *,
    effect: str,
    retryable: bool,
) -> GenericProviderOutcome:
    return GenericProviderOutcome.model_validate(
        {
            "schema_name": "video-channel-manager.telegram-generic-provider-outcome",
            "schema_version": 1,
            "publication_id": envelope.publication_id,
            "provider_payload_sha256": envelope.provider_payload_sha256,
            "provider_effect": effect,
            "retryable": retryable,
            "error": "provider rejected test request",
            "receipt": None,
        }
    )


def test_retryable_proven_no_effect_returns_item_to_pending_and_clears_intent() -> None:
    _, _, _, ledger, envelope = _runtime()
    entry = apply_provider_outcome(
        ledger,
        envelope,
        _failure(envelope, effect="confirmed_absent", retryable=True),
    )

    assert entry.state == "pending"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None
    assert entry.workflow_run_id is None
    assert entry.actual_chat_id is None
    assert entry.message_id is None


def test_terminal_proven_no_effect_becomes_failed_not_unknown() -> None:
    _, _, _, ledger, envelope = _runtime()
    entry = apply_provider_outcome(
        ledger,
        envelope,
        _failure(envelope, effect="confirmed_absent", retryable=False),
    )

    assert entry.state == "failed"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None


def test_ambiguous_provider_outcome_blocks_queue_as_unknown_and_keeps_intent() -> None:
    _, _, _, ledger, envelope = _runtime()
    entry = apply_provider_outcome(
        ledger,
        envelope,
        _failure(envelope, effect="may_exist", retryable=False),
    )

    assert entry.state == "unknown"
    assert entry.provider_effect == "may_exist"
    assert entry.intent_id == envelope.intent_id
    assert entry.actual_chat_id == envelope.target.chat_id


def test_verified_provider_outcome_becomes_published_with_exact_receipt() -> None:
    _, _, _, ledger, envelope = _runtime()
    receipt = GenericSendReceipt(
        schema_name="video-channel-manager.telegram-generic-send-receipt",
        schema_version=1,
        project_key=envelope.project_key,
        publication_id=envelope.publication_id,
        provider_payload_sha256=envelope.provider_payload_sha256,
        chat_id=envelope.target.chat_id,
        chat_username=envelope.target.chat_username,
        message_id=9001,
        message_url="https://t.me/deep_info_life/9001",
        verified_at_utc=envelope.prepared_at_utc,
    )
    outcome = GenericProviderOutcome(
        schema_name="video-channel-manager.telegram-generic-provider-outcome",
        schema_version=1,
        publication_id=envelope.publication_id,
        provider_payload_sha256=envelope.provider_payload_sha256,
        provider_effect="verified",
        receipt=receipt,
    )
    entry = apply_provider_outcome(ledger, envelope, outcome)

    assert entry.state == "published"
    assert entry.provider_effect == "verified"
    assert entry.message_id == 9001
    assert entry.message_url == "https://t.me/deep_info_life/9001"


def test_outcome_rejects_non_send_effect_and_ambiguous_retry() -> None:
    _, _, _, _, envelope = _runtime()
    payload = {
        "schema_name": "video-channel-manager.telegram-generic-provider-outcome",
        "schema_version": 1,
        "publication_id": envelope.publication_id,
        "provider_payload_sha256": envelope.provider_payload_sha256,
        "provider_effect": "impossible",
        "retryable": False,
        "error": "invalid effect",
        "receipt": None,
    }
    with pytest.raises(ValidationError):
        GenericProviderOutcome.model_validate(payload)

    payload["provider_effect"] = "may_exist"
    payload["retryable"] = True
    with pytest.raises(ValidationError, match="must never be marked retryable"):
        GenericProviderOutcome.model_validate(payload)


def test_outcome_cannot_be_applied_to_a_different_payload() -> None:
    _, _, _, ledger, envelope = _runtime()
    payload = _failure(envelope, effect="confirmed_absent", retryable=False).model_dump(mode="json")
    payload["provider_payload_sha256"] = "sha256:" + "0" * 64
    outcome = GenericProviderOutcome.model_validate(payload)

    with pytest.raises(ValueError, match="payload digest differs"):
        apply_provider_outcome(ledger, envelope, outcome)
