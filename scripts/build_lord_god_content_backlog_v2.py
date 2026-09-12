#!/usr/bin/env python3
"""Build a provider-inert 60-day VK content backlog for lord-god-strength."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from video_channel_manager.telegram_models import TelegramLedger, TelegramQueue

PROJECT_KEY = "lord-god-strength"
COMMUNITY_ID = 60805374
OWNER_ID = -60805374
MOSCOW = timezone(timedelta(hours=3), name="Europe/Moscow")

BAD_TITLE_MARKERS = (
    "ошибка импорта",
    "видео недоступно",
    "правообладател",
    "день рождения",
    "свадебный час",
)
PRIORITY_MARKERS = (
    "макартур", "спраул", "лоусон", "вошер", "коломийцев", "бики",
    "сперджен", "библи", "евангел", "христ", "проповед", "церков",
    "святост", "писание", "бог", "реформац", "пуритан",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path, help="03-wall-content-audit.json")
    parser.add_argument("--telegram-root", type=Path, required=True)
    parser.add_argument("--quote-queue", type=Path, required=True)
    parser.add_argument("--quote-ledger", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--video-count", type=int, default=60)
    parser.add_argument("--telegram-count", type=int, default=9)
    parser.add_argument("--quote-count", type=int, default=24)
    parser.add_argument("--max-views", type=int, default=1500)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean_title(value: object) -> str:
    return " ".join(str(value or "").split())


def file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_score(item: dict[str, Any]) -> tuple[int, int, float]:
    title = clean_title(item.get("title")).lower()
    priority = sum(marker in title for marker in PRIORITY_MARKERS)
    views = int(item.get("views") or 0)
    published = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00"))
    return (-priority, views, -published.timestamp())


def eligible_video(item: dict[str, Any], *, max_views: int) -> bool:
    title = clean_title(item.get("title"))
    low = title.lower()
    if item.get("state") != "unposted":
        return False
    if not title or any(marker in low for marker in BAD_TITLE_MARKERS):
        return False
    if int(item.get("duration_seconds") or 0) < 120:
        return False
    views = item.get("views")
    return isinstance(views, int) and 0 <= views <= max_views


def speaker_bucket(item: dict[str, Any]) -> str:
    title = clean_title(item.get("title")).lower()
    buckets = (
        ("макартур", "macarthur"),
        ("спраул", "sproul"),
        ("лоусон", "lawson"),
        ("вошер", "washer"),
        ("коломийцев", "kolomiytsev"),
        ("бики", "beeke"),
        ("сперджен", "spurgeon"),
    )
    for marker, bucket in buckets:
        if marker in title:
            return bucket
    return "general"


def select_videos(audit: dict[str, Any], *, count: int, max_views: int) -> list[dict[str, Any]]:
    items = [x for x in audit.get("videos", []) if isinstance(x, dict) and eligible_video(x, max_views=max_views)]
    pools: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        pools.setdefault(speaker_bucket(item), []).append(item)
    for pool in pools.values():
        pool.sort(key=video_score)
    order = ("macarthur", "sproul", "lawson", "washer", "beeke", "spurgeon", "kolomiytsev", "general")
    result: list[dict[str, Any]] = []
    while len(result) < count and any(pools.values()):
        for bucket in order:
            pool = pools.get(bucket, [])
            if pool and len(result) < count:
                result.append(pool.pop(0))
    return result


def telegram_ready(post: dict[str, Any]) -> bool:
    if post.get("editorial_status") != "ready":
        return False
    if post.get("fact_check_status") != "accepted":
        return False
    review = post.get("theology_review")
    return isinstance(review, dict) and review.get("review_status") == "accepted"


def telegram_text(post: dict[str, Any]) -> str:
    title = clean_title(post.get("title"))
    lead = clean_title(post.get("lead"))
    sections = post.get("sections") if isinstance(post.get("sections"), list) else []
    body = ""
    for section in sections:
        paragraphs = section.get("paragraphs") if isinstance(section, dict) else None
        if isinstance(paragraphs, list) and paragraphs:
            body = clean_title(paragraphs[0])
            break
    parts = [part for part in (title, lead, body) if part]
    return "\n\n".join(parts)


def select_telegram(root: Path, *, count: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("post.json")):
        try:
            post = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(post, dict) or not telegram_ready(post):
            continue
        publication_id = str(post.get("publication_id") or path.parent.name)
        if publication_id in seen:
            continue
        text = telegram_text(post)
        if not text:
            continue
        selected.append(
            {
                "publication_id": publication_id,
                "title": clean_title(post.get("title")),
                "text": text,
                "source_path": path.as_posix(),
                "topic_kind": post.get("topic_kind"),
            }
        )
        seen.add(publication_id)
        if len(selected) >= count:
            break
    return selected


def load_quote_evidence(queue_path: Path, ledger_path: Path) -> tuple[TelegramQueue, TelegramLedger]:
    queue = TelegramQueue.model_validate(read_json(queue_path))
    ledger = TelegramLedger.model_validate(read_json(ledger_path))
    if ledger.queue_digest != queue.digest:
        raise ValueError("Telegram quote ledger digest differs from the immutable queue")
    queue_ids = {post.publication_id for post in queue.posts}
    ledger_ids = set(ledger.entries)
    if ledger_ids != queue_ids:
        missing = sorted(queue_ids - ledger_ids)
        extra = sorted(ledger_ids - queue_ids)
        raise ValueError(f"Telegram quote ledger coverage mismatch: missing={missing}, extra={extra}")
    for post in queue.posts:
        entry = ledger.entries[post.publication_id]
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"Telegram quote payload SHA mismatch: {post.publication_id}")
    return queue, ledger


def select_quotes(queue_path: Path, ledger_path: Path, *, count: int) -> list[dict[str, Any]]:
    queue, ledger = load_quote_evidence(queue_path, ledger_path)
    selected: list[dict[str, Any]] = []
    for post in queue.posts:
        entry = ledger.entries[post.publication_id]
        if entry.state != "published" or entry.provider_effect != "verified":
            continue
        if entry.message_id is None or entry.message_url is None or entry.published_at_utc is None:
            raise ValueError(f"published Telegram quote lacks verified message identity: {post.publication_id}")
        selected.append(
            {
                "publication_id": post.publication_id,
                "title": post.title,
                "text": post.text,
                "source_url": str(post.source.url),
                "telegram_message_id": entry.message_id,
                "telegram_message_url": entry.message_url,
                "telegram_published_at_utc": entry.published_at_utc.isoformat(),
                "telegram_payload_sha256": entry.payload_sha256,
                "telegram_source_state": "published_verified",
            }
        )
        if len(selected) >= count:
            break
    return selected


def dt_epoch(day: date, hour: int) -> tuple[str, int]:
    dt = datetime.combine(day, time(hour=hour), tzinfo=MOSCOW)
    return dt.isoformat(), int(dt.timestamp())


def build_slots(
    start: date,
    days: int,
    videos: list[dict[str, Any]],
    texts: list[dict[str, Any]],
    quotes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    video_index = 0
    text_index = 0
    quote_index = 0
    for offset in range(days):
        day = start + timedelta(days=offset)
        if video_index < len(videos):
            at, epoch = dt_epoch(day, 19)
            video = videos[video_index]
            slots.append({
                "kind": "vk_video",
                "publish_at": at,
                "publish_date": epoch,
                "video_id": video["video_id"],
                "title": clean_title(video["title"]),
                "views_at_source_snapshot": video.get("views"),
                "source_state": video.get("state"),
            })
            video_index += 1
        if day.weekday() == 1 and text_index < len(texts):
            at, epoch = dt_epoch(day, 13)
            text = texts[text_index]
            slots.append({
                "kind": "telegram_editorial",
                "publish_at": at,
                "publish_date": epoch,
                **text,
            })
            text_index += 1
        if day.weekday() in {0, 2, 4} and quote_index < len(quotes):
            at, epoch = dt_epoch(day, 12)
            quote = quotes[quote_index]
            slots.append({
                "kind": "telegram_quote",
                "publish_at": at,
                "publish_date": epoch,
                **quote,
            })
            quote_index += 1
    return sorted(slots, key=lambda x: x["publish_date"])


def build_backlog(args: argparse.Namespace) -> dict[str, Any]:
    audit = read_json(args.audit)
    if audit.get("community_id") != COMMUNITY_ID:
        raise ValueError("audit community does not match lord-god-strength")
    videos = select_videos(audit, count=args.video_count, max_views=args.max_views)
    telegram = select_telegram(args.telegram_root, count=args.telegram_count)
    quotes = select_quotes(args.quote_queue, args.quote_ledger, count=args.quote_count)
    slots = build_slots(args.start_date, args.days, videos, telegram, quotes)
    return {
        "schema_name": "video-manager.lord-god-content-backlog",
        "schema_version": 1,
        "project_key": PROJECT_KEY,
        "community_id": COMMUNITY_ID,
        "owner_id": OWNER_ID,
        "mode": "provider-inert",
        "source_audit_sha256": audit.get("audit_sha256"),
        "source_audit_status": audit.get("status"),
        "source_audit_summary": audit.get("summary"),
        "start_date": args.start_date.isoformat(),
        "days": args.days,
        "live_revalidation_required": True,
        "video_candidate_count": len(videos),
        "telegram_candidate_count": len(telegram),
        "quote_candidate_count": len(quotes),
        "telegram_quote_queue_digest": load_quote_evidence(args.quote_queue, args.quote_ledger)[0].digest,
        "telegram_quote_queue_sha256": file_sha256(args.quote_queue),
        "telegram_quote_ledger_sha256": file_sha256(args.quote_ledger),
        "telegram_quote_evidence_policy": "published+verified+payload-bound",
        "slot_count": len(slots),
        "slots": slots,
    }


def render_markdown(backlog: dict[str, Any]) -> str:
    lines = [
        "# Lord God Strength — provider-inert content backlog",
        "",
        f"- Community: {backlog['community_id']}",
        f"- Window: {backlog['start_date']} + {backlog['days']} days",
        f"- Video candidates: **{backlog['video_candidate_count']}**",
        f"- Telegram editorial candidates: **{backlog['telegram_candidate_count']}**",
        f"- Telegram published+verified quote candidates: **{backlog['quote_candidate_count']}**",
        f"- Total candidate slots: **{backlog['slot_count']}**",
        "- Live VK revalidation before scheduling: **REQUIRED**",
        "",
        "| Moscow time | Kind | Candidate | Source metric |",
        "|---|---|---|---:|",
    ]
    for slot in backlog["slots"]:
        if slot["kind"] == "vk_video":
            candidate = f"{slot['video_id']} — {slot['title']}"
            metric = str(slot.get("views_at_source_snapshot", ""))
        else:
            candidate = f"{slot['publication_id']} — {slot['title']}"
            metric = (
                f"TG #{slot.get('telegram_message_id')}"
                if slot["kind"] == "telegram_quote"
                else "TG editorial"
            )
        lines.append(f"| {slot['publish_at']} | {slot['kind']} | {candidate} | {metric} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if (
        args.days <= 0
        or args.video_count < 0
        or args.telegram_count < 0
        or args.quote_count < 0
        or args.max_views < 0
    ):
        raise SystemExit("invalid non-positive backlog limits")
    backlog = build_backlog(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(backlog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path = args.output.with_suffix(".md")
    md_path.write_text(render_markdown(backlog), encoding="utf-8")
    print(
        f"Built provider-inert backlog: slots={backlog['slot_count']} "
        f"videos={backlog['video_candidate_count']} telegram={backlog['telegram_candidate_count']} "
        f"quotes={backlog['quote_candidate_count']} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
