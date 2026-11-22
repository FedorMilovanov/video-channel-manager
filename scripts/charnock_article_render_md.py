#!/usr/bin/env python3
"""Render a Charnock telegraph rich-article JSON back to its Markdown source.

The Charnock series keeps two parallel editorial artefacts: the human-readable
``*.md`` and the provider JSON consumed by the Telegraph publisher.  The
Markdown is the review surface; the JSON is what is sent.  This renderer is the
consistency bridge between them: it reproduces the exact house Markdown from a
JSON document (including bold/italic spans, blockquote credits and the closing
copyright note), and ``--check`` fails when the pair has drifted.

It is deliberately narrow: it supports only the block types used by the
Charnock articles (heading, paragraph, blockquote).  A new block type must be
taught here rather than silently dropped.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any


def iter_text(value: Any) -> str:
    """Plain text of a rich span tree, losing only formatting."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(iter_text(item) for item in value)
    if isinstance(value, dict):
        if "text" in value:
            return iter_text(value["text"])
        if "children" in value:
            return iter_text(value["children"])
    return ""


def rich_md(value: Any) -> str:
    """Render a rich span tree as Markdown inline markup."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(rich_md(item) for item in value)
    if isinstance(value, dict):
        kind = value.get("type")
        if kind == "bold":
            return f"**{rich_md(value.get('text', ''))}**"
        if kind == "italic":
            return f"*{rich_md(value.get('text', ''))}*"
        if kind == "url":
            return f"[{rich_md(value.get('text', ''))}]({value.get('url', '')})"
        if "text" in value:
            return rich_md(value["text"])
        if "children" in value:
            return rich_md(value["children"])
    return ""


def extract_footer(markdown: str) -> str:
    """Return the final ``©`` paragraph of an existing Markdown source, if any."""
    paragraphs = markdown.rstrip().split("\n\n")
    for paragraph in reversed(paragraphs):
        if paragraph.lstrip().startswith("©"):
            return paragraph.strip()
    return ""


def render_markdown(article: dict[str, Any], *, footer: str = "") -> str:
    blocks = article.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("article has no block list")
    out: list[str] = []
    for block in blocks:
        kind = block.get("type")
        if kind == "heading":
            if block.get("size") == 1:
                title = rich_md(block.get("text", "")).strip()
                if not (title.startswith("**") and title.endswith("**")):
                    title = f"**{title}**"
                out.append("# " + title)
            else:
                out.append("## " + rich_md(block.get("text", "")))
        elif kind == "paragraph":
            out.append(rich_md(block.get("text", "")))
        elif kind == "blockquote":
            inner = block.get("blocks")
            if not isinstance(inner, list) or not inner:
                raise ValueError(f"{block.get('block_id')}: empty blockquote")
            lines: list[str] = []
            for paragraph in inner:
                lines.append("> " + rich_md(paragraph.get("text", "")))
            credit = block.get("credit")
            if credit:
                credit = str(credit)
                if not credit.startswith("—"):
                    credit = "— " + credit
                lines.append("> " + credit)
            out.append("\n".join(lines))
        else:
            raise ValueError(f"{block.get('block_id')}: unsupported block type {kind!r}")
        out.append("")
    text = "\n".join(out).rstrip() + "\n"
    last_text = iter_text(blocks[-1].get("text")) if blocks else ""
    if footer and not last_text.lstrip().startswith("©"):
        text += "\n" + footer.rstrip() + "\n"
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article", required=True, type=Path, help="rich-article JSON")
    parser.add_argument("--markdown", type=Path, help="existing Markdown source to compare against")
    parser.add_argument("--out", type=Path, help="write rendered Markdown here instead of stdout")
    parser.add_argument("--check", action="store_true", help="exit 1 if the Markdown has drifted")
    args = parser.parse_args(argv)

    article = json.loads(args.article.read_text(encoding="utf-8"))
    footer = ""
    existing = ""
    if args.markdown is not None:
        existing = args.markdown.read_text(encoding="utf-8")
        # Source credit must be authored in JSON, not copied from reviewed Markdown.
    rendered = render_markdown(article)

    if args.check:
        if rendered.rstrip("\n") != existing.rstrip("\n"):
            diff = difflib.unified_diff(
                existing.rstrip("\n").splitlines(),
                rendered.rstrip("\n").splitlines(),
                fromfile="markdown",
                tofile="rendered",
                lineterm="",
            )
            sys.stderr.write("\n".join(diff) + "\n")
            return 1
        return 0

    if args.out is not None:
        args.out.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
