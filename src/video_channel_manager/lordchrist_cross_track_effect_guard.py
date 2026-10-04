from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from video_channel_manager.lordchrist_research_retirement import load_lordchrist_research_retirement
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_models import TelegramLedger
from video_channel_manager.telegram_multichannel_state import GenericPublicationLedger
from video_channel_manager.telegram_state import load_ledger as load_legacy_ledger
from video_channel_manager.telegram_state import load_queue as load_legacy_queue

SUCCESSOR_QUEUE_DIGEST = "sha256:6c9835793785570311108eec21fd1468aa83e0c45cf63eb554d0f6b9cb7d0873"
SUCCESSOR_LEDGER_FILENAME = "successor-publication-ledger.json"
SUCCESSOR_ENTRY_COUNT = 60
DEPTH_QUEUE_DIGEST = "sha256:c2ad28bb96e88a9e0633c4b7a55d6033bbf29c5a557e1aa4478cc2e0359e3441"
DEPTH_LEDGER_FILENAME = "successor-depth-v2-publication-ledger.json"
DEPTH_PUBLICATION_PREFIX = "lordchrist-successor-depth-v2-"
DEPTH_HISTORY_COUNT = 14
DEPTH_FUTURE_COUNT = 46


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
    retired_publication_ids: frozenset[str] | None = None,
) -> tuple[str, ...]:
    retired = retired_publication_ids or frozenset()
    return tuple(
        sorted(
            entry.publication_id
            for entry in entries
            if (entry.state == "dispatching" or entry.provider_effect == "may_exist")
            and entry.publication_id not in retired
        )
    )


def require_no_unresolved_provider_effects_across_tracks(
    *,
    tracks: Mapping[str, Iterable[EffectEntry]],
    retired_publication_ids_by_track: Mapping[str, frozenset[str]] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Fail closed when any LordChrist writer track has an unresolved provider effect.

    Track names are diagnostic labels only; they do not select provider identity.
    Every future LordChrist writer can use this helper to participate in one
    channel-wide no-blind-replay barrier without teaching this module about each
    new queue implementation.
    """

    retired_by_track = retired_publication_ids_by_track or {}
    unresolved: dict[str, tuple[str, ...]] = {}
    for track, entries in tracks.items():
        if not track or any(character.isspace() for character in track):
            raise ValueError("LordChrist effect-guard track names must be non-empty and whitespace-free")
        unresolved[track] = unresolved_provider_effect_ids(
            entries,
            retired_publication_ids=retired_by_track.get(track),
        )
    blocked = [(track, ids) for track, ids in unresolved.items() if ids]
    if blocked:
        parts = [f"{track}=" + ",".join(ids) for track, ids in blocked]
        raise ValueError("unresolved Lordchrist provider effect blocks all writers: " + " ".join(parts))
    return unresolved


def require_no_unresolved_provider_effects(
    *,
    legacy_entries: Iterable[EffectEntry],
    research_entries: Iterable[EffectEntry],
    retired_research_publication_ids: frozenset[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    result = require_no_unresolved_provider_effects_across_tracks(
        tracks={
            "legacy": legacy_entries,
            "research": research_entries,
        },
        retired_publication_ids_by_track={
            "research": retired_research_publication_ids or frozenset(),
        },
    )
    return {"legacy": result["legacy"], "research": result["research"]}


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


def load_optional_successor_ledger(
    path: Path,
    *,
    profile: TelegramChannelProfile,
) -> TelegramLedger | None:
    """Load the exact sealed-successor state as a channel-wide effect track.

    The ledger may legitimately be absent before predecessor completion. Once it
    exists, an unknown or partial queue identity is a hard failure rather than a
    reason to ignore state that may carry a provider effect.
    """

    if not path.exists():
        return None
    try:
        ledger = TelegramLedger.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Lordchrist successor ledger {path}: {exc}") from exc
    if ledger.project_key != profile.project_key:
        raise ValueError("successor ledger project differs from canonical Lordchrist profile")
    if ledger.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("successor ledger channel differs from canonical Lordchrist profile")
    if ledger.queue_digest != SUCCESSOR_QUEUE_DIGEST:
        raise ValueError("successor ledger queue digest differs from the sealed reviewed successor release")
    if len(ledger.entries) != SUCCESSOR_ENTRY_COUNT or any(
        not publication_id.startswith("lordchrist-successor-") for publication_id in ledger.entries
    ):
        raise ValueError("successor ledger coverage differs from the sealed reviewed successor release")
    return ledger


def load_optional_depth_ledger(
    path: Path,
    *,
    profile: TelegramChannelProfile,
) -> TelegramLedger | None:
    # Load the exact depth-v2 state as a channel-wide provider-effect track.

    if not path.exists():
        return None
    try:
        ledger = TelegramLedger.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid Lordchrist depth-v2 ledger {path}: {exc}") from exc
    if ledger.project_key != profile.project_key:
        raise ValueError("depth-v2 ledger project differs from canonical Lordchrist profile")
    if ledger.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("depth-v2 ledger channel differs from canonical Lordchrist profile")
    if ledger.queue_digest != DEPTH_QUEUE_DIGEST:
        raise ValueError("depth-v2 ledger queue digest differs from the reviewed depth-v2 release")
    depth_ids = [
        publication_id for publication_id in ledger.entries if publication_id.startswith(DEPTH_PUBLICATION_PREFIX)
    ]
    history_ids = [
        publication_id for publication_id in ledger.entries if not publication_id.startswith(DEPTH_PUBLICATION_PREFIX)
    ]
    if (
        len(ledger.entries) != SUCCESSOR_ENTRY_COUNT
        or len(depth_ids) != DEPTH_FUTURE_COUNT
        or len(history_ids) != DEPTH_HISTORY_COUNT
        or any(not publication_id.startswith("lordchrist-successor-") for publication_id in history_ids)
    ):
        raise ValueError("depth-v2 ledger coverage differs from the reviewed 14-history/46-future release")
    return ledger


def _load_active_queue_or_fail_closed(path: Path, *, label: str) -> Any:
    """Load the caller-supplied queue with the same union loader the runtime uses.

    The legacy track must never be inferred from an artifact whose schema is a
    generated successor runtime queue: that would bind the channel-wide effect
    barrier to the wrong ledger and report a schema error instead of an identity
    error. Unknown queue identities fail closed here.
    """

    from video_channel_manager.telegram_quote_runtime import load_active_queue

    try:
        return load_active_queue(path)
    except ValueError as exc:
        raise ValueError(f"invalid {label} {path}: {exc}") from exc


def require_no_cross_track_unresolved_effects(
    *,
    profile_path: Path,
    legacy_queue_path: Path,
    legacy_ledger_path: Path,
    research_ledger_path: Path,
) -> dict[str, object]:
    # After the quote handoff the active --queue path is a generated successor
    # runtime artifact. The channel-wide effect barrier must still inspect the
    # immutable predecessor ledger as its legacy track; explicit workflow-bound
    # paths keep that identity stable and fail closed if only one is supplied.
    predecessor_queue_raw = os.environ.get("LORDCHRIST_PREDECESSOR_QUEUE_PATH", "").strip()
    predecessor_ledger_raw = os.environ.get("LORDCHRIST_PREDECESSOR_LEDGER_PATH", "").strip()
    if bool(predecessor_queue_raw) != bool(predecessor_ledger_raw):
        raise ValueError("LordChrist predecessor guard paths must be configured together")

    from video_channel_manager.telegram_quote_runtime import SuccessorRuntimeQueue

    if predecessor_queue_raw:
        legacy_queue_path = Path(predecessor_queue_raw)
        legacy_ledger_path = Path(predecessor_ledger_raw)
        research_ledger_path = legacy_ledger_path.parent / "research-v2/publication-ledger.json"
        legacy_queue = load_legacy_queue(legacy_queue_path)
    else:
        active_queue = _load_active_queue_or_fail_closed(legacy_queue_path, label="active Telegram queue")
        if isinstance(active_queue, SuccessorRuntimeQueue):
            raise ValueError(
                "the active queue is a generated successor runtime artifact, so the predecessor effect track "
                "cannot be read from it; bind LORDCHRIST_PREDECESSOR_QUEUE_PATH and "
                "LORDCHRIST_PREDECESSOR_LEDGER_PATH to the exact predecessor artifacts"
            )
        legacy_queue = active_queue

    profile = load_channel_profile(profile_path)
    legacy_ledger = load_legacy_ledger(legacy_ledger_path, legacy_queue)
    if legacy_ledger.project_key != profile.project_key:
        raise ValueError("legacy ledger project differs from canonical Lordchrist profile")
    if legacy_ledger.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("legacy ledger channel differs from canonical Lordchrist profile")

    research_ledger = load_optional_research_ledger(research_ledger_path, profile=profile)
    successor_ledger_path = legacy_ledger_path.parent / SUCCESSOR_LEDGER_FILENAME
    successor_ledger = load_optional_successor_ledger(successor_ledger_path, profile=profile)
    depth_ledger_path = legacy_ledger_path.parent / DEPTH_LEDGER_FILENAME
    depth_ledger = load_optional_depth_ledger(depth_ledger_path, profile=profile)

    retirement = None
    retired_research_publication_ids: frozenset[str] = frozenset()
    if research_ledger is not None:
        retirement_path = research_ledger_path.parent / "retirement.json"
        if retirement_path.exists():
            retirement = load_lordchrist_research_retirement(retirement_path, ledger=research_ledger)
            retired_research_publication_ids = frozenset({retirement.publication_id})

    blockers = require_no_unresolved_provider_effects_across_tracks(
        tracks={
            "legacy": legacy_ledger.entries.values(),
            "research": research_ledger.entries.values() if research_ledger is not None else (),
            "successor": successor_ledger.entries.values() if successor_ledger is not None else (),
            "depth_v2": depth_ledger.entries.values() if depth_ledger is not None else (),
        },
        retired_publication_ids_by_track={
            "research": retired_research_publication_ids,
        },
    )
    return {
        "clear": True,
        "research_ledger_present": research_ledger is not None,
        "successor_ledger_present": successor_ledger is not None,
        "depth_v2_ledger_present": depth_ledger is not None,
        "legacy_unresolved": list(blockers["legacy"]),
        "research_unresolved": list(blockers["research"]),
        "successor_unresolved": list(blockers["successor"]),
        "depth_v2_unresolved": list(blockers["depth_v2"]),
        "retired_research_publications": sorted(retired_research_publication_ids),
        "research_retirement_issue": retirement.owning_issue if retirement is not None else None,
    }
