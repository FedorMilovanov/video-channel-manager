from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_state import initialize_ledger, skip_expired_pending
from video_channel_manager.telegram_publication_freshness import (
    next_publication_freshness,
    publication_freshness,
)
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"


def _release():
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-freshness-test",
        binding=binding,
    )
    return authorize_svodka_release(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="freshness-test",
        reviewed_at=datetime(2026, 8, 8, tzinfo=UTC),
    )


def test_publication_is_not_eligible_before_its_exact_slot() -> None:
    release = _release()
    first = release.items[0]

    decision = publication_freshness(
        release,
        first.publication_id,
        now=datetime(2026, 8, 9, 7, 29, 59, tzinfo=UTC),
    )

    assert decision.eligible is False
    assert decision.reason == "publication_not_due"


def test_publication_is_eligible_inside_two_hour_grace() -> None:
    release = _release()
    first = release.items[0]

    decision = publication_freshness(
        release,
        first.publication_id,
        now=datetime(2026, 8, 9, 9, 29, 59, tzinfo=UTC),
    )

    assert decision.eligible is True
    assert decision.reason == "publication_fresh"
    assert decision.deadline_utc == datetime(2026, 8, 9, 9, 30, tzinfo=UTC)


def test_publication_is_rejected_at_two_hour_deadline() -> None:
    release = _release()
    first = release.items[0]

    decision = publication_freshness(
        release,
        first.publication_id,
        now=datetime(2026, 8, 9, 9, 30, tzinfo=UTC),
    )

    assert decision.eligible is False
    assert decision.reason == "publication_too_stale"


def test_next_freshness_uses_strict_next_pending_item() -> None:
    release = _release()
    ledger = initialize_ledger(release)
    first_id = release.items[0].publication_id
    ledger.entries[first_id].state = "skipped"
    ledger.entries[first_id].provider_effect = "impossible"

    decision = next_publication_freshness(
        release,
        ledger,
        now=datetime(2026, 8, 9, 16, 30, tzinfo=UTC),
    )

    assert decision.eligible is True
    assert decision.publication_id == release.items[1].publication_id


def test_evening_run_skips_missed_morning_then_sees_evening_as_fresh() -> None:
    release = _release()
    ledger = initialize_ledger(release)
    evening_slot = datetime(2026, 8, 9, 16, 30, tzinfo=UTC)

    skipped = skip_expired_pending(release, ledger, now=evening_slot)
    decision = next_publication_freshness(release, ledger, now=evening_slot)

    assert skipped == (release.items[0].publication_id,)
    assert decision.eligible is True
    assert decision.publication_id == release.items[1].publication_id
    assert decision.reason == "publication_fresh"


def test_final_evening_item_still_expires_after_two_hours_not_midnight() -> None:
    release = _release()
    final = release.items[-1]

    decision = publication_freshness(
        release,
        final.publication_id,
        now=datetime(2026, 8, 15, 18, 30, tzinfo=UTC),
    )

    assert decision.eligible is False
    assert decision.reason == "publication_too_stale"
    assert decision.deadline_utc == datetime(2026, 8, 15, 18, 30, tzinfo=UTC)


def test_next_freshness_rejects_requested_item_that_is_not_strict_next() -> None:
    release = _release()
    ledger = initialize_ledger(release)

    decision = next_publication_freshness(
        release,
        ledger,
        now=datetime(2026, 8, 9, 16, 30, tzinfo=UTC),
        expected_publication_id=release.items[1].publication_id,
    )

    assert decision.eligible is False
    assert decision.reason == "requested_publication_is_not_strict_next"
    assert decision.publication_id == release.items[0].publication_id
