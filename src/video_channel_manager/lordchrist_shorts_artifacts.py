from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from video_channel_manager.lordchrist_shorts import (
    _load_audit,
    _write_model,
    build_backlog_status,
    load_bindings,
    load_candidate_approval,
    load_historical_baseline,
    load_inventory,
    load_media_acceptance,
    reconcile_historical_baseline,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Provider-inert LordChrist Shorts artifact reconciliation and backlog reporting."
    )
    sub = root.add_subparsers(dest="command", required=True)

    reconcile = sub.add_parser("reconcile-baseline")
    reconcile.add_argument("--audit", type=Path, required=True)
    reconcile.add_argument("--baseline", type=Path, required=True)
    reconcile.add_argument("--output", type=Path, required=True)
    reconcile.add_argument("--max-age-hours", type=int, default=48)

    backlog = sub.add_parser("backlog-status")
    backlog.add_argument("--inventory", type=Path, required=True)
    backlog.add_argument("--output", type=Path, required=True)
    backlog.add_argument("--bindings", type=Path)
    backlog.add_argument("--media", type=Path)
    backlog.add_argument("--candidate-approval", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "reconcile-baseline":
            package = _load_audit(args.audit)
            baseline, digest = load_historical_baseline(args.baseline)
            result = reconcile_historical_baseline(
                package,
                baseline,
                source_baseline_sha256=digest,
                max_age_hours=args.max_age_hours,
            )
            _write_model(args.output, result)
            print(
                json.dumps(
                    {
                        "historical_item_count": result.counts.historical_item_count,
                        "present_as_short": result.counts.present_as_short,
                        "present_as_candidate": result.counts.present_as_candidate,
                        "present_as_longform": result.counts.present_as_longform,
                        "present_unresolved": result.counts.present_unresolved,
                        "absent_from_snapshot": result.counts.absent_from_snapshot,
                        "new_shorts_not_in_baseline": result.counts.new_shorts_not_in_baseline,
                        "new_candidates_not_in_baseline": result.counts.new_candidates_not_in_baseline,
                        "compared_snapshot_id": result.compared_snapshot_id,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command == "backlog-status":
            inventory = load_inventory(args.inventory)
            status = build_backlog_status(
                inventory,
                bindings=load_bindings(args.bindings) if args.bindings else None,
                acceptance=load_media_acceptance(args.media) if args.media else None,
                candidate_approval=(
                    load_candidate_approval(args.candidate_approval) if args.candidate_approval else None
                ),
            )
            _write_model(args.output, status)
            print(
                json.dumps(
                    {
                        "inventory_item_count": status.counts.inventory_item_count,
                        "accepted": status.counts.accepted,
                        "media_missing": status.counts.media_missing,
                        "candidate_unconfirmed": status.counts.candidate_unconfirmed,
                        "release_authorized": status.release_authorized,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
