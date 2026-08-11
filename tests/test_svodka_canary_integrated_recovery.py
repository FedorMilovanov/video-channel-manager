from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_cli import (
    _recover_expired_before_exact_manual_prepare,
    parser as generic_parser,
)
from video_channel_manager.telegram_multichannel_state import initialize_ledger
from video_channel_manager.telegram_publication_freshness import (
    next_publication_freshness,
    parser as freshness_parser,
)
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
CANARY_WORKFLOW = ROOT / ".github/workflows/svodka-canary.yml"
MAX_LAG_MINUTES = 120


def _release():
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-integrated-recovery-test",
        binding=binding,
    )
    return authorize_svodka_release(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="integrated-recovery-test",
        reviewed_at=datetime(2026, 8, 8, tzinfo=UTC),
    )


def test_exact_canary_preflight_can_see_through_only_stale_predecessors_without_mutating_ledger() -> None:
    release = _release()
    ledger = initialize_ledger(release)
    requested = release.items[2]
    now = requested.scheduled_at.astimezone(UTC)

    decision = next_publication_freshness(
        release,
        ledger,
        now=now,
        expected_publication_id=requested.publication_id,
        max_lag_minutes=MAX_LAG_MINUTES,
        recover_stale_predecessors=True,
    )

    assert decision.eligible is True
    assert decision.publication_id == requested.publication_id
    assert decision.reason == "publication_fresh"
    assert all(entry.state == "pending" for entry in ledger.entries.values())
    assert all(entry.provider_effect == "impossible" for entry in ledger.entries.values())


def test_generic_exact_preflight_keeps_strict_next_semantics_without_explicit_recovery() -> None:
    release = _release()
    ledger = initialize_ledger(release)
    requested = release.items[2]
    now = requested.scheduled_at.astimezone(UTC)

    decision = next_publication_freshness(
        release,
        ledger,
        now=now,
        expected_publication_id=requested.publication_id,
        max_lag_minutes=MAX_LAG_MINUTES,
    )

    assert decision.eligible is False
    assert decision.reason == "requested_publication_is_not_strict_next"
    assert decision.publication_id == release.items[0].publication_id
    assert all(entry.state == "pending" for entry in ledger.entries.values())


def test_freshness_cli_requires_explicit_recovery_switch() -> None:
    base = [
        "next",
        "--release",
        "release.json",
        "--ledger",
        "ledger.json",
        "--publication-id",
        "svodka-wombat-cubic-poop",
    ]

    normal = freshness_parser().parse_args(base)
    recovery = freshness_parser().parse_args([*base, "--recover-stale-predecessors"])

    assert normal.recover_stale_predecessors is False
    assert recovery.recover_stale_predecessors is True


def test_prepare_cli_requires_explicit_recovery_switch() -> None:
    base = [
        "prepare",
        "--profile",
        "profile.json",
        "--release",
        "release.json",
        "--ledger",
        "ledger.json",
        "--target-proof",
        "target.json",
        "--mode",
        "manual",
        "--publication-id",
        "svodka-wombat-cubic-poop",
        "--run-id",
        "1",
        "--run-attempt",
        "1",
        "--github-sha",
        "a" * 40,
        "--github-workflow-sha",
        "b" * 40,
        "--envelope-output",
        "envelope.json",
    ]

    normal = generic_parser().parse_args(base)
    recovery = generic_parser().parse_args([*base, "--recover-stale-predecessors"])

    assert normal.recover_stale_predecessors is False
    assert recovery.recover_stale_predecessors is True


def test_exact_canary_preflight_still_rejects_wrong_or_premature_requested_item() -> None:
    release = _release()
    ledger = initialize_ledger(release)
    requested = release.items[2]
    now = requested.scheduled_at.astimezone(UTC)

    premature = next_publication_freshness(
        release,
        ledger,
        now=now - timedelta(seconds=1),
        expected_publication_id=requested.publication_id,
        max_lag_minutes=MAX_LAG_MINUTES,
        recover_stale_predecessors=True,
    )
    wrong = next_publication_freshness(
        release,
        ledger,
        now=now,
        expected_publication_id=release.items[3].publication_id,
        max_lag_minutes=MAX_LAG_MINUTES,
        recover_stale_predecessors=True,
    )

    assert premature.eligible is False
    assert premature.reason == "publication_not_due"
    assert premature.publication_id == requested.publication_id
    assert wrong.eligible is False
    assert wrong.reason == "requested_publication_is_not_strict_next"
    assert wrong.publication_id == requested.publication_id
    assert all(entry.state == "pending" for entry in ledger.entries.values())


def test_exact_manual_prepare_recovers_only_expired_predecessors_when_explicitly_enabled(monkeypatch) -> None:
    release = _release()
    ledger = initialize_ledger(release)
    requested = release.items[2]
    now = requested.scheduled_at.astimezone(UTC)
    monkeypatch.setenv("MAX_PUBLICATION_LAG_MINUTES", str(MAX_LAG_MINUTES))

    recovered = _recover_expired_before_exact_manual_prepare(
        release,
        ledger,
        mode="manual",
        expected_publication_id=requested.publication_id,
        recover_stale_predecessors=True,
        now=now,
    )

    assert recovered == (release.items[0].publication_id, release.items[1].publication_id)
    for publication_id in recovered:
        assert ledger.entries[publication_id].state == "skipped"
        assert ledger.entries[publication_id].provider_effect == "impossible"
    assert ledger.entries[requested.publication_id].state == "pending"
    assert ledger.entries[requested.publication_id].provider_effect == "impossible"


def test_prepare_recovery_default_is_noop_even_when_bound_is_configured(monkeypatch) -> None:
    release = _release()
    ledger = initialize_ledger(release)
    requested = release.items[2]
    now = requested.scheduled_at.astimezone(UTC)
    monkeypatch.setenv("MAX_PUBLICATION_LAG_MINUTES", str(MAX_LAG_MINUTES))

    recovered = _recover_expired_before_exact_manual_prepare(
        release,
        ledger,
        mode="manual",
        expected_publication_id=requested.publication_id,
        now=now,
    )

    assert recovered == ()
    assert all(entry.state == "pending" for entry in ledger.entries.values())


def test_explicit_prepare_recovery_fails_without_exact_manual_bound(monkeypatch) -> None:
    release = _release()
    requested = release.items[2]
    now = requested.scheduled_at.astimezone(UTC)

    no_bound = initialize_ledger(release)
    monkeypatch.delenv("MAX_PUBLICATION_LAG_MINUTES", raising=False)
    with pytest.raises(ValueError, match="requires MAX_PUBLICATION_LAG_MINUTES"):
        _recover_expired_before_exact_manual_prepare(
            release,
            no_bound,
            mode="manual",
            expected_publication_id=requested.publication_id,
            recover_stale_predecessors=True,
            now=now,
        )
    assert all(entry.state == "pending" for entry in no_bound.entries.values())

    scheduled = initialize_ledger(release)
    monkeypatch.setenv("MAX_PUBLICATION_LAG_MINUTES", str(MAX_LAG_MINUTES))
    with pytest.raises(ValueError, match="requires exact manual prepare"):
        _recover_expired_before_exact_manual_prepare(
            release,
            scheduled,
            mode="scheduled",
            expected_publication_id=None,
            recover_stale_predecessors=True,
            now=now,
        )
    assert all(entry.state == "pending" for entry in scheduled.entries.values())


def test_existing_canary_workflow_supplies_exact_identity_and_bound_before_durable_intent() -> None:
    workflow = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert "MAX_PUBLICATION_LAG_MINUTES: 120" in workflow
    assert "telegram_publication_freshness next" in workflow
    assert '--publication-id "$REQUESTED_PUBLICATION_ID"' in workflow
    assert workflow.count("--recover-stale-predecessors") == 2
    assert "telegram_multichannel_cli prepare" in workflow
    assert "--mode manual" in workflow
    assert workflow.index("Require fresh strict-next canary window") < workflow.index(
        "Prepare exactly one manual dispatch"
    )
    assert workflow.index("Prepare exactly one manual dispatch") < workflow.index(
        "Persist intent before Telegram mutation"
    )
    assert workflow.index("Persist intent before Telegram mutation") < workflow.index("Send exactly one canary payload")
