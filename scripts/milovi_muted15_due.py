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
    EXPECTED_BOT_ID,
    EXPECTED_BOT_USERNAME,
    EXPECTED_CHAT_ID,
    PROJECT_KEY,
    exact_paths,
    require_never_attempted_pending,
    require_raw_receipt_identifiers,
    state_check,
    state_init,
    validate_bundle,
)
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import load_ledger
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload

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
    if now.tzinfo is None or now.utcoffset() is None:
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


def _require_clean_pending(pid: str, *, checkout: Path) -> None:
    require_never_attempted_pending(pid, state_checkout=checkout)


def _require_exact_verified_receipt(row: dict, *, checkout: Path, as_of: datetime) -> None:
    """Validate recorded terminal evidence, never a live provider read or retry permission.

    The ledger's attempted timestamp is the durable intent/preparation time;
    it does not independently prove when Telegram received the request. A
    verified response can arrive after the lease, but not after ``as_of``.
    """
    pid = row["publication_id"]
    paths = exact_paths(pid)
    release = load_release(paths["release"])
    slot = datetime.fromisoformat(row["scheduled_at_proposal"])
    mismatch = (
        f"video receipt target, message identity or reviewed slot is inconsistent: {pid}; reconcile without replay"
    )
    if not (
        slot.tzinfo is not None
        and slot.utcoffset() is not None
        and len(release.items) == 1
        and release.items[0].publication_id == release.release_id == pid
        and isinstance(release.items[0].payload, GenericVideoPayload)
        and release.items[0].scheduled_at == slot
        and release.project_key == PROJECT_KEY
        and release.channel_username.casefold() == CHANNEL.casefold()
        and release.chat_id == EXPECTED_CHAT_ID
        and release.bot_id == EXPECTED_BOT_ID
        and (release.bot_username or "").casefold() == EXPECTED_BOT_USERNAME.casefold()
        and release.digest == row.get("release_digest")
        and release.candidate_digest() == row.get("release_candidate_sha256")
        and release.items[0].payload.provider_payload_sha256 == row.get("provider_payload_sha256")
    ):
        raise ValueError(mismatch)

    ledger_path = checkout / paths["ledger"]
    require_raw_receipt_identifiers(pid, state_checkout=checkout)
    entry = load_ledger(ledger_path, release).entries[pid]
    username = entry.actual_chat_username
    bot_username = entry.bot_username
    attempted = entry.attempted_at_utc
    verified_at = entry.published_at_utc
    if not (
        entry.state == "published"
        and entry.provider_effect == "verified"
        and entry.message_id is not None
        and entry.message_id > 0
        and entry.actual_chat_id == release.chat_id
        and entry.bot_id == release.bot_id
        and isinstance(username, str)
        and username.casefold() == release.channel_username.lstrip("@").casefold()
        and isinstance(bot_username, str)
        and bot_username.casefold() == (release.bot_username or "").casefold()
        and entry.message_url == f"https://t.me/{username}/{entry.message_id}"
        and attempted is not None
        and slot <= attempted < slot + MAX_LAG
        and verified_at is not None
        and verified_at <= as_of
    ):
        raise ValueError(mismatch)


def exact_state_decision(row: dict, *, checkout: Path, now: datetime | None = None) -> bool:
    """Read authoritative ledger/index without changing or initializing anything."""
    observed_at = now if now is not None else datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("current clock must be timezone-aware")
    pid = row["publication_id"]
    result = state_check(pid, state_checkout=checkout)
    if result["state"] == "published" and result["provider_effect"] == "verified":
        _require_exact_verified_receipt(row, checkout=checkout, as_of=observed_at)
        return False
    if result["state"] == "pending" and result["provider_effect"] == "impossible":
        _require_clean_pending(pid, checkout=checkout)
        state_check(pid, state_checkout=checkout, require_publishable=True)
        return True
    raise ValueError("provider state is unresolved; refusing repeat or blind send")


def missed_delivery_windows(now: datetime, rows: list[dict], *, checkout: Path) -> list[str]:
    """Audit expired owner-approved windows without granting catch-up authority.

    GitHub scheduled events may arrive well after the 19:00-21:00 Moscow
    window. A green due-gate with dispatch=false is not delivery evidence.
    Only previously elapsed exact slots are checked; upcoming items remain
    untouched and the result never authorizes replay.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("overdue audit clock must be timezone-aware")
    clock = now.astimezone(MOSCOW)
    missed: list[str] = []
    for row in rows:
        slot = datetime.fromisoformat(row["scheduled_at_proposal"]).astimezone(MOSCOW)
        if clock < slot + MAX_LAG:
            continue
        pid = row["publication_id"]
        receipt = state_check(pid, state_checkout=checkout)
        state, effect = receipt["state"], receipt["provider_effect"]
        if state == "published" and effect == "verified":
            _require_exact_verified_receipt(row, checkout=checkout, as_of=clock)
            continue
        if state == "pending" and effect == "impossible":
            _require_clean_pending(pid, checkout=checkout)
            missed.append(pid)
            continue
        raise ValueError(f"expired Milovi slot has unsafe or inconsistent provider state: {pid}")
    return missed


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
    parser.add_argument("operation", choices=("validate", "initialize-all", "due", "audit-expired"))
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
    if args.operation == "audit-expired":
        if args.state_checkout is None:
            raise ValueError("expired-window audit requires exact state checkout")
        missed = missed_delivery_windows(datetime.now(UTC), rows, checkout=args.state_checkout)
        print(
            json.dumps(
                {"missed_windows": missed, "count": len(missed), "provider_access": False, "provider_mutation": False}
            )
        )
        if missed:
            print(
                "::error::MILOVI_TELEGRAM_MISSED_DUE_WINDOWS "
                + str(len(missed))
                + " owner-approved slots expired without verified publication; never replay automatically"
            )
            return 2
        return 0
    if args.state_checkout is None or args.output is None:
        raise ValueError("due validation needs exact state checkout and output")
    current = datetime.now(UTC)
    row = due_row(current, rows)
    permit = row is not None and exact_state_decision(row, checkout=args.state_checkout, now=current)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as out:
        out.write("dispatch=" + ("true" if permit else "false") + "\n")
        if permit:
            out.write("publication_id=" + row["publication_id"] + "\n")
    print(
        json.dumps(
            {
                "dispatch": permit,
                "publication_id": row["publication_id"] if permit else None,
                "provider_access": False,
                "provider_mutation": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
