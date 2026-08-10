from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from video_channel_manager.lordchrist_cross_track_effect_guard import (
    require_no_unresolved_provider_effects,
    unresolved_provider_effect_ids,
)

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
