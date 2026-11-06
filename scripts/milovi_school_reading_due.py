"""Bounded Milovi School reading promotion: three exact dates, no second Telegram sender."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from video_channel_manager.milovi_telegram_feed import (
    MiloviFeedIndex,
    _save_index,
    state_init,
    validate_bundle,
)
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import (
    GenericPublicationLedger,
    initialize_ledger,
    load_ledger,
    save_ledger,
)
from video_channel_manager.telegram_multichannel_video import GenericVideoPayload
from video_channel_manager.telegram_multichannel_transport import GenericRichPhotoPayload

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

# A one-time owner-authorized editorial revision. No media or publication dates
# change, and only records proven entirely pending and provider-impossible can migrate.
# These are actual protected-state pre-revision identities, never inferred from a
# mutable current release.
RICH_EDITORIAL_PREDECESSORS: dict[str, tuple[str, str, str]] = {
    "milovi-feed-20261121-002": (
        "sha256:1db4cd061b8ed44c16a74131b8fd18b99a1aaf9912978a4547a19ab8cfbe9564",
        "sha256:73aa78fc7508a9a508e1990eee1489abd862141201fed197c45046d1241822c0",
        "sha256:2169fec7b56fa6d6bb082c78cdc29a590e167aa4b4785ae7dd32e1c42899c520",
    ),
    "milovi-feed-20261125-001": (
        "sha256:5c8702f05799dba96f1e20fe927fb8351010f5a3d80b716b5db0c415e9d90821",
        "sha256:ade7ed5ba38cd03ca8b97bb7e44f04f3aebf7f03506c56cf8f90a0023c27a2c5",
        "sha256:5b21ef36c094b110e32d6adc5e55fa7f982b204c19cc2469db18d1b499215ce1",
    ),
}
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
            and "Milovi Cake готовит" not in item.payload.caption
        ):
            raise ValueError(f"School release source and educational boundary mismatch: {pid}")
        if slug == "paris-brest-race-dessert":
            # The Nov 17 legacy candidate is retained as historic evidence, and
            # suppressed when the Nov 6 true Telegram receipt is verified.
            if item.payload.schema_version != 1:
                raise ValueError("Existing historical Paris-Brest release was mutated")
        elif not (
            isinstance(item.payload, GenericRichPhotoPayload)
            and item.payload.schema_version == 2
            and "<b>" in item.payload.caption
            and "<i>" in item.payload.caption
            and '<a href="https://french.milovicake.ru/articles/' in item.payload.caption
            and "Иллюстрация —" not in item.payload.expected_plain_caption
            and len(item.payload.expected_plain_caption) <= 1024
        ):
            raise ValueError(f"Future School photo has no real rich-text/URL entities: {pid}")


def migrate_two_provider_inert_editorial_revisions(checkout: Path) -> None:
    """One-time atomic (Git-committed) migration, refusing any earlier provider intent.

    Exact legacy digest, release candidate and payload IDs are sourced from the
    already-initialized protected branch. Writes happen only after BOTH records
    have been validated, never after a possible Telegram delivery.
    """
    path = checkout / STATE_FEED / "index.json"
    if not path.exists():
        return  # clean local test/state: ordinary initialize below handles it
    index = MiloviFeedIndex.model_validate_json(path.read_text(encoding="utf-8"))
    to_write: list[tuple[Path, GenericPublicationLedger]] = []
    for pid, (old_digest, old_candidate, old_payload) in RICH_EDITORIAL_PREDECESSORS.items():
        release = load_release(ROOT / "releases" / f"{pid}-runtime.json")
        ledger_path = checkout / STATE_FEED / f"{pid}.json"
        if not ledger_path.exists() and pid not in index.entries:
            continue  # entirely new, not yet initialized
        if not ledger_path.exists() or pid not in index.entries:
            raise ValueError(f"Editorial state/index missing one side of an existing record: {pid}")
        before = GenericPublicationLedger.model_validate_json(ledger_path.read_text(encoding="utf-8"))
        indexed = index.entries[pid]
        if before.release_digest == release.digest:
            load_ledger(ledger_path, release)
            if indexed.release_candidate_sha256 != release.candidate_digest() or (
                indexed.provider_payload_sha256 != release.items[0].payload.provider_payload_sha256
            ):
                raise ValueError(f"Rich School revision existing ledger/index mismatch: {pid}")
            continue
        if (
            before.release_digest != old_digest
            or before.release_id != pid
            or before.project_key != "milovi-cake"
            or before.channel_username != "@MiloviCake"
            or before.profile_sha256 != release.profile_sha256
            or set(before.entries) != {pid}
            or before.entries[pid].provider_payload_sha256 != old_payload
            or indexed.publication_id != pid
            or indexed.release_id != pid
            or indexed.release_candidate_sha256 != old_candidate
            or indexed.provider_payload_sha256 != old_payload
            or indexed.ledger_relative_path != f"content/telegram/milovi-cake/feed/{pid}.json"
        ):
            raise ValueError(f"Rich School revision is not pinned to exact protected pre-revision state: {pid}")
        entry = before.entries[pid]
        if not (
            entry.state == indexed.state == "pending"
            and entry.provider_effect == indexed.provider_effect == "impossible"
            and entry.intent_id is None
            and indexed.intent_id is None
            and entry.message_id is None
            and indexed.message_id is None
            and entry.message_url is None
            and indexed.message_url is None
            and entry.attempted_at_utc is None
            and entry.published_at_utc is None
            and entry.workflow_run_id is None
            and entry.workflow_run_attempt is None
        ):
            raise ValueError(f"Rich School revision cannot rewrite any possibly sent Telegram item: {pid}")
        new_ledger = initialize_ledger(release)
        to_write.append((ledger_path, new_ledger))
        indexed.release_candidate_sha256 = release.candidate_digest()
        indexed.provider_payload_sha256 = release.items[0].payload.provider_payload_sha256
    for ledger_path, new_ledger in to_write:
        save_ledger(ledger_path, new_ledger)
    if to_write:
        _save_index(path, index)


def initialize_all(checkout: Path) -> None:
    validate_exact_releases()
    migrate_two_provider_inert_editorial_revisions(checkout)
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
