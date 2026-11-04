#!/usr/bin/env python3
"""Build a provider-inert 60-day VK content backlog for lord-god-strength."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from video_channel_manager.telegram_historical_production import release_digest
from video_channel_manager.telegram_models import TelegramLedger, TelegramQueue
from video_channel_manager.telegram_quote_runtime import SuccessorRuntimeQueue, load_active_queue

QuoteQueue = TelegramQueue | SuccessorRuntimeQueue

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
    "макартур",
    "спраул",
    "лоусон",
    "вошер",
    "коломийцев",
    "бики",
    "сперджен",
    "библи",
    "евангел",
    "христ",
    "проповед",
    "церков",
    "святост",
    "писание",
    "бог",
    "реформац",
    "пуритан",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path, nargs="?", default=None, help="03-wall-content-audit.json")
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="build the text lane (quotes + historical) without a wall/video audit; "
        "required when the credential is a community access key, because wall.get/video.get "
        "are unavailable under group authorization (VK error 27)",
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--historical-release", type=Path, required=True)
    parser.add_argument("--historical-ledger", type=Path, required=True)
    parser.add_argument("--quote-queue", type=Path, required=True)
    parser.add_argument("--quote-ledger", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--video-count", type=int, default=60)
    parser.add_argument("--telegram-count", type=int, default=9)
    parser.add_argument("--quote-count", type=int, default=24)
    parser.add_argument(
        "--historical-text-mode",
        choices=("excerpt", "full"),
        default="excerpt",
        help="excerpt keeps the historical title+lead+first paragraph; full renders the complete reviewed post",
    )
    parser.add_argument("--max-views", type=int, default=1500)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean_title(value: object) -> str:
    return " ".join(str(value or "").split())


def read_json_evidence(path: Path) -> tuple[Any, str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def _git_bytes(root: Path, relative_path: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative_path}"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Git cannot read committed evidence {relative_path}: {error}")
    return completed.stdout


def git_blob_sha(root: Path, relative_path: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relative_path}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise ValueError(f"Git cannot resolve committed evidence {relative_path}")
    return completed.stdout.strip()


def read_committed_json(root: Path, relative_path: str) -> Any:
    return json.loads(_git_bytes(root, relative_path).decode("utf-8-sig"))


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


def telegram_text(post: dict[str, Any], *, text_mode: str = "excerpt") -> str:
    if text_mode not in {"excerpt", "full"}:
        raise ValueError(f"unsupported historical text mode: {text_mode}")
    title = clean_title(post.get("title"))
    lead = clean_title(post.get("lead"))
    sections = post.get("sections") if isinstance(post.get("sections"), list) else []
    if text_mode == "full":
        parts = [part for part in (title, lead) if part]
        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = clean_title(section.get("heading"))
            if heading:
                parts.append(heading)
            paragraphs = section.get("paragraphs")
            if isinstance(paragraphs, list):
                parts.extend(clean_title(paragraph) for paragraph in paragraphs if clean_title(paragraph))
        return "\n\n".join(part for part in parts if part)
    body = ""
    for section in sections:
        paragraphs = section.get("paragraphs") if isinstance(section, dict) else None
        if isinstance(paragraphs, list) and paragraphs:
            body = clean_title(paragraphs[0])
            break
    parts = [part for part in (title, lead, body) if part]
    return "\n\n".join(parts)


def load_historical_evidence(
    root: Path,
    release_path: Path,
    ledger_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str, str]:
    raw_release, release_file_sha256 = read_json_evidence(release_path)
    raw_ledger, ledger_file_sha256 = read_json_evidence(ledger_path)
    if not isinstance(raw_release, dict) or not isinstance(raw_ledger, dict):
        raise ValueError("historical release/ledger roots must be objects")
    if (
        raw_ledger.get("project_key") != PROJECT_KEY
        or str(raw_ledger.get("channel_username") or "").casefold() != "@lordchrist"
        or raw_ledger.get("release_id") != raw_release.get("release_id")
        or raw_ledger.get("release_sha256") != release_digest(raw_release)
    ):
        raise ValueError("historical production ledger is not bound to the exact LordChrist release")

    publication_ids = raw_release.get("publication_ids")
    if not isinstance(publication_ids, list) or len(publication_ids) != 1:
        raise ValueError("historical VK cross-post release must bind exactly one publication")
    publication_id = str(publication_ids[0] or "")
    revision_binding = raw_release.get("revision")
    if not isinstance(revision_binding, dict):
        raise ValueError("historical release lacks an exact revision binding")
    revision_path = str(revision_binding.get("path") or "")
    revision_blob = str(revision_binding.get("git_blob_sha") or "")
    if not revision_path or git_blob_sha(root, revision_path) != revision_blob:
        raise ValueError("historical committed revision blob differs from the published release")
    revision = read_committed_json(root, revision_path)
    if not isinstance(revision, dict) or revision.get("publication_id") != publication_id:
        raise ValueError("historical revision publication identity differs from the release")

    post_binding = revision.get("post")
    if not isinstance(post_binding, dict):
        raise ValueError("historical revision lacks a committed post binding")
    post_path = str(post_binding.get("path") or "")
    post_blob = str(post_binding.get("git_blob_sha") or "")
    if not post_path or git_blob_sha(root, post_path) != post_blob:
        raise ValueError("historical committed post blob differs from the reviewed revision")
    post = read_committed_json(root, post_path)
    if not isinstance(post, dict) or post.get("publication_id") != publication_id:
        raise ValueError("historical committed post identity differs from the release")
    return raw_release, raw_ledger, revision, post, release_file_sha256, ledger_file_sha256


def select_published_historical(
    root: Path,
    release_path: Path,
    ledger_path: Path,
    *,
    count: int,
    text_mode: str = "excerpt",
) -> tuple[list[dict[str, Any]], str, str, str]:
    release, ledger, revision, post, release_file_sha256, ledger_file_sha256 = load_historical_evidence(
        root,
        release_path,
        ledger_path,
    )
    publication_id = str(post["publication_id"])
    entries = ledger.get("entries")
    entry = entries.get(publication_id) if isinstance(entries, dict) else None
    if not isinstance(entry, dict):
        return [], release_file_sha256, ledger_file_sha256, release_digest(release)
    if entry.get("state") != "published" or entry.get("provider_effect") != "verified":
        return [], release_file_sha256, ledger_file_sha256, release_digest(release)
    message_id = entry.get("message_id")
    message_url = str(entry.get("message_url") or "")
    document_sha256 = str(entry.get("document_sha256") or "")
    if (
        type(message_id) is not int
        or message_id <= 0
        or message_url != f"https://t.me/lordchrist/{message_id}"
        or not document_sha256.startswith("sha256:")
        or not entry.get("published_at_utc")
    ):
        raise ValueError(f"published historical Telegram entry lacks exact provider evidence: {publication_id}")
    if count <= 0:
        return [], release_file_sha256, ledger_file_sha256, release_digest(release)
    text = telegram_text(post, text_mode=text_mode)
    if not text:
        raise ValueError(f"published historical Telegram post has no reusable text: {publication_id}")
    return (
        [
            {
                "publication_id": publication_id,
                "title": clean_title(post.get("title")),
                "text": text,
                "source_url": message_url,
                "source_path": str(revision["post"]["path"]),
                "topic_kind": post.get("topic_kind"),
                "telegram_message_id": message_id,
                "telegram_message_url": message_url,
                "telegram_published_at_utc": str(entry["published_at_utc"]),
                "telegram_document_sha256": document_sha256,
                "telegram_release_id": str(release["release_id"]),
                "telegram_release_sha256": str(ledger["release_sha256"]),
                "historical_revision_git_blob_sha": str(release["revision"]["git_blob_sha"]),
                "historical_post_git_blob_sha": str(revision["post"]["git_blob_sha"]),
                "telegram_source_state": "published_verified_historical",
            }
        ],
        release_file_sha256,
        ledger_file_sha256,
        release_digest(release),
    )


def load_quote_evidence(
    queue_path: Path,
    ledger_path: Path,
) -> tuple[list[dict[str, Any]], TelegramLedger, str, str, str]:
    """Load either the legacy 30-post queue or a successor runtime queue.

    Both queue shapes expose ``publication_id``/``title``/``text``/
    ``payload_sha256`` posts and a ``digest`` bound to the durable ledger.
    The successor runtime source carries only author/work, so its
    ``source_url`` is empty and the Telegram message URL remains the
    cross-post provenance.
    """

    _raw_queue, queue_sha256 = read_json_evidence(queue_path)
    raw_ledger, ledger_sha256 = read_json_evidence(ledger_path)
    queue: QuoteQueue = load_active_queue(queue_path)
    ledger = TelegramLedger.model_validate(raw_ledger)
    if ledger.queue_digest != queue.digest:
        raise ValueError("Telegram quote ledger digest differs from the immutable queue")
    queue_ids = {post.publication_id for post in queue.posts}
    ledger_ids = set(ledger.entries)
    if ledger_ids != queue_ids:
        missing = sorted(queue_ids - ledger_ids)
        extra = sorted(ledger_ids - queue_ids)
        raise ValueError(f"Telegram quote ledger coverage mismatch: missing={missing}, extra={extra}")
    posts: list[dict[str, Any]] = []
    for post in queue.posts:
        entry = ledger.entries[post.publication_id]
        if entry.payload_sha256 != post.payload_sha256:
            raise ValueError(f"Telegram quote payload SHA mismatch: {post.publication_id}")
        posts.append(
            {
                "publication_id": post.publication_id,
                "title": post.title,
                "text": post.text,
                "source_url": str(getattr(post.source, "url", "") or ""),
            }
        )
    return posts, ledger, queue_sha256, ledger_sha256, queue.digest


def select_published_quotes(
    posts: list[dict[str, Any]],
    ledger: TelegramLedger,
    *,
    count: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for post in posts:
        entry = ledger.entries[post["publication_id"]]
        if entry.state != "published" or entry.provider_effect != "verified":
            continue
        if entry.message_id is None or entry.message_url is None or entry.published_at_utc is None:
            raise ValueError(f"published Telegram quote lacks verified message identity: {post['publication_id']}")
        selected.append(
            {
                "publication_id": post["publication_id"],
                "title": post["title"],
                "text": post["text"],
                "source_url": post["source_url"],
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


def select_quotes(queue_path: Path, ledger_path: Path, *, count: int) -> list[dict[str, Any]]:
    posts, ledger, _, _, _ = load_quote_evidence(queue_path, ledger_path)
    return select_published_quotes(posts, ledger, count=count)


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
            slots.append(
                {
                    "kind": "vk_video",
                    "publish_at": at,
                    "publish_date": epoch,
                    "video_id": video["video_id"],
                    "title": clean_title(video["title"]),
                    "views_at_source_snapshot": video.get("views"),
                    "source_state": video.get("state"),
                }
            )
            video_index += 1
        if day.weekday() == 1 and text_index < len(texts):
            at, epoch = dt_epoch(day, 13)
            text = texts[text_index]
            slots.append(
                {
                    "kind": "telegram_editorial",
                    "publish_at": at,
                    "publish_date": epoch,
                    **text,
                }
            )
            text_index += 1
        if day.weekday() in {0, 2, 4} and quote_index < len(quotes):
            at, epoch = dt_epoch(day, 12)
            quote = quotes[quote_index]
            slots.append(
                {
                    "kind": "telegram_quote",
                    "publish_at": at,
                    "publish_date": epoch,
                    **quote,
                }
            )
            quote_index += 1
    return sorted(slots, key=lambda x: x["publish_date"])


def build_backlog(args: argparse.Namespace) -> dict[str, Any]:
    if args.text_only:
        if args.audit is not None:
            raise ValueError("--text-only does not accept an audit file")
        if args.video_count != 0:
            raise ValueError("--text-only requires --video-count 0")
        audit: dict[str, Any] | None = None
        videos: list[dict[str, Any]] = []
    else:
        if args.audit is None:
            raise ValueError("an audit file is required unless --text-only is used")
        audit = read_json(args.audit)
        if audit.get("community_id") != COMMUNITY_ID:
            raise ValueError("audit community does not match lord-god-strength")
        videos = select_videos(audit, count=args.video_count, max_views=args.max_views)
    historical, historical_release_sha256, historical_ledger_sha256, historical_release_digest = (
        select_published_historical(
            args.repository_root.resolve(),
            args.historical_release,
            args.historical_ledger,
            count=args.telegram_count,
            text_mode=args.historical_text_mode,
        )
    )
    quote_posts, quote_ledger, quote_queue_sha256, quote_ledger_sha256, quote_queue_digest = load_quote_evidence(
        args.quote_queue,
        args.quote_ledger,
    )
    quotes = select_published_quotes(quote_posts, quote_ledger, count=args.quote_count)
    slots = build_slots(args.start_date, args.days, videos, historical, quotes)
    return {
        "schema_name": "video-manager.lord-god-content-backlog",
        "schema_version": 1,
        "project_key": PROJECT_KEY,
        "community_id": COMMUNITY_ID,
        "owner_id": OWNER_ID,
        "mode": "provider-inert",
        "content_lane": "text-only" if args.text_only else "full",
        "source_audit_sha256": audit.get("audit_sha256") if audit is not None else None,
        "source_audit_status": audit.get("status") if audit is not None else "unavailable_community_key_text_lane",
        "source_audit_summary": audit.get("summary")
        if audit is not None
        else {
            "lane": "text-only",
            "reason": "wall.get/video.get are unavailable under group authorization (VK error 27); "
            "deduplication relies on the wave journal and Telegram ledgers, and the operator "
            "must confirm the VK postponed queue before apply",
        },
        "start_date": args.start_date.isoformat(),
        "days": args.days,
        "live_revalidation_required": True,
        "video_candidate_count": len(videos),
        "telegram_candidate_count": len(historical),
        "quote_candidate_count": len(quotes),
        "telegram_historical_release_sha256": historical_release_sha256,
        "telegram_historical_ledger_sha256": historical_ledger_sha256,
        "telegram_historical_release_digest": historical_release_digest,
        "telegram_historical_evidence_policy": "published+verified+release/revision/post-bound",
        "telegram_historical_text_mode": args.historical_text_mode,
        "telegram_quote_queue_digest": quote_queue_digest,
        "telegram_quote_queue_sha256": quote_queue_sha256,
        "telegram_quote_ledger_sha256": quote_ledger_sha256,
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
            metric = f"TG #{slot.get('telegram_message_id')}"
        lines.append(f"| {slot['publish_at']} | {slot['kind']} | {candidate} | {metric} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if args.days <= 0 or args.video_count < 0 or args.telegram_count < 0 or args.quote_count < 0 or args.max_views < 0:
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
