"""Read-only @lordchrist article backlog; proposed dates are never release authority.

The original Charnock Telegram messages were deleted. Only a matching terminal
scheduled_reissue receipt proves a replacement; missing or ambiguous state must
never be turned into a resend recommendation. This report does not write the
queue, protected state, or any provider. It does not prove fresh public readback
or approve a source migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = Path("content/telegram/lordchrist/telegraph-v1/article-queue.json")
LEDGER_PATH = Path("content/telegram/lordchrist/telegraph-v1/publication-ledger.json")
MANIFEST_PATH = Path("content/telegram/lordchrist/telegraph-v1/charnock/charnock-reschedule-2026.json")
MOSCOW = ZoneInfo("Europe/Moscow")
LORDCHRIST_CHAT_ID = -1001295216957
EDITORIAL_HOLDS = frozenset({"lordchrist-telegraph-charnock-13"})
# Report-only hold for the old Jude run's unknown inputs. A missing ledger
# entry does not resolve its target.
PROPOSAL_ONLY_HOLDS = {
    "lordchrist-telegraph-jude-1-5-20261105": "queued_run_43098273140_target_unknown",
}
# Exact historical Reformation queue alias, not a second release identity.
REFORMATION_QUEUE_ID = "lordchrist-telegraph-charnock-history-02"
REFORMATION_RECEIPT_ID = "lordchrist-telegraph-history-reformation-1517-01"
REFORMATION_QUEUE_BLOB = "b3f4f310157488f716bf38990f7b7da77589f5c8"
REFORMATION_MESSAGE_ID = 1593
REFORMATION_PAGE_URL = "https://telegra.ph/REFORMACIYA-EVANGELIE-PISANIE-I-SPORY-XVI-VEKA-04-11-02"
DEFAULT_STATE_REF = "state/lordchrist-telegram"
DEFAULT_STATE_REMOTE_REF = f"refs/remotes/origin/{DEFAULT_STATE_REF}"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read valid JSON {path}: {exc}") from None


def _iso_date(value: Any, *, field: str) -> date:
    if not isinstance(value, str):
        raise SystemExit(f"{field}: expected ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise SystemExit(f"{field}: invalid ISO date {value!r}") from None
    if parsed.isoformat() != value:
        raise SystemExit(f"{field}: expected YYYY-MM-DD")
    return parsed


def load_queue(path: Path) -> list[dict[str, Any]]:
    document = _read_json(path)
    items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list) or not items:
        raise SystemExit(f"{path}: no queue items")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("publication_id"), str) or not item["publication_id"]:
            raise SystemExit(f"{path}: invalid queue publication identity")
        pid = item["publication_id"]
        if pid in seen:
            raise SystemExit(f"{path}: duplicate queue publication identity {pid}")
        seen.add(pid)
        if item.get("scheduled_on_moscow") is not None:
            _iso_date(item["scheduled_on_moscow"], field=f"{pid} queue date")
    return items


def _ledger_entries(document: Any, *, source: str) -> dict[str, Any]:
    if (
        not isinstance(document, dict)
        or document.get("schema_name") != "video-channel-manager.lordchrist-telegraph-ledger"
        or document.get("schema_version") != 1
        or document.get("project_key") != "lord-god-strength"
        or not isinstance(document.get("entries"), dict)
    ):
        raise SystemExit(f"{source}: invalid or unbound LordChrist ledger; no safe proposal")
    return document["entries"]


def load_ledger_from_ref(root: Path, ref: str, path: Path) -> dict[str, Any]:
    """Read a named Git ref, without checking out or fetching it."""
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{ref}:{path.as_posix()}"], stderr=subprocess.PIPE
        )
        document = json.loads(raw)
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read valid ledger from {ref}: {exc}") from None
    return _ledger_entries(document, source=ref)


def load_ledger(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _ledger_entries(_read_json(path), source=str(path))


def load_calendar_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Read exact reviewed incident bindings, never a proposal file."""
    document = _read_json(path)
    items = document.get("items") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema_name") != "video-channel-manager.lordchrist-charnock-2026-reissue-v1"
        or document.get("schema_version") != 1
        or document.get("channel") != "@lordchrist"
        or document.get("timezone") != "Europe/Moscow"
        or document.get("release_time") != "12:00"
        or "proposal_status" in document
        or not isinstance(items, list)
        or not items
    ):
        raise SystemExit(f"{path}: missing, unreviewed or invalid Charnock calendar; no safe proposal")
    result: dict[str, dict[str, Any]] = {}
    dates: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise SystemExit(f"{path}: invalid calendar entry")
        pid = item.get("publication_id")
        when = item.get("scheduled_on_moscow")
        blob = item.get("article_git_blob_sha")
        source = item.get("source_article_sha256")
        url = item.get("verified_telegraph_url")
        deleted = item.get("deleted_telegram_message_id")
        if (
            not isinstance(pid, str)
            or not pid
            or not isinstance(blob, str)
            or re.fullmatch(r"[0-9a-f]{40}", blob) is None
            or not isinstance(source, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", source) is None
            or not isinstance(url, str)
            or not url.startswith("https://telegra.ph/")
            or type(deleted) is not int
            or deleted <= 0
        ):
            raise SystemExit(f"{path}: incomplete immutable calendar binding")
        _iso_date(when, field=f"{pid} calendar date")
        if pid in result or when in dates:
            raise SystemExit(f"{path}: duplicate publication or date in calendar")
        result[pid] = dict(item)
        dates.add(when)
    return result


def load_report_calendar(path: Path, root: Path) -> dict[str, dict[str, Any]]:
    """Use the production V3 resolver for the canonical report, retaining terminal legacy #09."""
    calendar = load_calendar_manifest(path)
    if path.resolve() != (root / MANIFEST_PATH).resolve():
        # Explicit noncanonical manifest: historical/offline analysis only.
        return calendar
    from video_channel_manager.lordchrist_charnock_reschedule import V3_CALENDAR, load_recovery_calendar_v3

    try:
        resolved = load_recovery_calendar_v3(root, require_approved=False)
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"{root / V3_CALENDAR}: invalid V3 calendar; no safe proposal: {exc}") from exc
    for binding in resolved:
        calendar[binding["publication_id"]] = {**binding, "report_calendar_version": 3}
    return calendar


def _published_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(MOSCOW).date().isoformat()
    except ValueError:
        return None


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _ordinary_receipt_status(entry: Any, pid: str) -> tuple[str, str | None]:
    """Return evidence class, not an assertion about current public visibility."""
    if not isinstance(entry, dict) or entry.get("publication_id") != pid:
        return "ambiguous", None
    message_id = entry.get("telegram_message_id")
    url = entry.get("telegraph_url")
    published_on = _published_date(entry.get("telegram_published_at_utc"))
    if (
        not _positive_int(message_id)
        or entry.get("telegram_chat_id") != LORDCHRIST_CHAT_ID
        or not isinstance(url, str)
        or not url.startswith("https://telegra.ph/")
        or published_on is None
        or "scheduled_reissue" in entry
    ):
        return "ambiguous", None
    state = entry.get("state")
    effect = entry.get("provider_effect")
    telegram_effect = entry.get("telegram_provider_effect")
    if state == "published" and effect == "verified" and telegram_effect == "verified":
        return "verified_receipt", published_on
    if state is None and effect is None and telegram_effect is None:
        # Pre-staged legacy schema: message + exact target + page + timestamp.
        return "legacy_receipt", published_on
    return "ambiguous", None


def _calendar_receipt_status(entry: Any, calendar: dict[str, Any]) -> tuple[str, str | None]:
    """Match the durable replacement receipt to the immutable incident identity."""
    if not isinstance(entry, dict):
        return "ambiguous", None
    if (
        entry.get("publication_id") != calendar["publication_id"]
        or entry.get("state") != "published"
        or entry.get("provider_effect") != "verified"
        or entry.get("telegram_chat_id") != LORDCHRIST_CHAT_ID
        or entry.get("telegram_message_id") != calendar["deleted_telegram_message_id"]
        or entry.get("telegraph_url") != calendar["verified_telegraph_url"]
        or entry.get("article_sha256")
        != calendar.get("historical_source_article_sha256", calendar["source_article_sha256"])
        or (
            calendar.get("report_calendar_version") == 3
            and (
                entry.get("github_sha") != calendar["original_github_sha"]
                or entry.get("cover_sha256") != calendar["original_cover_sha256"]
            )
        )
    ):
        return "ambiguous", None
    if "scheduled_reissue" not in entry:
        return "unclaimed", None
    receipt = entry["scheduled_reissue"]
    expected = {
        "scheduled_on_moscow": calendar["scheduled_on_moscow"],
        "original_deleted_message_id": calendar["deleted_telegram_message_id"],
        "source_article_sha256": calendar["source_article_sha256"],
        "telegraph_url": calendar["verified_telegraph_url"],
    }
    if calendar.get("binding_git_blob_sha"):
        expected["binding_git_blob_sha"] = calendar["binding_git_blob_sha"]
    if (
        isinstance(receipt, dict)
        and receipt.get("state") == "verified"
        and receipt.get("provider_effect") == "verified"
        and _positive_int(receipt.get("new_message_id"))
        and receipt.get("new_message_id") != calendar["deleted_telegram_message_id"]
        and all(receipt.get(key) == value for key, value in expected.items())
    ):
        # Verification may occur after the send, even on a different date.
        # A missing send timestamp must not be replaced by an expected date.
        return "verified", _published_date(receipt.get("sent_at_moscow"))
    return "ambiguous", None


def _calendar_source_blockers(item: dict[str, Any], calendar: dict[str, Any], root: Path) -> list[str]:
    """Check queue/manifest/file bindings, not live page or rendered payload."""
    blockers: list[str] = []
    if item.get("scheduled_on_moscow") != calendar.get("previous_scheduled_on_moscow", calendar["scheduled_on_moscow"]):
        blockers.append("queue_calendar_date_mismatch")
    article = item.get("article")
    if not isinstance(article, dict):
        return [*blockers, "queue_article_missing"]
    queue_blob = article.get("git_blob_sha")
    if queue_blob != calendar.get("queue_article_git_blob_sha", calendar["article_git_blob_sha"]):
        blockers.append("queue_calendar_blob_mismatch")
    raw_path = article.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return [*blockers, "queue_article_path_missing"]
    root = root.resolve()
    path = (root / raw_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return [*blockers, "queue_article_file_unavailable"]
    try:
        data = path.read_bytes()
    except OSError:
        return [*blockers, "queue_article_file_unavailable"]
    actual = hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()
    if actual != queue_blob:
        blockers.append("queue_article_file_blob_mismatch")
    return blockers


def classify(
    items: list[dict[str, Any]],
    ledger: dict[str, Any] | None,
    calendar: dict[str, dict[str, Any]],
    *,
    today: date,
    root: Path = ROOT,
    holds: frozenset[str] = EDITORIAL_HOLDS,
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "published": [],
        "overdue": [],
        "upcoming": [],
        "undated": [],
        "calendar_owned": [],
        "needs_reconciliation": [],
        "ledger_only": [],
    }
    represented_receipt_ids: set[str] = set()
    for item in items:
        pid = item["publication_id"]
        record: dict[str, Any] = {
            "publication_id": pid,
            "status": item.get("status"),
            "scheduled_on_moscow": item.get("scheduled_on_moscow"),
            "canary": bool(item.get("is_canary")),
            "held": pid in holds,
            "proposal_blockers": [],
        }
        if record["held"]:
            record["proposal_blockers"].append("editorial_hold")
        if record["canary"]:
            record["proposal_blockers"].append("canary")
        if record["status"] != "ready":
            record["proposal_blockers"].append("queue_not_ready")
        if pid in PROPOSAL_ONLY_HOLDS:
            record["proposal_blockers"].append(PROPOSAL_ONLY_HOLDS[pid])
        if pid == REFORMATION_QUEUE_ID:
            record["historical_receipt_id"] = REFORMATION_RECEIPT_ID
            record["proposal_blockers"].append("historical_article_no_replay")
            entry = ledger.get(REFORMATION_RECEIPT_ID) if ledger is not None else None
            status, published_on = _ordinary_receipt_status(entry, REFORMATION_RECEIPT_ID)
            article = item.get("article")
            if (
                ledger is not None
                and pid not in ledger
                and isinstance(article, dict)
                and article.get("git_blob_sha") == REFORMATION_QUEUE_BLOB
                and status in {"legacy_receipt", "verified_receipt"}
                and entry["telegram_message_id"] == REFORMATION_MESSAGE_ID
                and entry["telegraph_url"] == REFORMATION_PAGE_URL
            ):
                record["receipt_status"] = status
                record["telegram_message_id"] = REFORMATION_MESSAGE_ID
                record["published_on_moscow"] = published_on
                represented_receipt_ids.add(REFORMATION_RECEIPT_ID)
                groups["published"].append(record)
            else:
                record["receipt_status"] = "unavailable" if ledger is None else "ambiguous"
                record["proposal_blockers"].append("historical_receipt_requires_reconciliation")
                groups["needs_reconciliation"].append(record)
            continue
        if pid in calendar:
            binding = calendar[pid]
            record["calendar_date"] = binding["scheduled_on_moscow"]
            record["deleted_telegram_message_id"] = binding["deleted_telegram_message_id"]
            if binding.get("report_calendar_version") == 3:
                record["calendar_version"] = 3
                record["proposal_blockers"].append("v3_calendar_owned_no_automatic_reschedule")
                if not binding.get("release_approval"):
                    record["proposal_blockers"].append("v3_release_approval_missing")
            record["proposal_blockers"].extend(_calendar_source_blockers(item, binding, root))
            if ledger is None:
                status, published_on = "unavailable", None
            else:
                status, published_on = _calendar_receipt_status(ledger.get(pid), binding)
            record["receipt_status"] = status
            if status in ("unclaimed", "verified"):
                # The original was deleted, but its real publication date is
                # still relevant to a channel-wide one-article-per-day plan.
                original_date = _published_date(ledger[pid].get("telegram_published_at_utc"))  # type: ignore[index]
                record["original_published_on_moscow"] = original_date
                if original_date is None:
                    record["proposal_blockers"].append("original_publication_date_unresolved")
            if status == "verified":
                receipt = ledger[pid]["scheduled_reissue"]  # type: ignore[index]
                record["telegram_message_id"] = receipt["new_message_id"]
                record["published_on_moscow"] = published_on
                if published_on is None:
                    record["proposal_blockers"].append("publication_date_unresolved")
                groups["published"].append(record)
                continue
            if status != "unclaimed":
                record["proposal_blockers"].append(f"reissue_receipt_{status}")
            if binding["scheduled_on_moscow"] < today.isoformat():
                record["calendar_overdue_days"] = (today - date.fromisoformat(binding["scheduled_on_moscow"])).days
            groups["calendar_owned"].append(record)
            continue
        if ledger is None:
            record["receipt_status"] = "unavailable"
            record["proposal_blockers"].append("ledger_unavailable")
            groups["needs_reconciliation"].append(record)
            continue
        if pid in ledger:
            status, published_on = _ordinary_receipt_status(ledger[pid], pid)
            record["receipt_status"] = status
            if status == "ambiguous":
                record["proposal_blockers"].append("publication_receipt_ambiguous")
                groups["needs_reconciliation"].append(record)
            else:
                record["telegram_message_id"] = ledger[pid]["telegram_message_id"]
                record["published_on_moscow"] = published_on
                groups["published"].append(record)
            continue
        record["receipt_status"] = "no_ledger_entry"
        raw = item.get("scheduled_on_moscow")
        if not raw:
            groups["undated"].append(record)
        elif raw < today.isoformat():
            record["overdue_days"] = (today - date.fromisoformat(raw)).days
            groups["overdue"].append(record)
        else:
            groups["upcoming"].append(record)

    # A protected receipt can outlive its queue item. It must reserve its real
    # date without ever being turned back into a candidate for publication.
    if ledger is not None:
        if any(not isinstance(pid, str) or not pid for pid in ledger):
            raise SystemExit("ledger contains an invalid publication identity; no safe proposal")
        queue_ids = {item["publication_id"] for item in items}
        for pid in sorted(ledger.keys() - queue_ids - represented_receipt_ids):
            status, published_on = _ordinary_receipt_status(ledger[pid], pid)
            extra: dict[str, Any] = {
                "publication_id": pid,
                "receipt_status": status,
                "published_on_moscow": published_on,
            }
            if status != "ambiguous":
                extra["telegram_message_id"] = ledger[pid]["telegram_message_id"]
            groups["ledger_only"].append(extra)
    for records in groups.values():
        records.sort(
            key=lambda r: (r.get("calendar_date") or r.get("scheduled_on_moscow") or "9999", r["publication_id"])
        )
    return groups


def propose_slots(
    waiting: list[dict[str, Any]],
    *,
    start: date,
    gap_days: int,
    busy: set[date],
    horizon_days: int = 180,
) -> list[dict[str, Any]]:
    """Space from all occupied dates in both directions, not only new slots."""
    if gap_days < 1 or horizon_days < 0:
        raise SystemExit("--gap must be at least 1 day and horizon must be non-negative")
    proposal: list[dict[str, Any]] = []
    occupied = set(busy)
    cursor = start
    limit = start + timedelta(days=horizon_days)
    for item in waiting:
        if item.get("held") or item.get("canary") or item.get("proposal_blockers"):
            continue
        while cursor <= limit and any(abs((cursor - day).days) < gap_days for day in occupied):
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
        occupied.add(cursor)
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
    ledger_source: str = "file",
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    if gap_days < 1:
        raise SystemExit("--gap must be at least 1 day")
    if start < today:
        raise SystemExit("--start cannot be before --today")
    items = load_queue(queue_path)
    ledger = ledger_entries if ledger_entries is not None else load_ledger(ledger_path)
    if ledger_source == "absent":
        ledger = None
    elif ledger is None:
        ledger_source = "absent"
    calendar = load_report_calendar(manifest_path, repo_root)
    if set(calendar) - {item["publication_id"] for item in items}:
        raise SystemExit("calendar contains publication identities missing from the queue")
    groups = classify(items, ledger, calendar, today=today, root=repo_root, holds=holds)

    # Reserve even held, ambiguous and already-sent dates. A local Git ref can
    # be stale: every proposal still needs a fresh protected-state recheck.
    occupied: set[date] = set()
    for records in groups.values():
        for record in records:
            for key in ("scheduled_on_moscow", "calendar_date", "published_on_moscow", "original_published_on_moscow"):
                if key == "scheduled_on_moscow" and record.get("calendar_version") == 3:
                    # Historical queue date is an immutable identity, not a second active V3 reservation.
                    continue
                if record.get(key):
                    occupied.add(date.fromisoformat(record[key]))
    waiting = [{**r, "source": "queue"} for key in ("overdue", "undated") for r in groups[key]]
    waiting += [
        {**r, "source": "charnock_calendar"} for r in groups["calendar_owned"] if r.get("calendar_overdue_days")
    ]
    rank = {pid: index for index, pid in enumerate(priority)}
    waiting.sort(
        key=lambda r: (
            rank.get(r["publication_id"], len(rank)),
            r.get("calendar_date") or r.get("scheduled_on_moscow") or "9999",
            r["publication_id"],
        )
    )
    # Unknown effects or publication dates cannot establish which day is free.
    # Retain verified receipts as terminal, but stop all date suggestions until
    # those unknowns are reconciled; this is still only an advisory report.
    suppressed_by: list[str] = []
    if ledger is None:
        suppressed_by.append("ledger_unavailable")
    else:
        suppressed_by.extend(
            f"{record['publication_id']}:publication_date_unresolved"
            for record in groups["published"]
            if record.get("published_on_moscow") is None
        )
        suppressed_by.extend(
            f"{record['publication_id']}:original_publication_date_unresolved"
            for group in ("published", "calendar_owned")
            for record in groups[group]
            if "original_published_on_moscow" in record and record["original_published_on_moscow"] is None
        )
        suppressed_by.extend(
            f"{record['publication_id']}:publication_receipt_ambiguous" for record in groups["needs_reconciliation"]
        )
        suppressed_by.extend(
            f"{record['publication_id']}:reissue_receipt_ambiguous"
            for record in groups["calendar_owned"]
            if record["receipt_status"] == "ambiguous"
        )
        suppressed_by.extend(
            f"{record['publication_id']}:ledger_only_receipt_ambiguous"
            for record in groups["ledger_only"]
            if record["receipt_status"] == "ambiguous"
        )
    proposal = propose_slots(waiting, start=start, gap_days=gap_days, busy=occupied) if not suppressed_by else []
    return {
        "schema_name": "video-channel-manager.lordchrist-telegraph-backlog-plan",
        "schema_version": 1,
        "generated_for": today.isoformat(),
        "read_only": True,
        "ledger_source": ledger_source,
        "ledger_freshness": "not_proven_by_local_ref; re-read protected state before any decision",
        "proposal_start": start.isoformat(),
        "gap_days": gap_days,
        "counts": {name: len(records) for name, records in groups.items()},
        **groups,
        "proposal_suppressed_by": suppressed_by,
        "proposal": proposal,
        "editorial_holds": sorted(holds),
    }


def render(plan: dict[str, Any]) -> str:
    counts = plan["counts"]
    lines = [
        "Квитанции очереди: {published} | вне очереди: {ledger_only} | просрочено: {overdue} | "
        "впереди: {upcoming} | без даты: {undated} | календарь Чарнока: {calendar_owned} | "
        "сверить: {needs_reconciliation}".format(**counts)
    ]
    if plan["overdue"]:
        lines.append("\nПРОСРОЧЕНО (не разрешение на выпуск):")
        for r in plan["overdue"]:
            blockers = f"; блокеры: {', '.join(r['proposal_blockers'])}" if r["proposal_blockers"] else ""
            lines.append(
                f"  {r['publication_id']} — было {r['scheduled_on_moscow']}, {r['overdue_days']} дн.{blockers}"
            )
    if plan["undated"]:
        lines.append("\nБЕЗ ДАТЫ:")
        for r in plan["undated"]:
            blockers = f"; блокеры: {', '.join(r['proposal_blockers'])}" if r["proposal_blockers"] else ""
            lines.append(f"  {r['publication_id']}{blockers}")
    if plan["calendar_owned"]:
        lines.append("\nКАЛЕНДАРЬ ЧАРНОКА (оригинальные удалённые ID не подтверждают перевыпуск):")
        for r in plan["calendar_owned"]:
            blockers = ", ".join(r["proposal_blockers"]) or "нет локальных блокеров; provider не проверен"
            lines.append(
                f"  {r['publication_id']} — {r['calendar_date']}, удалённое сообщение "
                f"{r['deleted_telegram_message_id']}, receipt={r['receipt_status']}; {blockers}"
            )
    aliases = [r for r in plan["published"] if r.get("historical_receipt_id")]
    if aliases:
        lines.append("\nИСТОРИЧЕСКИЕ КВИТАНЦИИ ПОД ПРЕЖНИМ ID (не планировать повтор):")
        for r in aliases:
            lines.append(
                f"  {r['publication_id']} → {r['historical_receipt_id']}, "
                f"Telegram #{r['telegram_message_id']}, {r['published_on_moscow']}"
            )
    if plan["ledger_only"]:
        lines.append("\nКВИТАНЦИИ ВНЕ ТЕКУЩЕЙ ОЧЕРЕДИ (не планировать повтор):")
        for r in plan["ledger_only"]:
            when = r["published_on_moscow"] or "дата неизвестна"
            lines.append(f"  {r['publication_id']} — receipt={r['receipt_status']}, {when}")
    if plan["needs_reconciliation"]:
        lines.append("\nНУЖНА СВЕРКА (не планировать повтор):")
        for r in plan["needs_reconciliation"]:
            lines.append(f"  {r['publication_id']} — {r['receipt_status']}")
    if plan["upcoming"]:
        lines.append("\nВПЕРЕДИ (не разрешение на выпуск):")
        for r in plan["upcoming"]:
            lines.append(f"  {r['publication_id']} — {r['scheduled_on_moscow']}")
    if plan["proposal_suppressed_by"]:
        lines.append("\nЧЕРНОВИК ДАТ ОТКЛЮЧЁН ДО СВЕРКИ: " + ", ".join(plan["proposal_suppressed_by"]))
    if plan["proposal"]:
        lines.append(f"\nЧЕРНОВИК ДАТ (зазор {plan['gap_days']} дн. от занятых дат; не разрешение):")
        for slot in plan["proposal"]:
            lines.append(f"  {slot['proposed_date']} — {slot['publication_id']} (было {slot['was_scheduled_for']})")
    if plan["ledger_source"] == "absent":
        lines.append("\nВНИМАНИЕ: ledger не прочитан; все предложения дат отключены.")
    lines.append(
        "\nТолько чтение. Свежесть local ref, публичный readback, права, приёмка и разрешение владельца "
        "этим отчётом не подтверждаются."
    )
    return "\n".join(lines)


def _default_proposal_start(today: date, now: datetime) -> date:
    """Offer today's midday slot only before its 14:00 Moscow cutoff."""
    if now.tzinfo is None:
        raise ValueError("proposal clock must be timezone-aware")
    local = now.astimezone(MOSCOW)
    if local.date() == today and local.hour < 14:
        return today
    return today + timedelta(days=1)


def _safe_output_path(root: Path, out: Path, inputs: tuple[Path, ...]) -> Path:
    """An optional report must not overwrite content, a ledger or source code."""
    root = root.resolve()
    out = out.resolve()
    if out in {path.resolve() for path in inputs}:
        raise SystemExit("report output cannot overwrite a planner input")
    artifacts = (root / "artifacts").resolve()
    if artifacts != root / "artifacts":
        raise SystemExit("artifacts/ must not be a symlink")
    if out.is_relative_to(root) and not out.is_relative_to(artifacts):
        raise SystemExit("report output inside the checkout must be under artifacts/")
    if out.exists() and not out.is_relative_to(artifacts):
        raise SystemExit("refusing to overwrite an existing report path outside artifacts/")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--ledger-ref", help="read the durable ledger from this git ref instead")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--today", help="override for tests: YYYY-MM-DD")
    parser.add_argument("--start", help="first proposed date: YYYY-MM-DD (default: today's remaining midday slot)")
    parser.add_argument("--gap", type=int, default=2, help="minimum days between proposal and every occupied slot")
    parser.add_argument("--priority", action="append", default=[], metavar="PUBLICATION_ID")
    parser.add_argument("--out", type=Path, help="write the advisory JSON plan")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(argv)

    root = args.repo_root
    resolve = lambda path: path if path.is_absolute() else root / path  # noqa: E731
    local_now = datetime.now(MOSCOW)
    today = _iso_date(args.today, field="--today") if args.today else local_now.date()
    start = _iso_date(args.start, field="--start") if args.start else _default_proposal_start(today, local_now)
    if start < today:
        raise SystemExit("--start cannot be before --today")
    ledger_entries: dict[str, Any] | None = None
    ledger_source = "file"
    if args.ledger_ref:
        ledger_entries = load_ledger_from_ref(root, args.ledger_ref, args.ledger)
        ledger_source = args.ledger_ref
    elif not resolve(args.ledger).is_file():
        try:
            ledger_entries = load_ledger_from_ref(root, DEFAULT_STATE_REMOTE_REF, args.ledger)
            ledger_source = DEFAULT_STATE_REF
        except SystemExit:
            ledger_source = "absent"

    plan = build_plan(
        queue_path=resolve(args.queue),
        ledger_path=resolve(args.ledger),
        manifest_path=resolve(args.manifest),
        today=today,
        start=start,
        gap_days=args.gap,
        priority=tuple(args.priority),
        ledger_entries=ledger_entries,
        ledger_source=ledger_source,
        repo_root=root,
    )
    if args.out:
        requested_out = args.out if args.out.is_absolute() else root / args.out
        out = _safe_output_path(
            root, requested_out, (resolve(args.queue), resolve(args.ledger), resolve(args.manifest))
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=1) if args.json else render(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
