"""Fail closed before quote-v4 production mutates the shared LordChrist state.

A prior approved queue can later be shown to contain unsafe source attributions.
An immutable editorial hold revokes provider execution for that exact edition
without altering the signed queue, activation, scheduled slots or old receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "video-channel-manager.lordchrist-quote-editorial-safety-hold"
EXPECTED_RELEASE = "lordchrist-puritan-spurgeon-v4"
EXPECTED_STATUS = "blocked_pending_full_source_collation"


class QuoteEditorialHold(RuntimeError):
    """The exact v4 queue is prohibited from any provider/state mutation."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuoteEditorialHold(f"Missing or unreadable editorial evidence: {path}") from exc
    if not isinstance(data, dict):
        raise QuoteEditorialHold(f"Invalid editorial evidence structure: {path}")
    return data


def require_quote_v4_editorial_release(*, hold_path: Path, activation_path: Path, queue_path: Path) -> None:
    """Return only when v4 has a new, explicit authorization path.

    v4 is currently disallowed. A newer release must introduce its own
    approval and a separately reviewed transition of this guard, not a
    silent change to a previously signed manifest.
    """
    hold = _load_json(hold_path)
    activation = _load_json(activation_path)
    try:
        exact = queue_path.read_bytes().replace(b"\r\n", b"\n")
    except OSError as exc:
        raise QuoteEditorialHold(f"Cannot verify exact queued material: {queue_path}") from exc

    actual_sha = "sha256:" + hashlib.sha256(exact).hexdigest()
    expected = {
        "schema_name": EXPECTED_SCHEMA,
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "channel_username": "@lordchrist",
        "release_id": EXPECTED_RELEASE,
        "queue_digest": activation.get("queue_digest"),
        "approved_queue_file_sha256": actual_sha,
        "status": EXPECTED_STATUS,
    }
    for field, value in expected.items():
        if hold.get(field) != value:
            raise QuoteEditorialHold(f"Editorial hold field {field} does not match the exact release; fail closed")
    if activation.get("release_id") != EXPECTED_RELEASE or activation.get("provider_writes_authorized") is not True:
        raise QuoteEditorialHold("Quote activation differs from reviewed v4; fail closed")

    raise QuoteEditorialHold(
        "EDITORIAL QUALITY HOLD: quote-v4 publication is prohibited pending "
        "new source-grounded approval; PR #764 and issue #762. "
        "No provider mutation or state initialization is permitted."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed LordChrist quote-v4 quality safety hold")
    parser.add_argument("--hold", required=True, type=Path)
    parser.add_argument("--activation", required=True, type=Path)
    parser.add_argument("--queue", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        require_quote_v4_editorial_release(hold_path=args.hold, activation_path=args.activation, queue_path=args.queue)
    except QuoteEditorialHold as exc:
        print(str(exc), file=sys.stderr)
        return 23
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
