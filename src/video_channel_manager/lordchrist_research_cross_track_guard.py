from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable, Protocol, Sequence

from video_channel_manager.lordchrist_research_rollout import load_lordchrist_research_rollout_approval
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import load_ledger as load_research_ledger
from video_channel_manager.telegram_state import (
    load_ledger as load_legacy_ledger,
    load_queue as load_legacy_queue,
    publication_local_date,
)


class VerifiedEntry(Protocol):
    state: str
    provider_effect: str
    published_at_utc: datetime | None


def verified_on_date(entries: Iterable[VerifiedEntry], *, timezone_name: str, local_date: date) -> int:
    return sum(
        1
        for entry in entries
        if entry.state == "published"
        and entry.provider_effect == "verified"
        and entry.published_at_utc is not None
        and publication_local_date(entry.published_at_utc, timezone_name) == local_date
    )


def require_cross_track_capacity(
    *,
    profile_path: Path,
    approval_path: Path,
    legacy_queue_path: Path,
    legacy_ledger_path: Path,
    research_release_path: Path,
    research_ledger_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    profile = load_channel_profile(profile_path)
    approval = load_lordchrist_research_rollout_approval(approval_path)
    release = load_release(research_release_path)
    legacy_queue = load_legacy_queue(legacy_queue_path)
    legacy_ledger = load_legacy_ledger(legacy_ledger_path, legacy_queue)
    research_ledger = load_research_ledger(research_ledger_path, release)

    if profile.daily_verified_limit != approval.per_track_daily_verified_limit:
        raise ValueError("canonical Lordchrist per-track daily limit differs from rollout approval")
    if release.daily_verified_limit != approval.per_track_daily_verified_limit:
        raise ValueError("research release per-track daily limit differs from rollout approval")
    if release.project_key != profile.project_key or release.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("research release differs from canonical Lordchrist channel identity")
    if legacy_ledger.project_key != profile.project_key or legacy_ledger.channel_username.casefold() != profile.channel_username.casefold():
        raise ValueError("legacy ledger differs from canonical Lordchrist channel identity")

    effective_now = (now or datetime.now(tz=UTC)).astimezone(UTC)
    today = publication_local_date(effective_now, profile.timezone)
    legacy_verified = verified_on_date(
        legacy_ledger.entries.values(), timezone_name=profile.timezone, local_date=today
    )
    research_verified = verified_on_date(
        research_ledger.entries.values(), timezone_name=profile.timezone, local_date=today
    )
    total_verified = legacy_verified + research_verified
    limit = approval.cross_track_daily_verified_limit
    return {
        "eligible": total_verified < limit,
        "local_date": today.isoformat(),
        "timezone": profile.timezone,
        "legacy_verified": legacy_verified,
        "research_verified": research_verified,
        "total_verified": total_verified,
        "cross_track_daily_verified_limit": limit,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enforce the explicit Lordchrist legacy + research daily ceiling")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--legacy-queue", type=Path, required=True)
    parser.add_argument("--legacy-ledger", type=Path, required=True)
    parser.add_argument("--research-release", type=Path, required=True)
    parser.add_argument("--research-ledger", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    decision = require_cross_track_capacity(
        profile_path=args.profile,
        approval_path=args.approval,
        legacy_queue_path=args.legacy_queue,
        legacy_ledger_path=args.legacy_ledger,
        research_release_path=args.research_release,
        research_ledger_path=args.research_ledger,
    )
    print(json.dumps(decision, ensure_ascii=False))
    return 0 if decision["eligible"] is True else 3


if __name__ == "__main__":
    raise SystemExit(main())
