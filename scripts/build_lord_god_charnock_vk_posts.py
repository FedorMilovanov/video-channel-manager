#!/usr/bin/env python3
"""Split the Lord God Charnock longreads into VK-sized postponed wall posts.

The Telegraph cycle ``lordchrist-telegraph-charnock-*`` holds thirteen
articles of roughly 20-58k characters. A VK wall post is limited to 15,000
characters, so each article is converted to canonical VK plain text and
split at section boundaries into sequential parts. Every part carries
the article cover path/digest as evidence (the community key cannot
upload wall photos, so prepare emits text-only operations);
the output is provider-inert and deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk.text_writer import canonical_vk_text

SCHEMA_NAME = "video-manager.lord-god-charnock-vk-posts"
DEFAULT_MAX_CHARS = 13_800
LINKS_FOOTER = "\n\n🌐 https://gospod-bog.ru/\n📨 https://t.me/lordchrist\n\n#ГосподьБогСилаМоя #СтивенЧарнок"
CONTINUES_FOOTER = "\n\nПродолжение следует."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--article-queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    return parser.parse_args()


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def strip_emphasis(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(?=\S)(.+?)(?<=\S)\*(?!\w)", r"\1", text)
    return text


def md_to_blocks(markdown: str) -> tuple[str, list[tuple[str, bool]]]:
    """Convert markdown into (title, ordered (block, is_heading) blocks)."""

    title = ""
    blocks: list[tuple[str, bool]] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            block = canonical_vk_text(strip_emphasis(" ".join(current)))
            if block:
                blocks.append((block, False))
            current.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            flush()
            if not title:
                title = canonical_vk_text(strip_emphasis(line[2:].strip()))
            continue
        if line.startswith("## "):
            flush()
            heading = canonical_vk_text(strip_emphasis(line[3:].strip()))
            if heading:
                blocks.append((heading, True))
            continue
        if not line:
            flush()
            continue
        if line.startswith(">"):
            line = line.lstrip(">").strip()
        current.append(line)
    flush()
    if not title:
        raise ValueError("article markdown has no level-1 title")
    return title, blocks


def split_oversize(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]
    pieces: list[str] = []
    rest = block
    while len(rest) > limit:
        cut = max(rest.rfind(". ", 0, limit), rest.rfind("! ", 0, limit), rest.rfind("? ", 0, limit))
        if cut < limit // 3:
            cut = rest.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        pieces.append(rest[: cut + 1].strip())
        rest = rest[cut + 1 :].strip()
    if rest:
        pieces.append(rest)
    return pieces


def chunk_blocks(blocks: list[tuple[str, bool]], limit: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[tuple[str, bool]] = []
    size = 0

    def flush() -> None:
        nonlocal current, size
        # A section heading must open a part, never close one: move a
        # trailing heading into the next chunk.
        trailing: list[tuple[str, bool]] = []
        while current and current[-1][1]:
            trailing.insert(0, current.pop())
        if current:
            chunks.append([text for text, _ in current])
        current, size = trailing, sum(len(text) + 2 for text, _ in trailing)

    for block, is_heading in blocks:
        for piece in split_oversize(block, limit):
            piece_size = len(piece) + (2 if current else 0)
            if current and size + piece_size > limit:
                flush()
                piece_size = len(piece) + (2 if current else 0)
            current.append((piece, is_heading))
            size += piece_size
    if current:
        chunks.append([text for text, _ in current])
    return chunks


def build_posts(root: Path, queue_path: Path, max_chars: int) -> dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    items = [item for item in queue.get("items", []) if item.get("status") == "ready"]
    if not items:
        raise ValueError("article queue has no ready items")
    posts: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    for item in items:
        publication_id = str(item["publication_id"])
        article_json = root / str(item["article"]["path"])
        article_md = article_json.with_suffix(".md")
        markdown = article_md.read_text(encoding="utf-8")
        title, blocks = md_to_blocks(markdown)
        header_reserve = 220
        footer_reserve = max(len(LINKS_FOOTER), len(CONTINUES_FOOTER)) + 8
        chunks = chunk_blocks(blocks, max_chars - header_reserve - footer_reserve)
        total = len(chunks)
        # The queue is the source of truth for cover paths; publication ids
        # are not guaranteed to end with the numeric cycle suffix (e.g. the
        # Sunday historical special "...-history-01").
        cover_rel = str((item.get("cover") or {}).get("path") or "")
        if not cover_rel:
            ordinal_text = publication_id.rsplit("-", 1)[-1]
            cover_rel = (
                f"content/telegram/lordchrist/telegraph-v1/media/lordchrist-telegraph-charnock-{ordinal_text}-cover.jpg"
            )
        cover_path = root / cover_rel
        if not cover_path.is_file():
            raise ValueError(f"article cover is missing: {cover_rel}")
        cover_sha = sha256_bytes(cover_path.read_bytes())
        articles.append(
            {
                "publication_id": publication_id,
                "title": title,
                "source_markdown": article_md.relative_to(root).as_posix(),
                "source_markdown_sha256": sha256_bytes(article_md.read_bytes()),
                "cover_path": cover_rel,
                "cover_sha256": cover_sha,
                "parts": total,
            }
        )
        for index, chunk in enumerate(chunks, start=1):
            body = "\n\n".join(chunk)
            header = f"📖 Стивен Чарнок. «О бытии Бога»\n{title}\nЧасть {index} из {total}"
            footer = LINKS_FOOTER if index == total else CONTINUES_FOOTER
            message = canonical_vk_text(f"{header}\n\n{body}{footer}")
            if len(message) > 15_000:
                raise ValueError(f"{publication_id} part {index} exceeds the VK wall limit: {len(message)}")
            posts.append(
                {
                    "source_id": f"{publication_id}-vk-part-{index}",
                    "article_publication_id": publication_id,
                    "article_title": title,
                    "part": index,
                    "parts_total": total,
                    "message": message,
                    "message_sha256": sha256_text(message),
                    "cover_path": cover_rel,
                    "cover_sha256": cover_sha,
                }
            )
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": 1,
        "project_key": "lord-god-strength",
        "series": "stephen-charnock-on-the-existence-of-god",
        "articles": articles,
        "posts": posts,
    }


def main() -> int:
    args = parse_args()
    root = args.repository_root.resolve()
    payload = build_posts(
        root,
        (root / args.article_queue).resolve() if not args.article_queue.is_absolute() else args.article_queue,
        args.max_chars,
    )
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Built Charnock VK posts: articles={len(payload['articles'])} posts={len(payload['posts'])} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
