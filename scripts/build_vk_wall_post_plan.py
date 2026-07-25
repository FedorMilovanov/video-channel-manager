#!/usr/bin/env python3
"""Build a self-validating one-video VK wall post plan from a fresh VK snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.platforms.vk.wall import build_vk_wall_post_plan

_SITE_URL = "https://thelegendarypoet.ru/"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Fresh VK AuditPackage JSON")
    parser.add_argument("--video", required=True, help="Exact VK owner_id_video_id")
    parser.add_argument("--message", type=Path, required=True, help="Reviewed UTF-8 plain-text wall message")
    parser.add_argument("--sources", type=Path, required=True, help="JSON array of source link objects")
    parser.add_argument("--article-url", help="Published site article URL; omit while the article is still a draft")
    parser.add_argument("--output", type=Path, default=Path("data/reports/vk-wall-post-plan.json"))
    return parser


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Cannot read VK AuditPackage {path}: {exc}") from exc


def _load_sources(path: Path) -> list[dict[str, str]]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read source links {path}: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("Source links must be a JSON array of objects")
    sources = [
        {
            "label": str(item.get("label") or "Источник"),
            "url": str(item.get("url") or "").strip(),
            "kind": str(item.get("kind") or "source"),
        }
        for item in payload
    ]
    urls = [item["url"] for item in sources]
    if any(not url for url in urls):
        raise ValueError("Source links cannot contain blank URLs")
    if len(urls) != len(set(urls)):
        raise ValueError("Source links contain duplicate URLs")
    return sources


def _validate_visible_links(
    message: str,
    *,
    sources: list[dict[str, str]],
    article_url: str | None,
) -> None:
    for source in sources:
        url = source["url"]
        occurrences = message.count(url)
        if occurrences != 1:
            raise ValueError(
                f"Reviewed wall message must contain source URL exactly once; found {occurrences}: {url}"
            )

    route_url = article_url.strip() if article_url else _SITE_URL
    route_occurrences = message.count(route_url)
    if route_occurrences != 1:
        raise ValueError(
            f"Reviewed wall message must contain the exact site/article route once; found {route_occurrences}: {route_url}"
        )
    domain_occurrences = message.count("thelegendarypoet.ru")
    if domain_occurrences != 1:
        raise ValueError(
            "Reviewed wall message must contain exactly one The Legendary Poet route; "
            f"found {domain_occurrences}"
        )


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    args = _parser().parse_args()
    try:
        message = args.message.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"Cannot read wall message {args.message}: {exc}") from exc
    sources = _load_sources(args.sources)
    _validate_visible_links(message, sources=sources, article_url=args.article_url)
    plan = build_vk_wall_post_plan(
        _load_audit(args.target),
        video_remote_id=args.video,
        message=message,
        source_links=sources,
        article_url=args.article_url,
    )
    _atomic_write(args.output, plan)
    print(
        "VK wall post plan built:\n"
        f"  video: {plan['video_remote_id']}\n"
        f"  visible sources: {len(sources)}\n"
        f"  message sha256: {plan['message_sha256']}\n"
        f"  guid: {plan['guid']}\n"
        f"  plan sha256: {plan['plan_sha256']}\n"
        f"  output: {args.output}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
