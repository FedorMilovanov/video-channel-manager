#!/usr/bin/env python3
"""Apply a reviewed editorial patch to a Charnock rich-article JSON.

The patch is a small JSON file::

    {
      "replace": {"p-6": "New paragraph text with **bold**."},
      "insert_after": {
        "q-10": [
          {"type": "paragraph", "block_id": "p-20", "text": "New paragraph."}
        ]
      }
    }

Only top-level paragraphs and headings can be replaced; quotations are never
edited through this tool.  New blocks are inserted directly after the named
block.  The Markdown source is re-rendered from the JSON afterwards, so the
review surface cannot drift from what will be published.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from charnock_article_render_md import extract_footer, render_markdown

INLINE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|\[(.+?)\]\((.+?)\)", re.S)


def parse_inline(text: str) -> list[Any]:
    """Parse the narrow inline subset used by the series into rich spans."""
    spans: list[Any] = []
    pos = 0
    for match in INLINE.finditer(text):
        if match.start() > pos:
            spans.append(text[pos : match.start()])
        if match.group(1) is not None:
            spans.append({"type": "bold", "text": match.group(1)})
        elif match.group(2) is not None:
            spans.append({"type": "italic", "text": match.group(2)})
        else:
            spans.append({"type": "url", "text": match.group(3), "url": match.group(4)})
        pos = match.end()
    if pos < len(text):
        spans.append(text[pos:])
    if not spans:
        return [""]
    if len(spans) == 1 and isinstance(spans[0], str):
        return spans[0]
    return spans


def find_block(blocks: list[dict[str, Any]], block_id: str) -> tuple[int, dict[str, Any]]:
    for index, block in enumerate(blocks):
        if block.get("block_id") == block_id:
            return index, block
    raise SystemExit(f"block not found: {block_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--markdown", type=Path, help="Markdown source to rewrite (default: JSON sibling)")
    args = parser.parse_args(argv)

    article = json.loads(args.article.read_text(encoding="utf-8"))
    patch = json.loads(args.patch.read_text(encoding="utf-8"))
    blocks = article.get("blocks")
    if not isinstance(blocks, list):
        raise SystemExit("article has no block list")

    for block_id, text in patch.get("replace", {}).items():
        _, block = find_block(blocks, block_id)
        if block.get("type") not in {"paragraph", "heading"}:
            raise SystemExit(f"{block_id}: only paragraphs and headings may be replaced")
        block["text"] = parse_inline(text)

    for anchor_id, new_blocks in patch.get("insert_after", {}).items():
        index, _ = find_block(blocks, anchor_id)
        prepared: list[dict[str, Any]] = []
        for raw in new_blocks:
            block = dict(raw)
            if block.get("type") not in {"paragraph", "heading"}:
                raise SystemExit(f"insert after {anchor_id}: unsupported type {block.get('type')!r}")
            block["text"] = parse_inline(block["text"])
            prepared.append(block)
        blocks[index + 1 : index + 1] = prepared

    seen: set[str] = set()
    for block in blocks:
        block_id = block.get("block_id")
        if block_id in seen:
            raise SystemExit(f"duplicate block id after patch: {block_id}")
        seen.add(block_id)

    article["revision"] = args.revision
    article.setdefault("metadata", {})["updated_at"] = date.today().isoformat()
    args.article.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    markdown_path = args.markdown or args.article.with_suffix(".md")
    footer = extract_footer(markdown_path.read_text(encoding="utf-8")) if markdown_path.exists() else ""
    markdown_path.write_text(render_markdown(article, footer=footer), encoding="utf-8")
    print(
        f"applied {len(patch.get('replace', {}))} replacements and "
        f"{sum(len(v) for v in patch.get('insert_after', {}).values())} insertions; "
        f"rewrote {markdown_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
