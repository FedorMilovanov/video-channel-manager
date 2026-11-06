from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_cli import _read_scheduled_canary_authorization
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import (
    OwnerScheduledCanaryApproval,
    initialize_ledger,
    mark_published,
    prepare_next,
)
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt, GenericTargetProof
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "content/telegram/channels/lordchrist-shorts-v1.json"
RELEASE = ROOT / "content/telegram/lordchrist/shorts-v1-release.json"
BINDING = ROOT / "content/telegram/channels/lordchrist-shorts-v1-target-binding.json"
APPROVAL = ROOT / "content/telegram/lordchrist/shorts-v1-scheduled-canary-approval.json"
FIRST = "lordchrist-short-ba4ZahiY-U0"
NOV8 = datetime(2026, 11, 8, 13, 7, tzinfo=UTC)
NOV9 = NOV8 + timedelta(days=1)


def _context(now: datetime):
    profile = load_channel_profile(PROFILE)
    release = load_release(RELEASE)
    binding = load_target_binding(BINDING, profile)
    authority = _read_scheduled_canary_authorization(APPROVAL)
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
        chat_title="Господь Бог — сила моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    return profile, release, target, authority


def _prepare(profile, release, ledger, target, when, approval):
    return prepare_next(
        profile,
        release,
        ledger,
        run_id="1001",
        run_attempt="1",
        github_sha="1" * 40,
        github_workflow_sha="2" * 40,
        mode="scheduled",
        target=target,
        scheduled_canary_approval=approval,
        now=when,
    )


def test_owner_approved_canary_proof_matches_exact_immutable_short_video() -> None:
    profile, release, target, authority = _context(NOV8)
    assert isinstance(authority, OwnerScheduledCanaryApproval)
    assert authority.release_digest == release.digest
    assert authority.first_publication_id == FIRST
    assert authority.owner_authorized is True
    assert authority.only_first_scheduled_video is True
    assert authority.maximum_first_send_attempts == 1
    assert authority.require_verified_first_receipt_for_followons is True
    authority.require_exact_binding(profile, release, target)


def test_default_other_releases_still_require_verified_manual_canary() -> None:
    profile, release, target, authority = _context(NOV8)
    del authority
    ledger = initialize_ledger(release)
    prepared = _prepare(profile, release, ledger, target, NOV8, None)
    assert prepared.envelope is None
    assert prepared.reason == "scheduled execution requires a verified manual canary"
    assert ledger.entries[FIRST].state == "pending"


def test_first_owner_scheduled_video_then_verified_receipt_unlocks_followons() -> None:
    profile, release, target, authority = _context(NOV8)
    ledger = initialize_ledger(release)
    first = _prepare(profile, release, ledger, target, NOV8, authority)
    assert first.envelope is not None
    assert first.envelope.publication_id == FIRST
    assert first.envelope.dispatch_mode == "scheduled"
    receipt = GenericSendReceipt(
        schema_name="video-channel-manager.telegram-generic-send-receipt",
        schema_version=1,
        project_key=profile.project_key,
        publication_id=FIRST,
        provider_payload_sha256=first.envelope.provider_payload_sha256,
        chat_id=target.chat_id,
        chat_username=target.chat_username,
        message_id=1832,
        message_url="https://t.me/lordchrist/1832",
        verified_at_utc=NOV8,
    )
    published = mark_published(ledger, first.envelope, receipt)
    assert published.state == "published"
    assert published.provider_effect == "verified"
    assert published.dispatch_mode == "scheduled"
    profile2, release2, target2, authority2 = _context(NOV9)
    second = _prepare(profile2, release2, ledger, target2, NOV9, authority2)
    assert second.envelope is not None
    assert second.envelope.publication_id == "lordchrist-short-_aDIR0D7rSk"
    assert second.envelope.dispatch_mode == "scheduled"


def test_unknown_first_attempt_does_not_unlock_followons() -> None:
    profile, release, target, authority = _context(NOV8)
    ledger = initialize_ledger(release)
    first = _prepare(profile, release, ledger, target, NOV8, authority)
    assert first.envelope is not None
    profile2, release2, target2, authority2 = _context(NOV9)
    blocked = _prepare(profile2, release2, ledger, target2, NOV9, authority2)
    assert blocked.envelope is None
    assert "no verified receipt" in blocked.reason


def test_wrong_release_digest_and_target_can_never_reuse_approval() -> None:
    profile, release, target, authority = _context(NOV8)
    for change in (
        {"release_digest": "sha256:" + "0" * 64},
        {"bot_id": authority.bot_id + 1},
        {"first_publication_id": "some-other-first-video"},
    ):
        bad = authority.model_copy(update=change)
        with pytest.raises(ValueError, match="owner-scheduled canary differs"):
            _prepare(profile, release, initialize_ledger(release), target, NOV8, bad)


def test_approval_cannot_be_applied_to_manual_dispatch() -> None:
    profile, release, target, authority = _context(NOV8)
    with pytest.raises(ValueError, match="invalid for manual"):
        prepare_next(
            profile,
            release,
            initialize_ledger(release),
            run_id="1002",
            run_attempt="1",
            github_sha="1" * 40,
            github_workflow_sha="2" * 40,
            mode="manual",
            target=target,
            expected_publication_id=FIRST,
            scheduled_canary_approval=authority,
            now=NOV8,
        )


def test_changed_source_manifest_is_refused_before_any_provider_access(tmp_path: Path) -> None:
    _, _, _, authority = _context(NOV8)
    modified = authority.model_copy(update={"source_manifest_git_blob_sha1": "0" * 40})
    target = tmp_path / "tampered-approval.json"
    target.write_text(modified.model_dump_json(indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="source manifest changed"):
        _read_scheduled_canary_authorization(target)


def test_approval_date_and_owner_boolean_are_strictly_validated() -> None:
    value = json.loads(APPROVAL.read_text(encoding="utf-8"))
    for field, new in (
        ("owner_authorized", False),
        ("maximum_first_send_attempts", 2),
        ("approved_at", "2026-11-09T16:00:00+03:00"),
    ):
        changed = dict(value)
        changed[field] = new
        with pytest.raises(Exception):
            OwnerScheduledCanaryApproval.model_validate(changed)


def test_workflow_schedules_all_four_without_forging_manual_provenance() -> None:
    text = (ROOT / ".github/workflows/lordchrist-shorts4-publisher.yml").read_text(encoding="utf-8")
    assert 'cron: "7 13 8-11 11 *"' in text
    assert "now.day not in (8,9,10,11)" in text
    assert "scheduled-canary-authorization" in text
    assert "OWNER_CANARY_PROOF" in text
    assert "mode=scheduled" in text
    assert "run_attempt" not in text or "GITHUB_RUN_ATTEMPT" in text
