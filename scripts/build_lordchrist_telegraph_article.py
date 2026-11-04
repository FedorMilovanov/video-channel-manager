#!/usr/bin/env python3
"""Build a @lordchrist L3 Telegraph rich-article JSON from its Markdown source.

The Markdown file is the editorial source of truth; this builder produces the
``video-channel-manager.rich-article-document`` JSON consumed by
``video_channel_manager.lordchrist_telegraph_publisher``. Quote provenance is
computed, not hand-written: every Charnock quote is located as a contiguous
passage in the normalized Gutenberg #53527 text and anchored in ``sources``
(see ``TELEGRAPH_ARTICLE_STANDARD.md``).

Inputs:

* ``--md`` — the article Markdown (H1 title, ``##`` sections, ``>`` quotes with
  a ``> — credit`` line, paragraphs; ``**bold**`` / ``*italic*`` inline).
* ``--spec`` — a ``*.quotes.json`` spec next to the article with ``metadata``,
  the epigraph/scripture source entries and the ordered quote list
  ``[{"discourse": "беседа I", "start": "...", "end": "..."}]`` where
  start/end are verbatim English phrases in the source text.
* ``--source`` — the raw Gutenberg #53527 plain text.
* ``--out`` — the article JSON to write.
* ``--blocks-out`` — a file receiving the ``--block NAME:START:LEN`` arguments
  for ``scripts/lordchrist_article_sources_check.py``.

The first Markdown quote block is the epigraph (owned by the epigraph source
entry); every following quote block maps to one spec quote, in order.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

EPIGRAPH_BLOCK_GAP = 80  # slack after the quote span inside its checker block


def normalize_source(text: str) -> str:
    """Mirror the normalization used by the sources checker."""
    text = re.sub(r"\{[a-zA-Z]\d+\}", "", text)
    text = re.sub(r"\[\d+\]", "", text)
    text = text.replace("_", "")
    return re.sub(r"\s+", " ", text)


def rich(text: str) -> list[Any]:
    """Split inline ``**bold**`` / ``*italic*`` markup into rich spans."""
    out: list[Any] = []
    pos = 0
    for match in re.finditer(r"\*\*(.+?)\*\*|\*(.+?)\*", text, flags=re.S):
        if match.start() > pos:
            out.append(text[pos : match.start()])
        if match.group(1) is not None:
            out.append({"type": "bold", "text": match.group(1)})
        else:
            out.append({"type": "italic", "text": match.group(2)})
        pos = match.end()
    if pos < len(text):
        out.append(text[pos:])
    return [span for span in out if span != ""]


def parse_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    heading_no = quote_no = para_no = 0
    lines = markdown.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("# "):
            heading_no += 1
            blocks.append({"type": "heading", "block_id": f"h-{heading_no}", "text": rich(line[2:].strip()), "size": 1})
            index += 1
            continue
        if line.startswith("## "):
            heading_no += 1
            blocks.append({"type": "heading", "block_id": f"h-{heading_no}", "text": line[3:].strip(), "size": 2})
            index += 1
            continue
        if line.startswith("> "):
            body: list[str] = []
            credit: str | None = None
            while index < len(lines) and lines[index].startswith("> "):
                if lines[index].startswith("> —"):
                    credit = lines[index][2:].strip()
                else:
                    body.append(lines[index][2:])
                index += 1
            quote_no += 1
            blocks.append(
                {
                    "type": "blockquote",
                    "block_id": f"q-{quote_no}",
                    "blocks": [
                        {"type": "paragraph", "block_id": f"qp-{quote_no}", "text": rich(" ".join(body).strip())}
                    ],
                    "credit": credit,
                }
            )
            continue
        body = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].startswith(("#", ">")):
            body.append(lines[index])
            index += 1
        para_no += 1
        blocks.append({"type": "paragraph", "block_id": f"p-{para_no}", "text": rich(" ".join(body).strip())})
    return blocks


def locate_spans(source_text: str, quotes: list[dict[str, str]]) -> list[tuple[str, int, str]]:
    spans: list[tuple[str, int, str]] = []
    for quote in quotes:
        start = source_text.find(quote["start"])
        if start < 0:
            raise ValueError(f"quote start not found in source: {quote['start'][:60]!r}")
        end_at = source_text.find(quote["end"], start)
        if end_at < 0:
            raise ValueError(f"quote end not found in source: {quote['end'][:60]!r}")
        span = source_text[start : end_at + len(quote["end"])]
        if len(span) > 990:
            raise ValueError(f"quote span exceeds the 1000-char evidence limit: {len(span)} chars")
        spans.append((quote["discourse"], start, span))
    return spans


def build_document(markdown: str, spec: dict[str, Any], source_text: str) -> tuple[dict[str, Any], str]:
    quotes: list[dict[str, str]] = spec["quotes"]
    spans = locate_spans(source_text, quotes)
    blocks = parse_blocks(markdown)
    quote_blocks = [block for block in blocks if block["type"] == "blockquote"]
    if len(quote_blocks) != len(quotes) + 1:
        raise ValueError(f"Markdown has {len(quote_blocks)} quote blocks, expected epigraph + {len(quotes)} quotes")
    sources: list[dict[str, Any]] = [spec["epigraph_source"]]
    block_specs: list[str] = []
    for number, ((discourse, offset, span), _block) in enumerate(zip(spans, quote_blocks[1:], strict=True), start=2):
        name = f"H{number:02d}"
        block_specs.append(f"--block {name}:{offset}:{len(span) + EPIGRAPH_BLOCK_GAP}")
        sources.append(
            {
                "source_id": f"src-{number:02d}-charnock",
                "label": f"Стивен Чарнок, «О бытии Бога» ({discourse}), цитата {number}",
                "url": "https://www.gutenberg.org/files/53527/53527-h/53527-h.htm",
                "verified_on": spec["verified_on"],
                "evidence": (
                    f"EN: {span}  [смещение 0 в блоке {name} (нормализованный текст источника, "
                    f"позиция {offset}; {len(span)} зн.), eBook #53527 / издание 1853 г.; перевод канала]"
                ),
            }
        )
    sources.append(spec["scripture_source"])
    document = {
        "schema_name": "video-channel-manager.rich-article-document",
        "schema_version": 1,
        "document_id": spec["document_id"],
        "project_key": spec["project_key"],
        "metadata": spec["metadata"],
        "blocks": blocks,
        "sources": sources,
    }
    return document, " ".join(block_specs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--md", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="Gutenberg #53527 plain text")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--blocks-out", type=Path, required=True)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    markdown = args.md.read_text(encoding="utf-8")
    source_text = normalize_source(args.source.read_text(encoding="utf-8"))
    document, block_specs = build_document(markdown, spec, source_text)
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.blocks_out.write_text(block_specs, encoding="utf-8")
    print(f"built {args.out} ({len(document['blocks'])} blocks, {len(document['sources'])} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
