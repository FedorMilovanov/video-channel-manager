"""Bounded Milovi School reading promotion: three exact dates, no second Telegram sender."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from video_channel_manager.milovi_telegram_feed import state_init, validate_bundle
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import load_ledger
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload

ZONE = ZoneInfo("Europe/Moscow")
ROOT = Path("content/telegram/milovi-cake")
STATE_FEED = ROOT / "feed"
SCHOOL_REPO = "FedorMilovanov/Milovi_School"
SOURCE_COMMIT = "f540e8d6fca89592a8394e0a707e6af0d85afc14"
RELEASES = (
    ("2026-11-17", "milovi-feed-20261117-002", "paris-brest-race-dessert"),
    ("2026-11-21", "milovi-feed-20261121-002", "croissant-history"),
    ("2026-11-25", "milovi-feed-20261125-001", "stohrer-1730"),
)
# First screen contains actual native Cake videos. Never count pending, failed,
# historical deleted canaries, or unverified mock deliveries.
FIRST_TEN = ("milovi-feed-20261107-002",) + tuple(f"milovi-feed-202611{day:02d}-001" for day in range(8, 17))
OWNER_EARLY_PARIS_BREST = "milovi-feed-20261106-001"
ORIGINAL_PARIS_BREST = "milovi-feed-20261117-002"


def _load_state_index(checkout: Path) -> dict[str, object]:
    path = checkout / STATE_FEED / "index.json"
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Milovi protected channel-wide feed index missing or invalid") from exc
    if (
        index.get("project_key") != "milovi-cake"
        or index.get("channel_username") != "@MiloviCake"
        or not isinstance(index.get("entries"), dict)
    ):
        raise ValueError("Wrong Milovi protected index identity")
    return index["entries"]


def _verified(entry: object, expected_pid: str) -> bool:
    if not isinstance(entry, dict) or entry.get("publication_id") != expected_pid:
        return False
    return (
        entry.get("state") == "published"
        and entry.get("provider_effect") == "verified"
        and isinstance(entry.get("message_id"), int)
        and entry["message_id"] > 0
        and entry.get("message_url") is not None
    )


def _early_paris_brest_verified(checkout: Path, entries: dict[str, object]) -> bool:
    """Recognize only the owner-approved exact Nov 6 published photo, not a loose match."""
    early = entries.get(OWNER_EARLY_PARIS_BREST)
    if not _verified(early, OWNER_EARLY_PARIS_BREST):
        return False
    assert isinstance(early, dict)
    release = load_release(ROOT / "releases" / f"{OWNER_EARLY_PARIS_BREST}-runtime.json")
    original = load_release(ROOT / "releases" / f"{ORIGINAL_PARIS_BREST}-runtime.json")
    if (
        len(release.items) != 1
        or release.channel_username != "@MiloviCake"
        or release.chat_id != -1002215328390
        or release.bot_id != 8716602202
        or release.items[0].source_sha256 != original.items[0].source_sha256
        or release.items[0].payload.caption != original.items[0].payload.caption
        or release.items[0].payload.media_sha256 != original.items[0].payload.media_sha256
    ):
        raise ValueError("Owner's early School post identity differs from original Nov 17 story")
    ledger = load_ledger(checkout / STATE_FEED / f"{OWNER_EARLY_PARIS_BREST}.json", release)
    item = ledger.entries[OWNER_EARLY_PARIS_BREST]
    if not (
        item.state == "published"
        and item.provider_effect == "verified"
        and item.actual_chat_id == release.chat_id
        and item.bot_id == release.bot_id
        and item.message_id == early["message_id"]
        and item.message_url == early["message_url"]
    ):
        raise ValueError("Early School publication is not confirmed by exact protected provider receipt")
    return True


def require_first_ten_real_cake_videos(checkout: Path, entries: dict[str, object]) -> None:
    """The channel's first screen must be actual Cake work, not School promos."""
    for pid in FIRST_TEN:
        item = entries.get(pid)
        if not _verified(item, pid):
            raise ValueError(f"School reading requires verified first-ten Cake video: {pid}")
        release = load_release(ROOT / "releases" / f"{pid}-runtime.json")
        if (
            len(release.items) != 1
            or not isinstance(release.items[0].payload, GenericVideoPayload)
            or release.channel_username != "@MiloviCake"
            or release.chat_id != -1002215328390
            or release.bot_id != 8716602202
        ):
            raise ValueError(f"First screen must contain native Cake videos on exact target: {pid}")
        ledger_path = checkout / STATE_FEED / f"{pid}.json"
        ledger = load_ledger(ledger_path, release)
        e = ledger.entries[pid]
        if not (
            e.state == "published"
            and e.provider_effect == "verified"
            and e.message_id == item["message_id"]
            and e.actual_chat_id == -1002215328390
            and e.bot_id == 8716602202
            and e.message_url == item["message_url"]
        ):
            raise ValueError(f"First-screen Cake video lacks an exact protected receipt: {pid}")


def validate_exact_releases() -> None:
    for day, pid, slug in RELEASES:
        result = validate_bundle(pid, require_execution_authorized=True)
        release = load_release(ROOT / "releases" / f"{pid}-runtime.json")
        item = release.items[0]
        media = json.loads((ROOT / "releases" / f"{pid}-media.json").read_text(encoding="utf-8"))
        candidate = json.loads((ROOT / "candidates" / f"{pid}.json").read_text(encoding="utf-8"))
        if not (
            result["payload_kind"] == "photo"
            and result["provider_access_performed"] is False
            and release.channel_username == "@MiloviCake"
            and release.chat_id == -1002215328390
            and release.bot_id == 8716602202
            and item.scheduled_at.astimezone(ZONE).date().isoformat() == day
            and item.scheduled_at.astimezone(ZONE).strftime("%H:%M") == "12:30"
            and media["source"]["repository"] == SCHOOL_REPO
            and media["source"]["commit"] == SOURCE_COMMIT
            and media["source"]["path"]
            == f"public/images/articles/{'body-croissant-golden-baked' if slug == 'croissant-history' else slug}.webp"
            and candidate["source_context"]["school_article_url"] == f"https://french.milovicake.ru/articles/{slug}/"
            and item.payload.caption.count(f"https://french.milovicake.ru/articles/{slug}/") == 1
            and "Иллюстрация — Milovi School." in item.payload.caption
            and "Milovi Cake готовит" not in item.payload.caption
        ):
            raise ValueError(f"School release source and educational boundary mismatch: {pid}")


def initialize_all(checkout: Path) -> None:
    validate_exact_releases()
    for _, pid, _ in RELEASES:
        result = state_init(pid, state_checkout=checkout)
        print(json.dumps({"school_release_initialized": pid, "result": result}, ensure_ascii=False))
    _load_state_index(checkout)


def due(checkout: Path, *, now: datetime | None = None) -> dict[str, str]:
    validate_exact_releases()
    clock = (now or datetime.now(timezone.utc)).astimezone(ZONE)
    if clock.year != 2026 or clock.month != 11:
        return {"dispatch": "false", "reason": "year_or_month_mismatch"}
    matching = [(d, pid) for d, pid, _ in RELEASES if d == clock.date().isoformat()]
    if not matching:
        return {"dispatch": "false", "reason": "not_an_exact_school_date"}
    _, pid = matching[0]
    release = load_release(ROOT / "releases" / f"{pid}-runtime.json")
    slot = release.items[0].scheduled_at.astimezone(ZONE)
    if clock < slot or clock >= slot + timedelta(minutes=120):
        return {"dispatch": "false", "reason": "outside_reviewed_school_slot"}
    entries = _load_state_index(checkout)
    early_verified = _early_paris_brest_verified(checkout, entries)
    if pid == ORIGINAL_PARIS_BREST and early_verified:
        return {"dispatch": "false", "reason": "original_story_already_sent_20261106"}
    require_first_ten_real_cake_videos(checkout, entries)

    # One shared provider account and index. Any unresolved effect anywhere blocks.
    for eid, e in entries.items():
        if (
            not isinstance(e, dict)
            or e.get("state") in ("dispatching", "unknown")
            or e.get("provider_effect") == "may_exist"
        ):
            raise ValueError(f"unresolved Milovi channel-wide effect: {eid}")
    previous = [x for x in RELEASES if x[0] < clock.date().isoformat()]
    for _, prior_pid, _ in previous:
        if prior_pid == ORIGINAL_PARIS_BREST and early_verified:
            continue
        if not _verified(entries.get(prior_pid), prior_pid):
            raise ValueError(f"School reading strict predecessor not verified: {prior_pid}")

    today_verified = sum(
        1
        for eid, e in entries.items()
        if eid.startswith("milovi-feed-" + clock.strftime("%Y%m%d") + "-")
        and isinstance(e, dict)
        and e.get("state") == "published"
        and e.get("provider_effect") == "verified"
    )
    if today_verified >= 2:
        raise ValueError("Milovi owner-verified daily limit already reached")
    entry = entries.get(pid)
    if _verified(entry, pid):
        return {"dispatch": "false", "reason": "already_verified"}
    if not isinstance(entry, dict) or entry.get("state") != "pending" or entry.get("provider_effect") != "impossible":
        raise ValueError("School reading entry missing, uncertain, previously attempted or non-pending")
    ledger = load_ledger(checkout / STATE_FEED / f"{pid}.json", release)
    child = ledger.entries[pid]
    if child.state != "pending" or child.provider_effect != "impossible":
        raise ValueError("School reading exact immutable ledger differs from pending index")
    return {"dispatch": "true", "publication_id": pid, "reason": "exact_owner_approved_school_photo_due"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "initialize-all", "due"))
    parser.add_argument("--state-checkout", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        validate_exact_releases()
        print("Three exact owner-approved Milovi School story/photo releases validated; no provider access.")
    elif args.command == "initialize-all":
        if args.state_checkout is None:
            parser.error("initialize-all requires --state-checkout")
        initialize_all(args.state_checkout)
    else:
        if args.state_checkout is None or args.output is None:
            parser.error("due requires --state-checkout and --output")
        result = due(args.state_checkout)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("a", encoding="utf-8") as output:
            for key, value in result.items():
                output.write(f"{key}={value}\n")
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
