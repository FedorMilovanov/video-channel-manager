from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

from pydantic import ValidationError

from video_channel_manager.lordchrist_research_retirement import load_lordchrist_research_retirement
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_state import GenericPublicationLedger
from video_channel_manager.telegram_state import load_ledger as load_legacy_ledger
from video_channel_manager.telegram_state import load_queue as load_legacy_queue


class EffectEntry(Protocol):
    @property
    def publication_id(self) -> str: ...

    @property
    def state(self) -> str: ...

    @property
    def provider_effect(self) -> str: ...


def unresolved_provider_effect_ids(
    entries: Iterable[EffectEntry],
    *,
    retired_publication_ids: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    return tuple(
        sorted(
            entry.publication_id
            for entry in entries
            if (entry.state == "dispatching" or entry.provider_effect == "may_exist")
            and entry.publication_id not in retired_publication_ids
        )
    )


def require_no_unresolved_provider_effects(
    *,
    legacy_entries: Iterable[EffectEntry],
    research_entries: Iterable[EffectEntry],
    retired_research_publication_ids: frozenset[str] = frozenset(),
) -> dict[str, tuple[str, ...]]:
    legacy = unresolved_provider_effect_ids(legacy_entries)
    research = unresolved_provider_effect_ids(
        research_entries,
        retired_publication_ids=retired_research_publication_ids,
    )
    if legacy or research:
        parts: list[str] = []
        if legacy:
            parts.append("legacy=" + ",".join(legacy))
        if research:
            parts.append("research=" + ",".join(research))
        raise ValueError("unresolved Lordchrist provider effect blocks all writers: " + " ".join(parts))
    return {"legacy": legacy, "research": research}


def load_optional_research_ledger(
    path: Path,
    *,
    profile: TelegramChannelProfile,
) -> GenericPublicationLedger | None:
    if not path.exists():
        return None
    try:
        ledger = GenericPublicationLedger.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Lordchrist research ledger {path}: {exc}") from exc
    if ledger.project_key != profile.project_key:
        raise ValueError("research ledger project differs from canonical Lordchrist profile")
    if ledger.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("research ledger channel differs from canonical Lordchrist profile")
    if ledger.profile_sha256 != profile.digest:
        raise ValueError("research ledger profile digest differs from canonical Lordchrist profile")
    return ledger


def require_no_cross_track_unresolved_effects(
    *,
    profile_path: Path,
    legacy_queue_path: Path,
    legacy_ledger_path: Path,
    research_ledger_path: Path,
) -> dict[str, object]:
    profile = load_channel_profile(profile_path)
    legacy_queue = load_legacy_queue(legacy_queue_path)
    legacy_ledger = load_legacy_ledger(legacy_ledger_path, legacy_queue)
    if legacy_ledger.project_key != profile.project_key:
        raise ValueError("legacy ledger project differs from canonical Lordchrist profile")
    if legacy_ledger.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("legacy ledger channel differs from canonical Lordchrist profile")

    research_ledger = load_optional_research_ledger(research_ledger_path, profile=profile)
    retirement = None
    retired_research_publication_ids: frozenset[str] = frozenset()
    if research_ledger is not None:
        retirement_path = research_ledger_path.parent / "retirement.json"
        if retirement_path.exists():
            retirement = load_lordchrist_research_retirement(retirement_path, ledger=research_ledger)
            retired_research_publication_ids = frozenset({retirement.publication_id})

    blockers = require_no_unresolved_provider_effects(
        legacy_entries=legacy_ledger.entries.values(),
        research_entries=research_ledger.entries.values() if research_ledger is not None else (),
        retired_research_publication_ids=retired_research_publication_ids,
    )
    return {
        "clear": True,
        "research_ledger_present": research_ledger is not None,
        "legacy_unresolved": list(blockers["legacy"]),
        "research_unresolved": list(blockers["research"]),
        "retired_research_publications": sorted(retired_research_publication_ids),
        "research_retirement_issue": retirement.owning_issue if retirement is not None else None,
    }
