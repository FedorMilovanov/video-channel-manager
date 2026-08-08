from __future__ import annotations

import argparse
import json
from pathlib import Path

from video_channel_manager.telegram_lordchrist_outcome import (
    apply_lordchrist_provider_outcome,
    capture_lordchrist_provider_outcome,
    load_lordchrist_provider_outcome,
)
from video_channel_manager.telegram_presentation import load_presentation_policy, load_rendered_post
from video_channel_manager.telegram_publisher import (
    load_dispatch,
    load_ledger,
    load_queue,
    save_ledger,
    save_model,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Provider-free Lordchrist exact outcome tooling")
    root.add_argument("--queue", type=Path, required=True)
    root.add_argument("--ledger", type=Path, required=True)
    sub = root.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture")
    capture.add_argument("--presentation-policy", type=Path, required=True)
    capture.add_argument("--dispatch", type=Path, required=True)
    capture.add_argument("--rendered", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)

    apply = sub.add_parser("apply")
    apply.add_argument("--dispatch", type=Path, required=True)
    apply.add_argument("--rendered", type=Path, required=True)
    apply.add_argument("--outcome", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    queue = load_queue(args.queue)
    ledger = load_ledger(args.ledger, queue)
    envelope = load_dispatch(args.dispatch)
    rendered = load_rendered_post(args.rendered)

    if args.command == "capture":
        policy = load_presentation_policy(args.presentation_policy)
        entry = ledger.entries.get(envelope.publication_id)
        if entry is None:
            raise ValueError("post-send ledger does not contain the durable dispatch publication")
        outcome = capture_lordchrist_provider_outcome(queue, envelope, rendered, policy, entry)
        save_model(args.output, outcome)
        print(
            json.dumps(
                {
                    "captured": True,
                    "publication_id": outcome.publication_id,
                    "provider_effect": outcome.entry.provider_effect,
                    "state": outcome.entry.state,
                    "message_id": outcome.entry.message_id,
                    "published_at_utc": (
                        outcome.entry.published_at_utc.isoformat() if outcome.entry.published_at_utc else None
                    ),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
        return 0

    outcome = load_lordchrist_provider_outcome(args.outcome)
    entry = apply_lordchrist_provider_outcome(queue, ledger, envelope, rendered, outcome)
    save_ledger(args.ledger, ledger)
    print(
        json.dumps(
            {
                "applied": True,
                "publication_id": entry.publication_id,
                "provider_effect": entry.provider_effect,
                "state": entry.state,
                "message_id": entry.message_id,
                "message_url": entry.message_url,
                "published_at_utc": entry.published_at_utc.isoformat() if entry.published_at_utc else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
