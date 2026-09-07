from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from video_channel_manager.lordchrist_cross_track_effect_guard import require_no_cross_track_unresolved_effects
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_historical_bundle import materialize_historical_bundle
from video_channel_manager.telegram_historical_editorial import build_historical_rich_document
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof, preflight_channel
from video_channel_manager.telegram_rich_provider import (
    HttpxTelegramRichMutationProvider,
    TelegramRichMessageDocument,
    TelegramRichOutcomeArchiveReceipt,
    TelegramRichProviderOutcome,
    TelegramRichTargetBinding,
    publish_rich_once,
)
from video_channel_manager.telegram_rich_renderer import RichRenderResult, render_rich_document
from video_channel_manager.telegram_target_binding import load_target_binding

PROJECT = "lord-god-strength"
CHANNEL = "@lordchrist"
CHAT_ID = -1001295216957
CHAT_USERNAME = "lordchrist"
BOT_ID = 8716602202
BOT_USERNAME = "preaching_mp3_bot"
REPOSITORY = "FedorMilovanov/video-channel-manager"
OWNING_ISSUE = 561
STATE_BRANCH = "state/lordchrist-telegram"
MOSCOW = ZoneInfo("Europe/Moscow")
RELEASE_SCHEMA = "video-channel-manager.telegram-historical-production-release"
LEDGER_SCHEMA = "video-channel-manager.telegram-historical-production-ledger"
INTENT_SCHEMA = "video-channel-manager.telegram-historical-production-intent"
SECOND_PASS_SCHEMA = "video-channel-manager.telegram-historical-second-pass-verification"
SUCCESSOR_BINDING_SCHEMA = "video-channel-manager.telegram-historical-successor-cycle-binding"
HISTORICAL_LEDGER_RELATIVE = "content/telegram/lordchrist/historical-editorial/publication-ledger.json"
LEGACY_LEDGER_RELATIVE = "content/telegram/lordchrist/publication-ledger.json"
RESEARCH_LEDGER_RELATIVE = "content/telegram/lordchrist/research-v2/publication-ledger.json"
RICH_CANARY_LEDGER_RELATIVE = "content/telegram/lordchrist/rich-v1/live-canary-ledger.json"
LEGACY_QUEUE_RELATIVE = "content/telegram/lordchrist/verified-30-posts.json"
_GIT_BLOB_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _verify_blob(root: Path, identity: dict[str, Any], *, label: str) -> Path:
    path = root / str(identity.get("path") or "")
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    expected = str(identity.get("git_blob_sha") or "")
    actual = _blob(path.read_bytes())
    if not expected or actual != expected:
        raise ValueError(f"{label} Git blob differs: {path} ({actual})")
    return path


def _repo_relative(root: Path, path: Path) -> str:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise ValueError("successor manifest must remain inside the repository") from exc


def release_digest(release: dict[str, Any]) -> str:
    return _sha(release)


def _planned_dates(release: dict[str, Any], offsets: tuple[int, ...]) -> tuple[str, ...]:
    start = date.fromisoformat(str(release["cycle_start_date_moscow"]))
    planned = tuple((start + timedelta(days=offset)).isoformat() for offset in offsets)
    weekdays = tuple((start + timedelta(days=offset)).isoweekday() for offset in offsets)
    if any(day not in {1, 3, 6} for day in weekdays):
        raise ValueError("historical production dates do not follow Monday/Wednesday/Saturday")
    return planned


def _validate_second_pass(value: dict[str, Any], publication_ids: tuple[str, ...]) -> None:
    if (
        value.get("schema_name") != SECOND_PASS_SCHEMA
        or value.get("schema_version") != 1
        or value.get("owning_issue") != OWNING_ISSUE
        or value.get("project_key") != PROJECT
        or value.get("channel_username") != CHANNEL
        or value.get("second_pass_reviewed_urls") != 50
        or value.get("second_pass_unique_urls") != 50
        or value.get("provider_write_performed") is not False
    ):
        raise ValueError("invalid historical second-pass verification header")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) != 50:
        raise ValueError("historical second pass must contain exactly 50 reviewed URL records")
    urls: list[str] = []
    impact_counts = {"confirm": 0, "deepen": 0, "qualify": 0}
    for sequence, raw in enumerate(entries, start=1):
        if not isinstance(raw, dict) or raw.get("sequence") != sequence:
            raise ValueError("historical second-pass sequence is not contiguous")
        url = raw.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("historical second-pass URL is not exact HTTPS")
        urls.append(url)
        if raw.get("grade_assessment") not in {"A", "B+"} or raw.get("review_status") != "reviewed":
            raise ValueError("historical second-pass record is below A/B+ or not reviewed")
        impact = str(raw.get("impact") or "")
        if impact not in impact_counts:
            raise ValueError("historical second-pass impact is invalid")
        impact_counts[impact] += 1
        bound = raw.get("publication_ids")
        if not isinstance(bound, list) or not bound or any(item not in publication_ids for item in bound):
            raise ValueError("historical second-pass record is not bound to this exact cycle")
    if len(urls) != len(set(urls)):
        raise ValueError("historical second-pass URLs are not unique")
    if value.get("impact_counts") != impact_counts:
        raise ValueError("historical second-pass impact summary differs from records")
    coverage = value.get("post_coverage")
    conclusions = value.get("conclusions")
    if not isinstance(coverage, dict) or set(coverage) != set(publication_ids):
        raise ValueError("historical second-pass coverage differs from the exact nine posts")
    if not isinstance(conclusions, dict) or set(conclusions) != set(publication_ids):
        raise ValueError("historical second-pass conclusions differ from the exact nine posts")
    if any(not isinstance(coverage[item], int) or int(coverage[item]) < 3 for item in publication_ids):
        raise ValueError("every historical post requires at least three second-pass anchors")


def load_release(path: Path, root: Path) -> tuple[dict[str, Any], Any, Any, Path, dict[str, Any]]:
    release = _read(path)
    if (
        release.get("schema_name") != RELEASE_SCHEMA
        or release.get("schema_version") != 1
        or release.get("owning_issue") != OWNING_ISSUE
        or release.get("project_key") != PROJECT
        or release.get("channel_username") != CHANNEL
        or release.get("chat_id") != CHAT_ID
        or str(release.get("chat_username") or "").casefold() != CHAT_USERNAME
        or release.get("bot_id") != BOT_ID
        or str(release.get("bot_username") or "").casefold() != BOT_USERNAME
        or release.get("state_branch") != STATE_BRANCH
        or release.get("provider_writes_authorized") is not True
        or release.get("activation_policy") != "verified_canary_then_exact_schedule"
        or release.get("max_provider_attempts_per_publication") != 1
        or release.get("blind_mutation_retries") != 0
        or release.get("backfill_policy") != "none"
        or release.get("media_policy") != "text_only_until_exact_transport_bytes_are_bound"
    ):
        raise ValueError("invalid historical production release header")

    manifest_path = _verify_blob(root, release["manifest"], label="historical manifest")
    verification_path = _verify_blob(
        root,
        release["second_pass_verification"],
        label="historical second-pass verification",
    )
    profile_path = _verify_blob(root, release["profile"], label="historical rich profile")
    legacy_profile_path = _verify_blob(root, release["legacy_profile"], label="LordChrist legacy profile")
    target_binding_path = _verify_blob(root, release["target_binding"], label="historical target binding")

    manifest, queue, registry, theology = materialize_historical_bundle(manifest_path, repo_root=root)
    publication_ids = tuple(post.publication_id for post in queue.posts)
    if (
        manifest.cycle_id != release.get("cycle_id")
        or queue.cycle_id != release.get("cycle_id")
        or tuple(release.get("publication_ids") or ()) != publication_ids
        or release.get("canary_publication_id") != publication_ids[0]
        or queue.schedule.timezone != "Europe/Moscow"
        or queue.schedule.local_time != "19:17"
        or tuple(queue.schedule.iso_weekdays) != (1, 3, 6)
        or queue.schedule.backfill_policy != "none"
    ):
        raise ValueError("historical production release differs from the sealed editorial cycle")
    if theology.digest != queue.theology_profile_sha256:
        raise ValueError("historical production theology differs from sealed editorial cycle")
    if any(post.images for post in queue.posts):
        raise ValueError("historical production v1 is text-only until exact media transport bytes are separately bound")

    verification = _read(verification_path)
    _validate_second_pass(verification, publication_ids)
    if verification.get("cycle_id") != queue.cycle_id:
        raise ValueError("second-pass verification is bound to another historical cycle")

    offsets = tuple(post.release_offset_days for post in queue.posts)
    planned = _planned_dates(release, offsets)
    if tuple(release.get("scheduled_dates_moscow") or ()) != planned:
        raise ValueError("historical production release scheduled dates differ from the sealed offsets")
    schedule = release.get("schedule")
    if not isinstance(schedule, dict) or (
        schedule.get("timezone") != "Europe/Moscow"
        or schedule.get("local_time") != "19:17"
        or tuple(schedule.get("iso_weekdays") or ()) != (1, 3, 6)
        or schedule.get("freshness_minutes") != 120
    ):
        raise ValueError("historical production schedule is not the exact reviewed cadence")
    if release.get("replenishment_guard_remaining") != 1:
        raise ValueError("historical production must require a successor before the final cycle publication")
    return (
        release,
        queue,
        registry,
        profile_path,
        {
            "legacy_profile_path": legacy_profile_path,
            "target_binding_path": target_binding_path,
            "verification": verification,
            "planned_dates": planned,
        },
    )


def build_document(
    root: Path,
    release: dict[str, Any],
    queue: Any,
    registry: Any,
    profile_path: Path,
    target_binding_path: Path,
    publication_id: str,
) -> tuple[TelegramRichMessageDocument, RichRenderResult]:
    post = next((candidate for candidate in queue.posts if candidate.publication_id == publication_id), None)
    if post is None:
        raise ValueError("historical publication is outside the exact release")
    article = build_historical_rich_document(queue, post, registry)
    if article.media or article.media_slots:
        raise ValueError("historical production v1 cannot emit unbound media")
    profile = load_channel_profile(profile_path)
    binding = load_target_binding(target_binding_path, profile)
    if (
        profile.project_key != PROJECT
        or profile.channel_username.casefold() != CHANNEL.casefold()
        or profile.provider_writes_authorized is not True
        or binding.chat_id != CHAT_ID
        or binding.chat_username.casefold() != CHAT_USERNAME
        or binding.bot_id != BOT_ID
        or binding.bot_username.casefold() != BOT_USERNAME
        or binding.can_post_messages is not True
    ):
        raise ValueError("historical rich profile/target binding differs from exact LordChrist target")
    target = TelegramRichTargetBinding(
        schema_name="video-channel-manager.telegram-rich-target-binding",
        schema_version=1,
        project_key=PROJECT,
        channel_username=CHANNEL,
        profile_sha256=profile.digest,
        target_binding_sha256=binding.digest,
        source_binding=binding,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
    )
    document, render = render_rich_document(
        article,
        target,
        publication_id=publication_id,
        provider_assigned_media_ids=(),
        skip_entity_detection=False,
    )
    if document.expected_media_sha256 is not None or document.provider_assigned_media_paths:
        raise ValueError("historical production v1 unexpectedly rendered provider media")
    return document, render


def new_ledger(release: dict[str, Any], queue: Any, planned_dates: tuple[str, ...]) -> dict[str, Any]:
    return {
        "schema_name": LEDGER_SCHEMA,
        "schema_version": 1,
        "release_id": release["release_id"],
        "release_sha256": release_digest(release),
        "owning_issue": OWNING_ISSUE,
        "project_key": PROJECT,
        "channel_username": CHANNEL,
        "cycle_id": queue.cycle_id,
        "canary_publication_id": release["canary_publication_id"],
        "canary_verified_at_utc": None,
        "successor_cycle_binding": None,
        "entries": {
            post.publication_id: {
                "publication_id": post.publication_id,
                "sequence": post.sequence,
                "scheduled_date_moscow": planned_dates[index],
                "state": "pending",
                "provider_effect": "impossible",
                "dispatch_mode": None,
                "workflow_run_id": None,
                "workflow_run_attempt": None,
                "github_sha": None,
                "document_sha256": None,
                "intent_created_at_utc": None,
                "published_at_utc": None,
                "message_id": None,
                "message_url": None,
                "error": None,
            }
            for index, post in enumerate(queue.posts)
        },
    }


def _validate_successor_binding(binding: Any, release: dict[str, Any]) -> None:
    if binding is None:
        return
    if not isinstance(binding, dict):
        raise ValueError("historical successor cycle binding must be an object or null")
    required = {
        "schema_name",
        "schema_version",
        "current_release_id",
        "current_release_sha256",
        "current_cycle_id",
        "successor_cycle_id",
        "successor_manifest_path",
        "successor_manifest_git_blob_sha",
        "successor_queue_sha256",
        "successor_source_registry_sha256",
        "successor_theology_profile_sha256",
        "verified_at_utc",
        "verified_by",
        "provider_write_performed",
    }
    if set(binding) != required:
        raise ValueError("historical successor cycle binding has unexpected fields")
    if (
        binding.get("schema_name") != SUCCESSOR_BINDING_SCHEMA
        or binding.get("schema_version") != 1
        or binding.get("current_release_id") != release["release_id"]
        or binding.get("current_release_sha256") != release_digest(release)
        or binding.get("current_cycle_id") != release["cycle_id"]
        or binding.get("successor_cycle_id") == release["cycle_id"]
        or not isinstance(binding.get("successor_cycle_id"), str)
        or not str(binding.get("successor_manifest_path") or "")
        or _GIT_BLOB_RE.fullmatch(str(binding.get("successor_manifest_git_blob_sha") or "")) is None
        or _SHA256_RE.fullmatch(str(binding.get("successor_queue_sha256") or "")) is None
        or _SHA256_RE.fullmatch(str(binding.get("successor_source_registry_sha256") or "")) is None
        or _SHA256_RE.fullmatch(str(binding.get("successor_theology_profile_sha256") or "")) is None
        or not str(binding.get("verified_by") or "").strip()
        or binding.get("provider_write_performed") is not False
    ):
        raise ValueError("historical successor cycle binding is invalid")
    verified = datetime.fromisoformat(str(binding["verified_at_utc"]).replace("Z", "+00:00"))
    if verified.tzinfo is None:
        raise ValueError("historical successor cycle binding timestamp must be timezone-aware")


def successor_cycle_is_bound(ledger: dict[str, Any], release: dict[str, Any]) -> bool:
    binding = ledger.get("successor_cycle_binding")
    _validate_successor_binding(binding, release)
    return binding is not None


def load_ledger(
    path: Path,
    release: dict[str, Any],
    queue: Any,
    planned_dates: tuple[str, ...],
    *,
    create: bool = False,
) -> dict[str, Any]:
    ledger = new_ledger(release, queue, planned_dates) if create and not path.exists() else _read(path)
    entries = ledger.get("entries")
    expected_ids = tuple(post.publication_id for post in queue.posts)
    if (
        ledger.get("schema_name") != LEDGER_SCHEMA
        or ledger.get("schema_version") != 1
        or ledger.get("release_id") != release["release_id"]
        or ledger.get("release_sha256") != release_digest(release)
        or ledger.get("owning_issue") != OWNING_ISSUE
        or ledger.get("project_key") != PROJECT
        or ledger.get("channel_username") != CHANNEL
        or ledger.get("cycle_id") != queue.cycle_id
        or ledger.get("canary_publication_id") != release["canary_publication_id"]
        or not isinstance(entries, dict)
        or tuple(entries) != expected_ids
    ):
        raise ValueError("historical production ledger is bound to another release/cycle")
    _validate_successor_binding(ledger.get("successor_cycle_binding"), release)
    for index, publication_id in enumerate(expected_ids):
        raw = entries[publication_id]
        if not isinstance(raw, dict) or (
            raw.get("publication_id") != publication_id
            or raw.get("sequence") != index + 1
            or raw.get("scheduled_date_moscow") != planned_dates[index]
            or raw.get("state") not in {"pending", "intent", "published", "may_exist", "failed_no_effect"}
            or raw.get("provider_effect")
            not in {"impossible", "verified", "may_exist", "not_dispatched", "confirmed_absent"}
        ):
            raise ValueError("historical production ledger entry is invalid")
    return ledger


def bind_successor_cycle(
    root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    successor_manifest_path: Path,
    *,
    verified_by: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if successor_cycle_is_bound(ledger, release):
        raise ValueError("historical successor cycle is already durably bound")
    if not verified_by.strip():
        raise ValueError("successor cycle binding requires verified_by")
    resolved = successor_manifest_path if successor_manifest_path.is_absolute() else root / successor_manifest_path
    if not resolved.is_file():
        raise ValueError("successor historical manifest does not exist")
    manifest, queue, registry, theology = materialize_historical_bundle(resolved, repo_root=root)
    if (
        manifest.project_key != PROJECT
        or manifest.channel_username.casefold() != CHANNEL.casefold()
        or manifest.cycle_id == release["cycle_id"]
        or queue.cycle_id != manifest.cycle_id
        or len(queue.posts) != len(release["publication_ids"])
        or queue.schedule.timezone != "Europe/Moscow"
        or queue.schedule.local_time != "19:17"
        or tuple(queue.schedule.iso_weekdays) != (1, 3, 6)
        or queue.schedule.backfill_policy != "none"
    ):
        raise ValueError("successor historical cycle does not satisfy the reviewed production cadence")
    verified_at = (now or datetime.now(tz=UTC)).astimezone(UTC).isoformat()
    binding = {
        "schema_name": SUCCESSOR_BINDING_SCHEMA,
        "schema_version": 1,
        "current_release_id": release["release_id"],
        "current_release_sha256": release_digest(release),
        "current_cycle_id": release["cycle_id"],
        "successor_cycle_id": manifest.cycle_id,
        "successor_manifest_path": _repo_relative(root, resolved),
        "successor_manifest_git_blob_sha": _blob(resolved.read_bytes()),
        "successor_queue_sha256": queue.digest,
        "successor_source_registry_sha256": registry.digest,
        "successor_theology_profile_sha256": theology.digest,
        "verified_at_utc": verified_at,
        "verified_by": verified_by.strip(),
        "provider_write_performed": False,
    }
    _validate_successor_binding(binding, release)
    ledger["successor_cycle_binding"] = binding
    return ledger


def _entry(ledger: dict[str, Any], publication_id: str) -> dict[str, Any]:
    entries = ledger["entries"]
    if not isinstance(entries, dict):
        raise ValueError("historical ledger entries are invalid")
    raw = entries.get(publication_id)
    if not isinstance(raw, dict):
        raise ValueError("historical publication is outside the durable release ledger")
    return raw


def _require_old_rich_terminal(state_root: Path) -> None:
    ledger = _read(state_root / RICH_CANARY_LEDGER_RELATIVE)
    entries = ledger.get("entries")
    if not isinstance(entries, dict) or len(entries) != 1:
        raise ValueError("historical writer cannot prove the prior LordChrist rich canary terminal state")
    raw = next(iter(entries.values()))
    if not isinstance(raw, dict) or raw.get("state") != "published" or raw.get("provider_effect") != "verified":
        raise ValueError("prior LordChrist rich provider effect is unresolved")


def _verified_today(path: Path, today_moscow: str) -> int:
    ledger = _read(path)
    entries = ledger.get("entries")
    if not isinstance(entries, dict):
        raise ValueError(f"ledger has no entries: {path}")
    count = 0
    for raw in entries.values():
        if not isinstance(raw, dict) or raw.get("state") != "published" or raw.get("provider_effect") != "verified":
            continue
        published = raw.get("published_at_utc")
        if not published:
            raise ValueError("verified publication lacks published_at_utc")
        published_date = (
            datetime.fromisoformat(str(published).replace("Z", "+00:00")).astimezone(MOSCOW).date().isoformat()
        )
        if published_date == today_moscow:
            count += 1
    return count


def _guard_unresolved(ledger: dict[str, Any]) -> None:
    entries = ledger.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("historical ledger entries are invalid")
    for raw in entries.values():
        if isinstance(raw, dict) and raw.get("state") in {"intent", "may_exist"}:
            raise ValueError(
                f"unresolved historical provider state blocks writer: {raw.get('publication_id')}={raw.get('state')}"
            )


def guard_state(
    root: Path,
    state_root: Path,
    release: dict[str, Any],
    ledger: dict[str, Any],
    legacy_profile_path: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    _guard_unresolved(ledger)
    _require_old_rich_terminal(state_root)
    cross_track = require_no_cross_track_unresolved_effects(
        profile_path=legacy_profile_path,
        legacy_queue_path=root / LEGACY_QUEUE_RELATIVE,
        legacy_ledger_path=state_root / LEGACY_LEDGER_RELATIVE,
        research_ledger_path=state_root / RESEARCH_LEDGER_RELATIVE,
    )
    current = (now or datetime.now(tz=UTC)).astimezone(MOSCOW)
    today = current.date().isoformat()
    quote_count = _verified_today(state_root / LEGACY_LEDGER_RELATIVE, today)
    entries = ledger.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("historical ledger entries are invalid")
    historical_count = 0
    for raw in entries.values():
        if (
            not isinstance(raw, dict)
            or raw.get("state") != "published"
            or raw.get("provider_effect") != "verified"
            or not raw.get("published_at_utc")
        ):
            continue
        published_date = (
            datetime.fromisoformat(str(raw["published_at_utc"]).replace("Z", "+00:00"))
            .astimezone(MOSCOW)
            .date()
            .isoformat()
        )
        historical_count += published_date == today
    if historical_count >= 1:
        raise ValueError("historical rich daily verified limit is already used")
    if quote_count + historical_count >= int(release["max_combined_verified_per_day_moscow"]):
        raise ValueError("combined LordChrist verified daily limit is already used")
    return {
        "clear": True,
        "moscow_date": today,
        "quote_verified_today": quote_count,
        "historical_verified_today": historical_count,
        "combined_verified_today": quote_count + historical_count,
        "cross_track": cross_track,
        "provider_write_performed": False,
    }


@dataclass(frozen=True)
class ScheduledDecision:
    active: bool
    publication_id: str | None
    reason: str


def decide_scheduled(
    release: dict[str, Any],
    ledger: dict[str, Any],
    publication_ids: tuple[str, ...],
    planned_dates: tuple[str, ...],
    *,
    now: datetime | None = None,
) -> ScheduledDecision:
    current = (now or datetime.now(tz=UTC)).astimezone(MOSCOW)
    if ledger.get("canary_verified_at_utc") is None:
        return ScheduledDecision(False, None, "canary_not_verified")
    today = current.date().isoformat()
    if today not in planned_dates:
        return ScheduledDecision(False, None, "no_historical_slot_today")
    index = planned_dates.index(today)
    publication_id = publication_ids[index]
    scheduled = datetime.combine(current.date(), time(19, 17), tzinfo=MOSCOW)
    age = current - scheduled
    schedule = release["schedule"]
    if not isinstance(schedule, dict):
        raise ValueError("historical release schedule is invalid")
    freshness = timedelta(minutes=int(schedule["freshness_minutes"]))
    if age < timedelta(0):
        return ScheduledDecision(False, publication_id, "slot_not_started")
    if age > freshness:
        return ScheduledDecision(False, publication_id, "slot_expired_no_backfill")
    raw = _entry(ledger, publication_id)
    if raw["state"] == "published" and raw.get("provider_effect") == "verified":
        return ScheduledDecision(False, publication_id, "slot_already_verified")
    if raw["state"] != "pending":
        raise ValueError(f"scheduled historical publication is not safely pending: {raw['state']}")
    entries = ledger.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("historical ledger entries are invalid")
    remaining = sum(isinstance(item, dict) and item.get("state") == "pending" for item in entries.values())
    if remaining <= int(release["replenishment_guard_remaining"]) and not successor_cycle_is_bound(ledger, release):
        return ScheduledDecision(False, publication_id, "successor_cycle_required_before_exhaustion")
    return ScheduledDecision(True, publication_id, "active_exact_historical_slot")


def coverage_status(release: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    entries = ledger.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("historical ledger entries are invalid")
    pending = [
        str(raw["publication_id"])
        for raw in entries.values()
        if isinstance(raw, dict) and raw.get("state") == "pending"
    ]
    terminal_verified = [
        str(raw["publication_id"])
        for raw in entries.values()
        if isinstance(raw, dict) and raw.get("state") == "published" and raw.get("provider_effect") == "verified"
    ]
    terminal_no_effect = [
        str(raw["publication_id"])
        for raw in entries.values()
        if isinstance(raw, dict) and raw.get("state") == "failed_no_effect"
    ]
    guard_remaining = int(release["replenishment_guard_remaining"])
    successor_bound = successor_cycle_is_bound(ledger, release)
    return {
        "release_id": release["release_id"],
        "pending_count": len(pending),
        "verified_count": len(terminal_verified),
        "terminal_no_effect_count": len(terminal_no_effect),
        "pending_publication_ids": pending,
        "successor_cycle_verified": successor_bound,
        "successor_cycle_binding": ledger.get("successor_cycle_binding"),
        "replenishment_warning": len(pending) <= guard_remaining + 2 and not successor_bound,
        "exhaustion_block_active": len(pending) <= guard_remaining and not successor_bound,
        "provider_write_performed": False,
    }


def _target_proof(path: Path) -> GenericTargetProof:
    return GenericTargetProof.model_validate_json(path.read_text(encoding="utf-8"))


def _require_target(
    proof: GenericTargetProof,
    document: TelegramRichMessageDocument,
    *,
    now: datetime | None = None,
) -> None:
    if (
        proof.chat_id,
        proof.chat_username.casefold(),
        proof.bot_id,
        proof.bot_username.casefold(),
        proof.can_post_messages,
        proof.profile_sha256,
    ) != (
        document.target.chat_id,
        document.target.chat_username.casefold(),
        document.target.bot_id,
        document.target.bot_username.casefold(),
        True,
        document.target.profile_sha256,
    ):
        raise ValueError("fresh historical target proof differs from exact rich target")
    age = (now or datetime.now(tz=UTC)) - proof.checked_at_utc.astimezone(UTC)
    if age < -timedelta(minutes=1) or age > timedelta(minutes=15):
        raise ValueError("historical target proof is stale")


def run_preflight(profile_path: Path, *, token: str) -> GenericTargetProof:
    profile = load_channel_profile(profile_path)
    return preflight_channel(
        profile,
        token=token,
        expected_chat_id=CHAT_ID,
        expected_bot_id=BOT_ID,
        expected_bot_username=BOT_USERNAME,
    )


def prepare(
    root: Path,
    state_root: Path,
    release: dict[str, Any],
    queue: Any,
    registry: Any,
    profile_path: Path,
    target_binding_path: Path,
    legacy_profile_path: Path,
    planned_dates: tuple[str, ...],
    ledger: dict[str, Any],
    target_path: Path,
    *,
    mode: str,
    expected_publication_id: str | None,
    repository: str,
    sha: str,
    run_id: str,
    attempt: str,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any], str]:
    publication_ids = tuple(post.publication_id for post in queue.posts)
    if mode == "scheduled":
        decision = decide_scheduled(release, ledger, publication_ids, planned_dates, now=now)
        if not decision.active:
            return None, ledger, decision.reason
        if decision.publication_id is None:
            raise AssertionError("active historical schedule has no publication id")
        publication_id = decision.publication_id
    elif mode == "manual_canary":
        publication_id = str(expected_publication_id or "")
        if publication_id != release["canary_publication_id"]:
            raise ValueError("manual historical production is restricted to the exact canary publication")
        if ledger.get("canary_verified_at_utc") is not None:
            raise ValueError("historical canary is already verified")
        not_before = datetime.fromisoformat(str(release["canary_not_before_moscow"]))
        not_after = datetime.fromisoformat(str(release["canary_not_after_moscow"]))
        current = (now or datetime.now(tz=UTC)).astimezone(MOSCOW)
        if current < not_before or current > not_after:
            raise ValueError("historical canary authorization window is not active")
    else:
        raise ValueError("historical prepare mode must be scheduled or manual_canary")

    guard_state(root, state_root, release, ledger, legacy_profile_path, now=now)
    raw = _entry(ledger, publication_id)
    if raw["state"] != "pending" or raw.get("provider_effect") != "impossible":
        raise ValueError("historical publication is not exact pending/impossible")
    if repository != REPOSITORY or attempt != "1":
        raise ValueError("historical production requires exact repository and first workflow attempt")
    document, render = build_document(
        root,
        release,
        queue,
        registry,
        profile_path,
        target_binding_path,
        publication_id,
    )
    target = _target_proof(target_path)
    _require_target(target, document, now=now)
    created_at = (now or datetime.now(tz=UTC)).astimezone(UTC).isoformat()
    intent = {
        "schema_name": INTENT_SCHEMA,
        "schema_version": 1,
        "release_id": release["release_id"],
        "release_sha256": release_digest(release),
        "owning_issue": OWNING_ISSUE,
        "cycle_id": release["cycle_id"],
        "publication_id": publication_id,
        "dispatch_mode": mode,
        "scheduled_date_moscow": raw["scheduled_date_moscow"],
        "github_repository": repository,
        "github_sha": sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": attempt,
        "document_sha256": document.document_sha256,
        "render_sha256": render.render_sha256,
        "target_proof_sha256": _sha(target.model_dump(mode="json")),
        "created_at_utc": created_at,
        "mutation_request_limit": 1,
        "automatic_retry_allowed": False,
        "blind_retry_allowed": False,
        "fallback_allowed": False,
        "media_policy": release["media_policy"],
    }
    raw.update(
        {
            "state": "intent",
            "provider_effect": "impossible",
            "dispatch_mode": mode,
            "workflow_run_id": run_id,
            "workflow_run_attempt": attempt,
            "github_sha": sha,
            "document_sha256": document.document_sha256,
            "intent_created_at_utc": created_at,
            "error": None,
        }
    )
    return intent, ledger, "prepared"


class _Archiver:
    def __init__(self, path: Path) -> None:
        self.path = path

    def archive(self, outcome_bytes: bytes, *, outcome_sha256: str) -> TelegramRichOutcomeArchiveReceipt:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(outcome_bytes)
        if "sha256:" + hashlib.sha256(outcome_bytes).hexdigest() != outcome_sha256:
            raise ValueError("historical provider outcome archive digest mismatch")
        return TelegramRichOutcomeArchiveReceipt(
            schema_name="video-channel-manager.telegram-rich-outcome-archive-receipt",
            schema_version=1,
            outcome_sha256=outcome_sha256,
            archive_reference=f"workflow-local:{self.path}",
            durable_before_state_mutation=True,
        )


def send(
    root: Path,
    release: dict[str, Any],
    queue: Any,
    registry: Any,
    profile_path: Path,
    target_binding_path: Path,
    intent: dict[str, Any],
    target_path: Path,
    outcome_path: Path,
    *,
    token: str,
) -> TelegramRichProviderOutcome:
    publication_id = str(intent.get("publication_id") or "")
    if (
        intent.get("schema_name") != INTENT_SCHEMA
        or intent.get("release_sha256") != release_digest(release)
        or intent.get("owning_issue") != OWNING_ISSUE
        or intent.get("github_repository") != REPOSITORY
        or intent.get("workflow_run_attempt") != "1"
        or intent.get("mutation_request_limit") != 1
        or intent.get("automatic_retry_allowed") is not False
        or intent.get("blind_retry_allowed") is not False
        or intent.get("fallback_allowed") is not False
        or publication_id not in tuple(release["publication_ids"])
    ):
        raise ValueError("historical durable intent differs from exact release authority")
    document, render = build_document(
        root,
        release,
        queue,
        registry,
        profile_path,
        target_binding_path,
        publication_id,
    )
    if document.document_sha256 != intent.get("document_sha256") or render.render_sha256 != intent.get("render_sha256"):
        raise ValueError("historical rich document changed after durable intent")
    target = _target_proof(target_path)
    _require_target(target, document)
    if _sha(target.model_dump(mode="json")) != intent.get("target_proof_sha256"):
        raise ValueError("historical target proof changed after durable intent")
    profile = load_channel_profile(profile_path)
    provider = HttpxTelegramRichMutationProvider(token=token)
    try:
        archived = publish_rich_once(
            document,
            target,
            provider,
            _Archiver(outcome_path),
            profile=profile,
            state_mutation=None,
        )
    finally:
        provider.close()
    return archived.outcome


def apply(
    ledger: dict[str, Any],
    release: dict[str, Any],
    intent: dict[str, Any],
    outcome: TelegramRichProviderOutcome,
) -> dict[str, Any]:
    publication_id = str(intent.get("publication_id") or "")
    raw = _entry(ledger, publication_id)
    if (
        raw["state"] != "intent"
        or raw.get("document_sha256") != intent.get("document_sha256")
        or outcome.publication_id != publication_id
        or outcome.document_sha256 != intent.get("document_sha256")
    ):
        raise ValueError("historical provider outcome has no exact durable intent")
    if outcome.provider_effect == "verified":
        published_at = datetime.now(tz=UTC).isoformat()
        raw.update(
            {
                "state": "published",
                "provider_effect": "verified",
                "published_at_utc": published_at,
                "message_id": outcome.message_id,
                "message_url": outcome.message_url,
                "error": None,
            }
        )
        if publication_id == release["canary_publication_id"]:
            ledger["canary_verified_at_utc"] = published_at
    elif outcome.provider_effect == "may_exist":
        raw.update(
            {
                "state": "may_exist",
                "provider_effect": "may_exist",
                "error": outcome.error or "ambiguous provider effect",
            }
        )
    else:
        raw.update(
            {
                "state": "failed_no_effect",
                "provider_effect": outcome.provider_effect,
                "error": outcome.error or f"provider effect: {outcome.provider_effect}",
            }
        )
    return ledger


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="cmd", required=True)
    commands = (
        "preview",
        "ensure-ledger",
        "guard",
        "coverage",
        "bind-successor",
        "preflight",
        "prepare",
        "send",
        "apply",
        "status",
    )
    for name in commands:
        command = sub.add_parser(name)
        command.add_argument("--release", type=Path, required=True)
        command.add_argument("--root", type=Path, default=Path("."))
        if name in {"ensure-ledger", "guard", "coverage", "bind-successor", "prepare", "apply", "status"}:
            command.add_argument("--ledger", type=Path, required=True)
        if name in {"guard", "prepare"}:
            command.add_argument("--state-root", type=Path, required=True)
        if name == "bind-successor":
            command.add_argument("--successor-manifest", type=Path, required=True)
            command.add_argument("--verified-by", required=True)
        if name == "preflight":
            command.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            command.add_argument("--mode", choices=("scheduled", "manual_canary"), required=True)
            command.add_argument("--expected-publication-id")
            command.add_argument("--target-proof", type=Path, required=True)
            command.add_argument("--github-repository", required=True)
            command.add_argument("--github-sha", required=True)
            command.add_argument("--run-id", required=True)
            command.add_argument("--run-attempt", required=True)
            command.add_argument("--intent-output", type=Path, required=True)
        if name == "send":
            command.add_argument("--intent", type=Path, required=True)
            command.add_argument("--target-proof", type=Path, required=True)
            command.add_argument("--outcome", type=Path, required=True)
        if name == "apply":
            command.add_argument("--intent", type=Path, required=True)
            command.add_argument("--outcome", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    release, queue, registry, profile_path, aux = load_release(args.release, args.root)
    planned_dates = tuple(aux["planned_dates"])
    target_binding_path = Path(aux["target_binding_path"])
    legacy_profile_path = Path(aux["legacy_profile_path"])

    if args.cmd == "preview":
        publication_id = str(release["canary_publication_id"])
        document, render = build_document(
            args.root,
            release,
            queue,
            registry,
            profile_path,
            target_binding_path,
            publication_id,
        )
        print(
            json.dumps(
                {
                    "release_id": release["release_id"],
                    "release_sha256": release_digest(release),
                    "cycle_id": release["cycle_id"],
                    "canary_publication_id": publication_id,
                    "document_sha256": document.document_sha256,
                    "render_sha256": render.render_sha256,
                    "scheduled_dates_moscow": list(planned_dates),
                    "provider_write_performed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.cmd == "ensure-ledger":
        ledger = load_ledger(args.ledger, release, queue, planned_dates, create=True)
        _write(args.ledger, ledger)
        print(json.dumps({"release_id": release["release_id"], "created": True, "provider_write_performed": False}))
        return 0

    if args.cmd == "preflight":
        proof = run_preflight(profile_path, token=os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"])
        _write(args.output, proof.model_dump(mode="json"))
        print(proof.model_dump_json())
        return 0

    if args.cmd == "send":
        outcome = send(
            args.root,
            release,
            queue,
            registry,
            profile_path,
            target_binding_path,
            _read(args.intent),
            args.target_proof,
            args.outcome,
            token=os.environ["LORDCHRIST_TELEGRAM_BOT_TOKEN"],
        )
        print(outcome.model_dump_json())
        return 0

    ledger = load_ledger(args.ledger, release, queue, planned_dates)

    if args.cmd == "guard":
        print(
            json.dumps(
                guard_state(args.root, args.state_root, release, ledger, legacy_profile_path),
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "coverage":
        print(json.dumps(coverage_status(release, ledger), ensure_ascii=False))
        return 0
    if args.cmd == "bind-successor":
        updated = bind_successor_cycle(
            args.root,
            release,
            ledger,
            args.successor_manifest,
            verified_by=args.verified_by,
        )
        _write(args.ledger, updated)
        print(json.dumps(updated["successor_cycle_binding"], ensure_ascii=False))
        return 0
    if args.cmd == "prepare":
        intent, updated, reason = prepare(
            args.root,
            args.state_root,
            release,
            queue,
            registry,
            profile_path,
            target_binding_path,
            legacy_profile_path,
            planned_dates,
            ledger,
            args.target_proof,
            mode=args.mode,
            expected_publication_id=args.expected_publication_id,
            repository=args.github_repository,
            sha=args.github_sha,
            run_id=args.run_id,
            attempt=args.run_attempt,
        )
        if intent is None:
            print(json.dumps({"prepared": False, "reason": reason, "provider_write_performed": False}))
            return 3
        _write(args.intent_output, intent)
        _write(args.ledger, updated)
        print(
            json.dumps(
                {"prepared": True, "publication_id": intent["publication_id"], "reason": reason},
                ensure_ascii=False,
            )
        )
        return 0
    if args.cmd == "apply":
        outcome = TelegramRichProviderOutcome.model_validate_json(args.outcome.read_text(encoding="utf-8"))
        updated = apply(ledger, release, _read(args.intent), outcome)
        _write(args.ledger, updated)
        print(json.dumps(_entry(updated, str(outcome.publication_id)), ensure_ascii=False))
        return 0
    if args.cmd == "status":
        print(json.dumps(ledger, ensure_ascii=False))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
