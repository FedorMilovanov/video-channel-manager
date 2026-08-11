from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue, load_release
from video_channel_manager.telegram_multichannel_state import (
    GenericPublicationLedger,
    load_ledger,
    publication_window,
    strict_next_item,
    verify_ledger_against_release,
)

DEFAULT_MAX_LAG_MINUTES = 120


@dataclass(frozen=True)
class FreshnessDecision:
    eligible: bool
    reason: str
    publication_id: str | None
    scheduled_at_utc: datetime | None
    deadline_utc: datetime | None


def publication_deadline(
    release: GenericReleaseQueue,
    publication_id: str,
    *,
    max_lag_minutes: int = DEFAULT_MAX_LAG_MINUTES,
) -> datetime:
    if not 1 <= max_lag_minutes <= 360:
        raise ValueError("max publication lag must be between 1 and 360 minutes")

    item = next((candidate for candidate in release.items if candidate.publication_id == publication_id), None)
    if item is None:
        raise ValueError(f"publication is absent from immutable release: {publication_id}")

    scheduled = item.scheduled_at.astimezone(UTC)
    _, state_window_end = publication_window(release, publication_id)
    return min(state_window_end, scheduled + timedelta(minutes=max_lag_minutes))


def publication_freshness(
    release: GenericReleaseQueue,
    publication_id: str,
    *,
    now: datetime,
    max_lag_minutes: int = DEFAULT_MAX_LAG_MINUTES,
) -> FreshnessDecision:
    if now.tzinfo is None:
        raise ValueError("freshness timestamp must be timezone-aware")

    item = next((candidate for candidate in release.items if candidate.publication_id == publication_id), None)
    if item is None:
        raise ValueError(f"publication is absent from immutable release: {publication_id}")

    effective_now = now.astimezone(UTC)
    scheduled = item.scheduled_at.astimezone(UTC)
    deadline = publication_deadline(
        release,
        publication_id,
        max_lag_minutes=max_lag_minutes,
    )

    if effective_now < scheduled:
        return FreshnessDecision(False, "publication_not_due", publication_id, scheduled, deadline)
    if effective_now >= deadline:
        return FreshnessDecision(False, "publication_too_stale", publication_id, scheduled, deadline)
    return FreshnessDecision(True, "publication_fresh", publication_id, scheduled, deadline)


def skip_expired_pending_by_freshness(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    *,
    now: datetime | None = None,
    max_lag_minutes: int = DEFAULT_MAX_LAG_MINUTES,
) -> tuple[str, ...]:
    """Skip strict-next pending items exactly when their dispatch freshness expires.

    This is intentionally opt-in for callers that also enforce the same bounded
    publication freshness before provider mutation. Legacy window-only recovery
    remains available in ``telegram_multichannel_state.skip_expired_pending``.
    """

    effective_now = now or datetime.now(tz=UTC)
    if effective_now.tzinfo is None:
        raise ValueError("stale-publication check timestamp must be timezone-aware")
    effective_now = effective_now.astimezone(UTC)
    verify_ledger_against_release(ledger, release)

    skipped: list[str] = []
    for item in release.items:
        entry = ledger.entries[item.publication_id]
        if entry.state in {"published", "skipped"}:
            continue
        if entry.state != "pending":
            break

        deadline = publication_deadline(
            release,
            item.publication_id,
            max_lag_minutes=max_lag_minutes,
        )
        if effective_now < deadline:
            break

        entry.state = "skipped"
        entry.provider_effect = "impossible"
        entry.last_error = f"publication freshness deadline expired at {deadline.isoformat()} before dispatch"
        skipped.append(item.publication_id)
    return tuple(skipped)


def _freshness_after_recoverable_stale_predecessors(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    *,
    now: datetime,
    expected_publication_id: str,
    max_lag_minutes: int,
) -> FreshnessDecision:
    """Preview exact-manual strict-next semantics without mutating durable state."""

    verify_ledger_against_release(ledger, release)
    for item in release.items:
        entry = ledger.entries[item.publication_id]
        if entry.state in {"published", "skipped"}:
            continue
        if entry.state != "pending":
            return FreshnessDecision(
                False,
                f"strict queue blocked by {item.publication_id} in state {entry.state}",
                item.publication_id,
                item.scheduled_at.astimezone(UTC),
                None,
            )

        decision = publication_freshness(
            release,
            item.publication_id,
            now=now,
            max_lag_minutes=max_lag_minutes,
        )
        if item.publication_id == expected_publication_id:
            return decision
        if decision.reason == "publication_too_stale":
            continue
        return FreshnessDecision(
            False,
            "requested_publication_is_not_strict_next",
            item.publication_id,
            item.scheduled_at.astimezone(UTC),
            decision.deadline_utc,
        )

    return FreshnessDecision(False, "release_complete_after_stale_recovery", None, None, None)


def next_publication_freshness(
    release: GenericReleaseQueue,
    ledger: GenericPublicationLedger,
    *,
    now: datetime,
    expected_publication_id: str | None = None,
    max_lag_minutes: int = DEFAULT_MAX_LAG_MINUTES,
    recover_stale_predecessors: bool = False,
) -> FreshnessDecision:
    if recover_stale_predecessors:
        if expected_publication_id is None:
            raise ValueError("stale predecessor recovery preview requires an exact publication_id")
        return _freshness_after_recoverable_stale_predecessors(
            release,
            ledger,
            now=now,
            expected_publication_id=expected_publication_id,
            max_lag_minutes=max_lag_minutes,
        )

    item, reason = strict_next_item(release, ledger)
    if item is None:
        return FreshnessDecision(False, reason, None, None, None)
    if expected_publication_id is not None and item.publication_id != expected_publication_id:
        return FreshnessDecision(
            False,
            "requested_publication_is_not_strict_next",
            item.publication_id,
            item.scheduled_at.astimezone(UTC),
            None,
        )
    return publication_freshness(
        release,
        item.publication_id,
        now=now,
        max_lag_minutes=max_lag_minutes,
    )


def _decision_json(decision: FreshnessDecision) -> str:
    return json.dumps(
        {
            "eligible": decision.eligible,
            "reason": decision.reason,
            "publication_id": decision.publication_id,
            "scheduled_at_utc": decision.scheduled_at_utc.isoformat() if decision.scheduled_at_utc else None,
            "deadline_utc": decision.deadline_utc.isoformat() if decision.deadline_utc else None,
        },
        ensure_ascii=False,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Bound Telegram publication lateness before provider access")
    sub = root.add_subparsers(dest="command", required=True)

    item = sub.add_parser("item")
    item.add_argument("--release", type=Path, required=True)
    item.add_argument("--publication-id", required=True)
    item.add_argument("--max-lag-minutes", type=int, default=DEFAULT_MAX_LAG_MINUTES)

    next_item = sub.add_parser("next")
    next_item.add_argument("--release", type=Path, required=True)
    next_item.add_argument("--ledger", type=Path, required=True)
    next_item.add_argument("--publication-id")
    next_item.add_argument("--max-lag-minutes", type=int, default=DEFAULT_MAX_LAG_MINUTES)
    next_item.add_argument(
        "--recover-stale-predecessors",
        action="store_true",
        help="Preview through only bounded-stale pending predecessors before an exact requested publication.",
    )
    return root


def main() -> int:
    args = parser().parse_args()
    release = load_release(args.release)
    now = datetime.now(tz=UTC)

    if args.command == "item":
        decision = publication_freshness(
            release,
            args.publication_id,
            now=now,
            max_lag_minutes=args.max_lag_minutes,
        )
    elif args.command == "next":
        ledger = load_ledger(args.ledger, release)
        decision = next_publication_freshness(
            release,
            ledger,
            now=now,
            expected_publication_id=args.publication_id,
            max_lag_minutes=args.max_lag_minutes,
            recover_stale_predecessors=args.recover_stale_predecessors,
        )
    else:
        raise AssertionError(f"unhandled freshness command: {args.command}")

    print(_decision_json(decision))
    return 0 if decision.eligible else 3


if __name__ == "__main__":
    raise SystemExit(main())
