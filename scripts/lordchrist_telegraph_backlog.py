"""Read-only release backlog and a spaced slot proposal for @lordchrist articles.

The publisher only ever asks "is exactly one article scheduled today?", so a
missed window leaves no trace: the article simply never publishes, and nothing
warns that four of them are now overdue.  This tool answers the other question —
what is waiting, what is overdue, and which dates would keep releases apart —
without touching the queue, the ledger or any provider.

It is advisory by construction: it writes nothing except an optional JSON file
with the plan, and it never mutates content, state or provider.  Dates it
proposes are proposals for the owner, not authority.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = Path("content/telegram/lordchrist/telegraph-v1/article-queue.json")
LEDGER_PATH = Path("content/telegram/lordchrist/telegraph-v1/publication-ledger.json")
MANIFEST_PATH = Path("content/telegram/lordchrist/telegraph-v1/charnock/charnock-reschedule-2026.json")

# Release-time editorial holds: these must not be proposed for a slot.
# lordchrist-telegraph-charnock-13 — issue #997: independent quotation review
# and a new approved blob are required before the @lordchrist release.
EDITORIAL_HOLDS = frozenset({"lordchrist-telegraph-charnock-13"})


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_queue(path: Path) -> list[dict[str, Any]]:
    document = _read_json(path)
    items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list) or not items:
        raise SystemExit(f"{path}: no queue items")
    return items


def load_ledger_from_ref(root: Path, ref: str, path: Path) -> dict[str, Any]:
    """Read the durable ledger from a git ref (read-only, no checkout needed)."""
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{ref}:{path.as_posix()}"], stderr=subprocess.PIPE
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(f"cannot read ledger from {ref}: {exc}") from None
    document = json.loads(raw)
    entries = document.get("entries") if isinstance(document, dict) else None
    return entries if isinstance(entries, dict) else {}


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    document = _read_json(path)
    entries = document.get("entries") if isinstance(document, dict) else None
    return entries if isinstance(entries, dict) else {}


def load_calendar_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """publication_id -> review calendar record for the Charnock reissue workflow."""
    if not path.is_file():
        return {}
    document = _read_json(path)
    items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        pid = item.get("publication_id")
        when = item.get("scheduled_on_moscow")
        if isinstance(pid, str) and isinstance(when, str):
            result[pid] = {
                "date": when,
                "deleted_telegram_message_id": item.get("deleted_telegram_message_id"),
            }
    return result


def classify(
    items: list[dict[str, Any]],
    ledger: dict[str, Any],
    calendar: dict[str, str],
    *,
    today: date,
    holds: frozenset[str] = EDITORIAL_HOLDS,
) -> dict[str, list[dict[str, Any]]]:
    published: list[dict[str, Any]] = []
    overdue: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    undated: list[dict[str, Any]] = []
    calendar_owned: list[dict[str, Any]] = []

    for item in items:
        pid = item.get("publication_id")
        if not isinstance(pid, str):
            continue
        entry = ledger.get(pid) or {}
        record = {
            "publication_id": pid,
            "status": item.get("status"),
            "scheduled_on_moscow": item.get("scheduled_on_moscow"),
            "canary": bool(item.get("is_canary")),
            "held": pid in holds,
            "telegram_message_id": entry.get("telegram_message_id"),
            "telegraph_path": entry.get("telegraph_path"),
        }
        if pid in calendar:
            # The reviewed Charnock calendar owns these dates, and the ledger
            # still carries the deleted 2026-11-05 message ids, so a ledger-only
            # view would wrongly call them published.
            record["calendar_date"] = calendar[pid]["date"]
            record["deleted_telegram_message_id"] = calendar[pid]["deleted_telegram_message_id"]
            if calendar[pid]["date"] < today.isoformat():
                record["calendar_overdue_days"] = (today - date.fromisoformat(calendar[pid]["date"])).days
            calendar_owned.append(record)
            continue
        if entry.get("telegram_message_id"):
            published.append(record)
            continue
        raw = item.get("scheduled_on_moscow")
        if not raw:
            undated.append(record)
            continue
        record["scheduled_on_moscow"] = raw
        if raw < today.isoformat():
            record["overdue_days"] = (today - date.fromisoformat(raw)).days
            overdue.append(record)
        else:
            upcoming.append(record)

    order = lambda record: record.get("scheduled_on_moscow") or ""  # noqa: E731
    overdue.sort(key=order)
    upcoming.sort(key=order)
    published.sort(key=order)
    undated.sort(key=lambda record: record["publication_id"])
    calendar_owned.sort(key=lambda record: record.get("calendar_date") or "")
    return {
        "published": published,
        "overdue": overdue,
        "upcoming": upcoming,
        "undated": undated,
        "calendar_owned": calendar_owned,
    }


def propose_slots(
    waiting: list[dict[str, Any]],
    *,
    start: date,
    gap_days: int,
    busy: set[date],
    horizon_days: int = 180,
) -> list[dict[str, Any]]:
    """One article per date, at least `gap_days` apart across the whole channel.

    `waiting` must already be ordered by how overdue each item is; held and
    canary items are skipped and stay waiting for an owner decision.
    """
    if gap_days < 1:
        raise SystemExit("--gap must be at least 1 day")
    proposal: list[dict[str, Any]] = []
    cursor = start
    limit = start + timedelta(days=horizon_days)
    for item in waiting:
        if item["held"] or item.get("canary"):
            continue
        while cursor in busy and cursor <= limit:
            cursor += timedelta(days=1)
        if cursor > limit:
            break
        proposal.append(
            {
                "publication_id": item["publication_id"],
                "proposed_date": cursor.isoformat(),
                "was_scheduled_for": item.get("calendar_date") or item.get("scheduled_on_moscow") or "—",
                "source": item["source"],
            }
        )
        busy.add(cursor)
        cursor += timedelta(days=gap_days)
    return proposal


def build_plan(
    *,
    queue_path: Path,
    ledger_path: Path,
    manifest_path: Path,
    today: date,
    start: date,
    gap_days: int,
    ledger_entries: dict[str, Any] | None = None,
    priority: tuple[str, ...] = (),
    holds: frozenset[str] = EDITORIAL_HOLDS,
) -> dict[str, Any]:
    items = load_queue(queue_path)
    ledger = ledger_entries if ledger_entries is not None else load_ledger(ledger_path)
    calendar = load_calendar_manifest(manifest_path)
    groups = classify(items, ledger, calendar, today=today, holds=holds)

    busy = {
        date.fromisoformat(record["scheduled_on_moscow"])
        for record in groups["upcoming"]
        if record.get("scheduled_on_moscow")
    }
    busy |= {
        date.fromisoformat(record["calendar_date"])
        for record in groups["calendar_owned"]
        if record.get("calendar_date") and record["calendar_date"] >= today.isoformat()
    }

    waiting: list[dict[str, Any]] = []
    for record in groups["overdue"]:
        waiting.append({**record, "source": "queue"})
    for record in groups["undated"]:
        waiting.append({**record, "source": "queue"})
    for record in groups["calendar_owned"]:
        if record.get("calendar_overdue_days"):
            waiting.append({**record, "source": "charnock_calendar"})
    priority_rank = {pid: index for index, pid in enumerate(priority)}
    waiting.sort(
        key=lambda record: (
            priority_rank.get(record["publication_id"], len(priority_rank)),
            record.get("calendar_date") or record.get("scheduled_on_moscow") or "9999",
            record["publication_id"],
        )
    )
    proposal = propose_slots(waiting, start=start, gap_days=gap_days, busy=busy)

    return {
        "schema_name": "video-channel-manager.lordchrist-telegraph-backlog-plan",
        "schema_version": 1,
        "generated_for": today.isoformat(),
        "read_only": True,
        "gap_days": gap_days,
        "counts": {name: len(records) for name, records in groups.items()},
        **groups,
        "proposal": proposal,
        "editorial_holds": sorted(EDITORIAL_HOLDS),
    }


def render(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    counts = plan["counts"]
    lines.append(
        "Опубликовано: {published} | просрочено: {overdue} | впереди: {upcoming} | "
        "без даты: {undated} | календарь Чарнока: {calendar_owned}".format(**counts)
    )
    if plan["overdue"]:
        lines.append("\nПРОСРОЧЕНО (окно прошло, нужен явный выпуск):")
        for record in plan["overdue"]:
            held = " [HOLD]" if record["held"] else ""
            lines.append(
                f"  {record['publication_id']} — было {record['scheduled_on_moscow']}, "
                f"{record['overdue_days']} дн.{held}"
            )
    if plan["undated"]:
        lines.append("\nБЕЗ ДАТЫ (нужно решение владельца):")
        for record in plan["undated"]:
            held = " [HOLD]" if record["held"] else ""
            lines.append(f"  {record['publication_id']}{held}")
    if plan["calendar_owned"]:
        lines.append("\nКАЛЕНДАРЬ ЧАРНОКА (отдельный манифест, руками не двигать):")
        for record in plan["calendar_owned"]:
            extra = ""
            if record.get("calendar_overdue_days"):
                extra = f", просрочка {record['calendar_overdue_days']} дн."
            if record.get("deleted_telegram_message_id"):
                extra += f", удалённое сообщение {record['deleted_telegram_message_id']}"
            held = " [HOLD]" if record["held"] else ""
            lines.append(f"  {record['publication_id']} — {record.get('calendar_date')}{extra}{held}")
    if plan["upcoming"]:
        lines.append("\nВПЕРЕДИ:")
        for record in plan["upcoming"]:
            lines.append(f"  {record['publication_id']} — {record['scheduled_on_moscow']}")
    if plan["proposal"]:
        lines.append(
            f"\nПРЕДЛОЖЕНИЕ: шаг {plan['gap_days']} дн., не более одной статьи в день, занятые даты пропускаются:"
        )
        for slot in plan["proposal"]:
            where = "календарь Чарнока" if slot["source"] == "charnock_calendar" else "очередь"
            lines.append(
                f"  {slot['proposed_date']} — {slot['publication_id']} ({where}, было {slot['was_scheduled_for']})"
            )
    lines.append("\nТолько чтение: очередь, ledger и провайдер не меняются. Даты — предложение.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--ledger-ref", help="read the durable ledger from this git ref instead")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--today", help="override for tests: YYYY-MM-DD")
    parser.add_argument("--start", help="first proposed date: YYYY-MM-DD (default: next day)")
    parser.add_argument("--gap", type=int, default=3, help="days between proposed slots")
    parser.add_argument(
        "--priority",
        action="append",
        default=[],
        metavar="PUBLICATION_ID",
        help="pull this publication to the front of the proposed order (repeatable)",
    )
    parser.add_argument("--out", type=Path, help="write the plan JSON here")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(argv)

    root = args.repo_root
    resolve = lambda path: path if path.is_absolute() else root / path  # noqa: E731
    today = date.fromisoformat(args.today) if args.today else datetime.now().date()
    start = date.fromisoformat(args.start) if args.start else today + timedelta(days=1)
    plan = build_plan(
        queue_path=resolve(args.queue),
        ledger_path=resolve(args.ledger),
        manifest_path=resolve(args.manifest),
        today=today,
        start=start,
        gap_days=args.gap,
        priority=tuple(args.priority),
        ledger_entries=(load_ledger_from_ref(root, args.ledger_ref, args.ledger) if args.ledger_ref else None),
    )
    if args.out:
        out = args.out if args.out.is_absolute() else root / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=1) if args.json else render(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
