"""Exact immutable Milovi 15-video staging and scheduled-due gate (#809).

The module cannot send provider requests. All actual sends are delegated to
the existing canonical single-writer workflow with durable intent protection.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from video_channel_manager.milovi_telegram_feed import (
    state_check,
    state_init,
    validate_bundle,
)

PLAN = Path("content/telegram/milovi-cake/november-muted15-editorial-plan-20261106.json")
EXPECTED_REF = "agent/milovi-video-muted15-80ee7f9fea"
EXPECTED_COMMIT = "9331af0c6015404bfda0cd2c6392066b78dc68b3"
EXACT_FIRST = "milovi-feed-20261108-001"
EXACT_LAST = "milovi-feed-20261122-001"
CHANNEL = "@MiloviCake"
MOSCOW = ZoneInfo("Europe/Moscow")
MAX_LAG = timedelta(minutes=120)


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: " + str(path))
    return value


def reviewed_items() -> list[dict]:
    """Prove all fifteen approved releases and immutable media before state work."""
    doc = _read_json(PLAN)
    if (
        doc.get("schema_name") != "video-channel-manager.milovi-telegram-muted15-editorial-plan"
        or doc.get("target") != CHANNEL
        or doc.get("files_count") != 15
        or doc.get("artifact_ref") != EXPECTED_REF
        or doc.get("artifact_commit") != EXPECTED_COMMIT
        or doc.get("release_authorized") is not True
        or doc.get("execution_authorized") is not True
        or doc.get("provider_mutation_allowed") is not True
        or doc.get("owner_publication_approved") is not True
    ):
        raise ValueError("exact owner-authorized fifteen-video plan has drifted")
    rows = doc.get("items")
    if not isinstance(rows, list) or len(rows) != 15:
        raise ValueError("approved video plan does not contain exactly fifteen items")
    ids, hashes, digests = set(), set(), set()
    for index, row in enumerate(rows):
        day = index + 8
        expected_id = f"milovi-feed-202611{day:02d}-001"
        expected_time = datetime(2026, 11, day, 19, 0, tzinfo=MOSCOW).isoformat()
        if (
            row.get("publication_id") != expected_id
            or row.get("scheduled_at_proposal") != expected_time
            or row.get("owner_publication_approved") is not True
            or row.get("release_authorized") is not True
            or row.get("execution_authorized") is not True
            or row.get("rights_verified") is not True
        ):
            raise ValueError("owner-approved individual video/slot mismatch")
        checked = validate_bundle(expected_id, require_execution_authorized=True)
        if (
            checked["valid"] is not True
            or checked["provider_access_performed"] is not False
            or checked["blockers"]
            or checked["payload_kind"] != "video"
            or checked["release_digest"] != row["release_digest"]
            or checked["release_candidate_sha256"] != row["release_candidate_sha256"]
            or checked["provider_payload_sha256"] != row["provider_payload_sha256"]
        ):
            raise ValueError("exact signed video release differs from reviewed plan")
        ids.add(expected_id)
        hashes.add(row["sha256"])
        digests.add(row["release_digest"])
    if len(ids) != 15 or len(hashes) != 15 or len(digests) != 15:
        raise ValueError("duplicate video IDs, media or release digest")
    if rows[0]["publication_id"] != EXACT_FIRST or rows[-1]["publication_id"] != EXACT_LAST:
        raise ValueError("video sequence does not match exact expected boundaries")
    return rows


def due_row(now: datetime, rows: list[dict]) -> dict | None:
    """Decide only inside one exact 2026 daily 19:00 Moscow two-hour slot."""
    if now.tzinfo is None:
        raise ValueError("current clock must be timezone-aware")
    local = now.astimezone(MOSCOW)
    if local.year != 2026 or local.month != 11 or not 8 <= local.day <= 22:
        return None
    slot = datetime(2026, 11, local.day, 19, 0, tzinfo=MOSCOW)
    if not slot <= local < slot + MAX_LAG:
        return None
    row = rows[local.day - 8]
    if row["publication_id"] != f"milovi-feed-202611{local.day:02d}-001":
        raise ValueError("scheduled day no longer matches reviewed release")
    return row


def exact_state_decision(row: dict, *, checkout: Path) -> bool:
    """Read authoritative ledger/index without changing or initializing anything."""
    pid = row["publication_id"]
    result = state_check(pid, state_checkout=checkout)
    ledger = _read_json(checkout / "content/telegram/milovi-cake/feed" / (pid + ".json"))
    entry = ledger.get("entries", {}).get(pid)
    if not isinstance(entry, dict):
        raise ValueError("missing exact durable state entry")
    if result["state"] == "published" and result["provider_effect"] == "verified":
        if not isinstance(entry.get("message_id"), int) or entry["message_id"] <= 0:
            raise ValueError("published record without verified Telegram receipt")
        if not entry.get("message_url"):
            raise ValueError("published record without message URL")
        return False
    if result["state"] == "pending" and result["provider_effect"] == "impossible":
        if entry.get("intent_id") is not None or entry.get("message_id") is not None:
            raise ValueError("pending record has an unresolved provider intent")
        state_check(pid, state_checkout=checkout, require_publishable=True)
        return True
    raise ValueError("provider state is unresolved; refusing repeat or blind send")


def initialize_all(checkout: Path) -> list[str]:
    """Atomic transaction is committed by the caller only after all 15 succeed."""
    rows = reviewed_items()
    initialized = []
    for row in rows:
        pid = row["publication_id"]
        state_init(pid, state_checkout=checkout)
        checked = state_check(pid, state_checkout=checkout)
        if not checked["valid"]:
            raise ValueError("initialized state does not validate")
        initialized.append(pid)
    return initialized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "initialize-all", "due"))
    parser.add_argument("--state-checkout", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = reviewed_items()
    if args.operation == "initialize-all":
        if args.state_checkout is None:
            raise ValueError("initialization needs exact state checkout")
        ids = initialize_all(args.state_checkout)
        print(json.dumps({"initialized": ids, "count": len(ids), "provider_access": False}))
        return 0
    if args.operation == "validate":
        print(json.dumps({"verified": True, "releases": len(rows), "provider_access": False}))
        return 0
    if args.state_checkout is None or args.output is None:
        raise ValueError("due validation needs exact state checkout and output")
    current = datetime.now(UTC)
    row = due_row(current, rows)
    permit = row is not None and exact_state_decision(row, checkout=args.state_checkout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as out:
        out.write("dispatch=" + ("true" if permit else "false") + "\n")
        if permit:
            out.write("publication_id=" + row["publication_id"] + "\n")
    print(json.dumps({
        "dispatch": permit,
        "publication_id": row["publication_id"] if permit else None,
        "provider_access": False,
        "provider_mutation": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
