from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_cross_track_effect_guard import (
    require_no_cross_track_unresolved_effects,
    require_no_unresolved_provider_effects,
    unresolved_provider_effect_ids,
)
from video_channel_manager.telegram_presentation import load_presentation_policy

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_GUARD = ROOT / "src/video_channel_manager/lordchrist_research_cross_track_guard.py"
LEGACY_CLI = ROOT / "src/video_channel_manager/telegram_cli.py"


@dataclass(frozen=True)
class Entry:
    publication_id: str
    state: str
    provider_effect: str


def test_unresolved_effect_detection_is_symmetric() -> None:
    safe = Entry("safe", "published", "verified")
    legacy_unknown = Entry("legacy-unknown", "dispatching", "may_exist")
    research_unknown = Entry("research-unknown", "dispatching", "may_exist")

    assert unresolved_provider_effect_ids([safe]) == ()
    assert unresolved_provider_effect_ids([safe, legacy_unknown]) == ("legacy-unknown",)

    with pytest.raises(ValueError, match=r"legacy=legacy-unknown"):
        require_no_unresolved_provider_effects(
            legacy_entries=[legacy_unknown],
            research_entries=[safe],
        )
    with pytest.raises(ValueError, match=r"research=research-unknown"):
        require_no_unresolved_provider_effects(
            legacy_entries=[safe],
            research_entries=[research_unknown],
        )


def test_confirmed_absent_and_pending_states_do_not_false_block() -> None:
    entries = [
        Entry("pending", "pending", "impossible"),
        Entry("retry", "pending", "confirmed_absent"),
        Entry("published", "published", "verified"),
    ]
    result = require_no_unresolved_provider_effects(legacy_entries=entries, research_entries=entries)
    assert result == {"legacy": (), "research": ()}


def test_research_daily_guard_checks_effects_before_quota_decision() -> None:
    source = RESEARCH_GUARD.read_text(encoding="utf-8")
    unresolved = source.index("require_no_unresolved_provider_effects(")
    quota = source.index("legacy_verified = verified_on_date")
    assert unresolved < quota


def test_legacy_validate_and_preflight_guard_before_provider_access() -> None:
    source = LEGACY_CLI.read_text(encoding="utf-8")
    validate = source.index('if args.command == "validate":')
    validate_guard = source.index("cross_track = _cross_track_guard", validate)
    preflight = source.index('if args.command == "preflight":')
    preflight_guard = source.index("_cross_track_guard(args.queue, args.ledger)", preflight)
    provider = source.index("proof = preflight_target", preflight)
    resolve = source.index('if args.command == "resolve":')
    assert validate < validate_guard < preflight < preflight_guard < provider < resolve
    assert "_cross_track_guard" not in source[resolve:]


def _depth_runtime_queue_path(tmp_path: Path) -> Path:
    from video_channel_manager.telegram_quote_depth import build_depth_runtime_queue

    content = ROOT / "content/telegram/lordchrist"
    queue = build_depth_runtime_queue(
        candidate_path=content / "successor-quotes-v1.json",
        translation_ledger_path=content / "successor-translation-ledger-v1.json",
        integrity_amendment_path=content / "successor-integrity-amendments-v1.json",
    )
    path = tmp_path / "lordchrist-successor-depth-v2-runtime-queue.json"
    path.write_text(queue.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def test_generated_successor_queue_requires_an_exact_predecessor_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated successor queue must never be read as the legacy predecessor track."""

    monkeypatch.delenv("LORDCHRIST_PREDECESSOR_QUEUE_PATH", raising=False)
    monkeypatch.delenv("LORDCHRIST_PREDECESSOR_LEDGER_PATH", raising=False)
    active_queue = _depth_runtime_queue_path(tmp_path)

    with pytest.raises(ValueError, match="bind LORDCHRIST_PREDECESSOR_QUEUE_PATH"):
        require_no_cross_track_unresolved_effects(
            profile_path=ROOT / "content/telegram/channels/lordchrist.json",
            legacy_queue_path=active_queue,
            legacy_ledger_path=tmp_path / "successor-depth-v2-publication-ledger.json",
            research_ledger_path=tmp_path / "research-v2/publication-ledger.json",
        )


def test_bound_predecessor_track_inspects_a_generated_successor_active_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the exact binding, the barrier still checks the successor track."""

    from datetime import UTC, datetime

    from video_channel_manager.telegram_models import LedgerEntry
    from video_channel_manager.telegram_quote_runtime import build_successor_runtime_queue
    from video_channel_manager.telegram_state import initialize_ledger, load_queue

    content = ROOT / "content/telegram/lordchrist"
    predecessor = load_queue(content / "verified-30-posts.json")
    predecessor_ledger_path = tmp_path / "publication-ledger.json"
    predecessor_ledger_path.write_text(
        initialize_ledger(predecessor).model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    policy = load_presentation_policy(content / "presentation-policy.json")
    successor = build_successor_runtime_queue(
        candidate_path=content / "successor-quotes-v1.json",
        translation_ledger_path=content / "successor-translation-ledger-v1.json",
        integrity_amendment_path=content / "successor-integrity-amendments-v1.json",
        release_path=content / "successor-release-v2.json",
        activation_path=content / "successor-activation-v1.json",
        expected_chat_id=-1001295216957,
        expected_bot_id=8716602202,
        expected_bot_username="preaching_mp3_bot",
        presentation_policy_id=policy.policy_id,
        presentation_policy_sha256=policy.digest,
    )
    successor_ledger = initialize_ledger(successor)  # type: ignore[arg-type]
    post = successor.posts[0]
    successor_ledger.entries[post.publication_id] = LedgerEntry(
        publication_id=post.publication_id,
        payload_sha256=post.payload_sha256,
        state="dispatching",
        provider_effect="may_exist",
        intent_id="e" * 32,
        dispatch_mode="scheduled",
        scheduled_slot="morning",
        workflow_run_id="42",
        workflow_run_attempt="1",
        github_sha="e" * 40,
        github_workflow_sha="f" * 40,
        attempted_at_utc=datetime(2026, 9, 10, 8, 0, tzinfo=UTC),
        actual_chat_id=-1001295216957,
        actual_chat_username="lordchrist",
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
    )
    successor_ledger_path = tmp_path / "successor-publication-ledger.json"
    successor_ledger_path.write_text(successor_ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")

    active_queue_path = tmp_path / "active-successor-runtime-queue.json"
    active_queue_path.write_text(successor.model_dump_json(indent=2) + "\n", encoding="utf-8")
    monkeypatch.setenv("LORDCHRIST_PREDECESSOR_QUEUE_PATH", str(content / "verified-30-posts.json"))
    monkeypatch.setenv("LORDCHRIST_PREDECESSOR_LEDGER_PATH", str(predecessor_ledger_path))

    with pytest.raises(ValueError, match=r"successor=.*lordchrist-successor-"):
        require_no_cross_track_unresolved_effects(
            profile_path=ROOT / "content/telegram/channels/lordchrist.json",
            legacy_queue_path=active_queue_path,
            legacy_ledger_path=successor_ledger_path,
            research_ledger_path=tmp_path / "research-v2/publication-ledger.json",
        )
