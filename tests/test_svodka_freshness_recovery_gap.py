from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_state import initialize_ledger, skip_expired_pending
from video_channel_manager.telegram_publication_freshness import (
    next_publication_freshness,
    publication_deadline,
    publication_freshness,
    skip_expired_pending_by_freshness,
)
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
SKIP_WORKFLOW_PATH = ROOT / ".github/workflows/svodka-skip-expired.yml"
SCHEDULED_WORKFLOW_PATH = ROOT / ".github/workflows/svodka-scheduled-publisher.yml"
CLI_PATH = ROOT / "src/video_channel_manager/telegram_multichannel_cli.py"
MAX_LAG_MINUTES = 120


def _release():
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-recovery-gap-test",
        binding=binding,
    )
    return authorize_svodka_release(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="freshness-recovery-test",
        reviewed_at=datetime(2026, 8, 8, tzinfo=UTC),
    )


def test_freshness_deadline_is_also_the_recovery_skip_boundary() -> None:
    release = _release()
    first = release.items[0]
    deadline = publication_deadline(
        release,
        first.publication_id,
        max_lag_minutes=MAX_LAG_MINUTES,
    )

    before = publication_freshness(
        release,
        first.publication_id,
        now=deadline - timedelta(microseconds=1),
        max_lag_minutes=MAX_LAG_MINUTES,
    )
    at_deadline = publication_freshness(
        release,
        first.publication_id,
        now=deadline,
        max_lag_minutes=MAX_LAG_MINUTES,
    )

    ledger_before = initialize_ledger(release)
    skipped_before = skip_expired_pending_by_freshness(
        release,
        ledger_before,
        now=deadline - timedelta(microseconds=1),
        max_lag_minutes=MAX_LAG_MINUTES,
    )

    ledger_at_deadline = initialize_ledger(release)
    skipped_at_deadline = skip_expired_pending_by_freshness(
        release,
        ledger_at_deadline,
        now=deadline,
        max_lag_minutes=MAX_LAG_MINUTES,
    )

    assert before.eligible is True
    assert before.deadline_utc == deadline
    assert at_deadline.eligible is False
    assert at_deadline.reason == "publication_too_stale"
    assert skipped_before == ()
    assert skipped_at_deadline == (first.publication_id,)
    assert ledger_at_deadline.entries[first.publication_id].state == "skipped"
    assert ledger_at_deadline.entries[first.publication_id].provider_effect == "impossible"


def test_bounded_recovery_closes_the_old_dead_zone_without_changing_legacy_mode() -> None:
    release = _release()
    first = release.items[0]
    second = release.items[1]
    deadline = publication_deadline(
        release,
        first.publication_id,
        max_lag_minutes=MAX_LAG_MINUTES,
    )
    next_slot = second.scheduled_at.astimezone(UTC)
    assert deadline < next_slot

    bounded_ledger = initialize_ledger(release)
    legacy_ledger = initialize_ledger(release)

    bounded_skipped = skip_expired_pending_by_freshness(
        release,
        bounded_ledger,
        now=deadline,
        max_lag_minutes=MAX_LAG_MINUTES,
    )
    legacy_skipped = skip_expired_pending(release, legacy_ledger, now=deadline)

    assert bounded_skipped == (first.publication_id,)
    assert legacy_skipped == ()

    evening = next_publication_freshness(
        release,
        bounded_ledger,
        now=next_slot,
        max_lag_minutes=MAX_LAG_MINUTES,
    )
    assert evening.eligible is True
    assert evening.publication_id == second.publication_id
    assert evening.reason == "publication_fresh"


def test_svodka_manual_and_scheduled_recovery_share_the_same_explicit_limit() -> None:
    skip_workflow = SKIP_WORKFLOW_PATH.read_text(encoding="utf-8")
    scheduled_workflow = SCHEDULED_WORKFLOW_PATH.read_text(encoding="utf-8")
    cli = CLI_PATH.read_text(encoding="utf-8")

    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in skip_workflow
    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in scheduled_workflow
    assert "telegram_multichannel_cli skip-expired" in skip_workflow
    assert "telegram_multichannel_cli skip-expired" in scheduled_workflow
    assert "max_lag_minutes = _configured_max_publication_lag_minutes()" in cli
    assert "skip_expired_pending_by_freshness" in cli
