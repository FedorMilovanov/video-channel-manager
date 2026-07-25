from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_channel_manager.config import get_settings
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.youtube.comment_plan import video_id_set_sha256

_AUDIT_SCHEMA = "video-manager.youtube-comment-audit"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _suggested_profile(title: str, duration_seconds: int | None) -> str:
    lower = title.casefold()
    if "#shorts" in lower or (duration_seconds is not None and duration_seconds <= 60):
        return "short"
    if any(token in lower for token in ("english", "англий", "китай", "中文", "translation")):
        return "foreign_language_adaptation"
    if "cover" in lower or "кавер" in lower:
        return "cover_or_adaptation"
    if any(token in lower for token in ("дебаты", "apostrophes", "биография", "история", "анализ")):
        return "historical_or_essay"
    return "long_form_poetry"


def _fact_type_candidates(profile: str) -> list[str]:
    if profile == "short":
        return ["composition_history", "first_publication", "textual_structure"]
    if profile == "historical_or_essay":
        return ["documented_context", "archival_provenance", "performance_history"]
    if profile in {"cover_or_adaptation", "foreign_language_adaptation"}:
        return ["adaptation_history", "performance_history", "documented_context"]
    return [
        "composition_history",
        "first_publication",
        "manuscript_history",
        "textual_structure",
        "archival_provenance",
    ]


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# YouTube comment editorial queue",
        "",
        f"- Channel: `{payload['channel_id']}`",
        f"- Source snapshot: `{payload['source_snapshot']}`",
        f"- Queue items: **{len(payload['items'])}**",
        "",
        "This file is an editorial queue, not a write plan. Every item starts as `needs-research` and targets structured comment schema v2.",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"## {item['title']}",
                "",
                f"- Video ID: `{item['video_id']}`",
                f"- URL: {item['video_url']}",
                f"- Audit status: `{item['audit_status']}`",
                f"- Suggested profile: `{item['suggested_profile']}`",
                f"- Fact families to research: {', '.join(item['fact_type_candidates'])}",
                f"- Suggested record: `{item['suggested_content_path']}`",
                "- Relevant playlists:",
            ]
        )
        playlists = item.get("relevant_playlists")
        if isinstance(playlists, list) and playlists:
            for playlist in playlists:
                if isinstance(playlist, dict):
                    lines.append(f"  - {playlist.get('title')}: {playlist.get('url')}")
        else:
            lines.append("  - none in the snapshot")
        lines.extend(
            [
                "",
                "### Required rendering",
                "",
                "```text",
                "[contextual marker] *[work-specific factual heading]*",
                "",
                "[substantial sourced fact]",
                "",
                "_[specific lead]:_ [specific question]?",
                "",
                "📌 *The Legendary Poet:* https://thelegendarypoet.ru/",
                "🎧 *[relevant playlist]:* [URL when required]",
                "*Сообщество проекта VK:* https://vk.com/thelegendarypoet",
                "[optional primary text on one line]",
                "```",
                "",
                "### Existing description for research context",
                "",
                str(item.get("description") or ""),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a research queue for every public video lacking a channel-authored top-level comment."
    )
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--include-owned", action="store_true", help="Also queue videos that already have a channel comment"
    )
    args = parser.parse_args()

    try:
        package = AuditPackage.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
        audit = _read_json(args.audit)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load queue inputs: {exc}", file=sys.stderr)
        return 2

    channel_id = package.channel.ref.channel_id
    public_videos = [item for item in package.videos if (item.privacy_status or "").lower() == "public"]
    public_ids = [item.ref.remote_id for item in public_videos]
    if audit.get("schema_name") != _AUDIT_SCHEMA or audit.get("schema_version") != 1:
        print("ERROR: unsupported comment audit schema.", file=sys.stderr)
        return 2
    if audit.get("channel_id") != channel_id or audit.get("source_snapshot") != str(package.snapshot_id):
        print("ERROR: comment audit does not belong to this snapshot/channel.", file=sys.stderr)
        return 2
    if audit.get("inventory_video_ids_sha256") != video_id_set_sha256(public_ids):
        print("ERROR: comment audit inventory hash does not match the public-video snapshot.", file=sys.stderr)
        return 2

    audit_videos = audit.get("videos")
    if not isinstance(audit_videos, list):
        print("ERROR: comment audit videos must be a list.", file=sys.stderr)
        return 2
    audit_by_id = {
        str(item.get("video_id") or ""): item
        for item in audit_videos
        if isinstance(item, dict) and item.get("video_id")
    }
    if set(audit_by_id) != set(public_ids):
        print("ERROR: comment audit does not cover exactly the public-video snapshot.", file=sys.stderr)
        return 2

    collection_by_key = {item.ref.stable_key: item for item in package.collections}
    memberships_by_video: dict[str, list[dict[str, str]]] = defaultdict(list)
    for membership in package.memberships:
        collection = collection_by_key.get(membership.collection_ref.stable_key)
        if collection is None:
            continue
        video_id = membership.video_ref.remote_id
        memberships_by_video[video_id].append(
            {
                "playlist_id": collection.ref.remote_id,
                "title": collection.title,
                "url": f"https://www.youtube.com/playlist?list={collection.ref.remote_id}",
            }
        )

    items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for video in public_videos:
        video_id = video.ref.remote_id
        live = audit_by_id[video_id]
        status = str(live.get("status") or "")
        queueable = status in {"missing", "foreign_only"} or (args.include_owned and status == "owned_present")
        if not queueable:
            skipped.append({"video_id": video_id, "title": video.title, "reason": status})
            continue
        profile = _suggested_profile(video.title, video.duration_seconds)
        items.append(
            {
                "editorial_status": "needs-research",
                "target_schema_version": 2,
                "video_id": video_id,
                "title": video.title,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "audit_status": status,
                "suggested_profile": profile,
                "profile_requires_human_review": True,
                "fact_type_candidates": _fact_type_candidates(profile),
                "duration_seconds": video.duration_seconds,
                "published_at": video.published_at.isoformat() if video.published_at else None,
                "description": video.description,
                "relevant_playlists": sorted(memberships_by_video.get(video_id, []), key=lambda item: item["title"]),
                "stable_project_links": {
                    "site": "https://thelegendarypoet.ru/",
                    "vk": "https://vk.com/thelegendarypoet",
                    "telegram": "https://t.me/thelegendarypoet",
                    "rutube": "https://rutube.ru/channel/74579453/",
                },
                "required_link_labels": {
                    "site": "📌 *The Legendary Poet:*",
                    "vk": "*Сообщество проекта VK:*",
                    "playlist_prefix": "🎧 *",
                    "primary_text_prefix": "📚 _",
                },
                "suggested_content_path": f"content/youtube-comments/{video_id}.json",
                "requirements": [
                    "research one concrete composition/publication/manuscript/structure/archive/adaptation fact",
                    "map the exact factual paragraph to exact fact.source_ids",
                    "use a unique variation_key and work-specific heading",
                    "write a question tied to a precise textual or documented detail",
                    "keep each link label and URL on the same line",
                    "use no coloured circle markers and no generic hype",
                    "use only relevant playlist links",
                    "human approval required before plan inclusion",
                ],
            }
        )

    payload: dict[str, Any] = {
        "schema_name": "video-manager.youtube-comment-editorial-queue",
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "channel_id": channel_id,
        "source_snapshot": str(package.snapshot_id),
        "source_comment_audit": str(args.audit),
        "inventory_video_count": len(public_videos),
        "inventory_video_ids_sha256": video_id_set_sha256(public_ids),
        "counts": dict(sorted(Counter(str(item["audit_status"]) for item in items).items())),
        "items": items,
        "skipped": skipped,
    }

    settings = get_settings()
    if args.output is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        args.output = settings.data_dir / "reports" / f"youtube-comment-editorial-queue-{channel_id}-{timestamp}.json"
    _write_json(args.output, payload)
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(_markdown(payload), encoding="utf-8")
    print("YouTube comment editorial queue built:")
    print(f"  queue items: {len(items)}")
    print(f"  skipped: {len(skipped)}")
    print(f"JSON → {args.output}")
    print(f"Markdown → {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
