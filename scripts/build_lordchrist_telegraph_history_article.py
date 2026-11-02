#!/usr/bin/env python3
"""Build a generic @lordchrist Telegraph history article from Markdown + evidence.

Unlike the Charnock-specific Gutenberg builder, this builder accepts exact
source anchors for each historical quotation and an explicit image library.
The output is a provider-neutral RichArticleDocument consumed by the canonical
LordChrist Telegraph publisher; it performs no network requests or writes.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from video_channel_manager.telegram_rich_models import RichArticleDocument

_INLINE = re.compile(
    r"\*\*(?P<bold>.+?)\*\*|\*(?P<italic>.+?)\*|"
    r"\[(?P<label>[^\]]+)\]\((?P<url>https?://[^)\s]+)\)",
    flags=re.S,
)
_IMAGE = re.compile(r"^!\[(?P<alt>[^\]]+)\]\((?P<uri>https?://[^)\s]+)\)$")


def rich(text: str) -> list[Any]:
    """Parse the inline Markdown used by the editorial source."""
    out: list[Any] = []
    pos = 0
    for match in _INLINE.finditer(text):
        if match.start() > pos:
            out.append(text[pos : match.start()])
        if match.group("bold") is not None:
            out.append({"type": "bold", "text": match.group("bold")})
        elif match.group("italic") is not None:
            out.append({"type": "italic", "text": match.group("italic")})
        else:
            out.append({"type": "url", "text": match.group("label"), "url": match.group("url")})
        pos = match.end()
    if pos < len(text):
        out.append(text[pos:])
    return [span for span in out if span != ""]


def parse_blocks(markdown: str, media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    media_by_uri = {str(item["uri"]): item for item in media}
    if len(media_by_uri) != len(media):
        raise ValueError("media spec contains duplicate URIs")

    blocks: list[dict[str, Any]] = []
    heading_no = quote_no = para_no = media_no = 0
    lines = markdown.splitlines()
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
            blocks.append({"type": "heading", "block_id": f"h-{heading_no}", "text": rich(line[3:].strip()), "size": 2})
            index += 1
            continue
        if line.startswith("> "):
            quote_no += 1
            quote_lines: list[str] = []
            credit: str | None = None
            while index < len(lines) and lines[index].startswith("> "):
                quoted_line = lines[index][2:].strip()
                if quoted_line.startswith("—"):
                    if credit is not None:
                        raise ValueError(f"quote q-{quote_no} contains more than one credit line")
                    credit = quoted_line
                elif quoted_line:
                    quote_lines.append(quoted_line)
                index += 1
            if not quote_lines:
                raise ValueError(f"quote q-{quote_no} is empty")
            blocks.append(
                {
                    "type": "blockquote",
                    "block_id": f"q-{quote_no}",
                    "blocks": [
                        {
                            "type": "paragraph",
                            "block_id": f"qp-{quote_no}",
                            "text": rich(" ".join(quote_lines)),
                        }
                    ],
                    "credit": credit,
                }
            )
            continue
        image = _IMAGE.fullmatch(line)
        if image:
            media_no += 1
            uri = image.group("uri")
            item = media_by_uri.get(uri)
            if item is None:
                raise ValueError(f"image URI is not declared in the media spec: {uri}")
            blocks.append(
                {
                    "type": "media",
                    "block_id": f"img-{media_no:02d}",
                    "media_id": item["media_id"],
                    "caption": {"text": image.group("alt")},
                }
            )
            index += 1
            continue

        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].startswith(("# ", "## ", "> ")):
            if _IMAGE.fullmatch(lines[index]):
                break
            paragraph.append(lines[index])
            index += 1
        para_no += 1
        blocks.append({"type": "paragraph", "block_id": f"p-{para_no}", "text": rich(" ".join(paragraph).strip())})

    if not blocks or blocks[0].get("type") != "heading" or blocks[0].get("size") != 1:
        raise ValueError("Markdown must begin with exactly one H1 title")
    if sum(1 for block in blocks if block.get("type") == "heading" and block.get("size") == 1) != 1:
        raise ValueError("Markdown must contain exactly one H1 title")
    return blocks


def _collect_markdown_links(markdown: str) -> list[tuple[str, str]]:
    seen: set[str] = set()
    links: list[tuple[str, str]] = []
    for match in re.finditer(r"(?<!!)\[(?P<label>[^\]]+)\]\((?P<url>https?://[^)\s]+)\)", markdown):
        url = match.group("url")
        if url not in seen:
            seen.add(url)
            links.append((match.group("label"), url))
    return links


def build_document(markdown: str, spec: dict[str, Any]) -> dict[str, Any]:
    media = spec.get("media", [])
    if not isinstance(media, list):
        raise ValueError("spec.media must be a list")
    blocks = parse_blocks(markdown, media)

    quote_blocks = [block for block in blocks if block.get("type") == "blockquote"]
    anchors = spec.get("quote_anchors", [])
    if not isinstance(anchors, list) or len(anchors) != len(quote_blocks):
        raise ValueError(f"found {len(quote_blocks)} quote blocks but {len(anchors)} source anchors")

    markdown_links = _collect_markdown_links(markdown)
    source_by_url: dict[str, dict[str, Any]] = {}
    for idx, (label, url) in enumerate(markdown_links, start=1):
        source_by_url[url] = {
            "source_id": f"src-link-{idx:02d}",
            "label": label[:200],
            "url": url,
            "verified_on": spec["verified_on"],
            "evidence": None,
        }

    for idx, (quote_block, anchor) in enumerate(zip(quote_blocks, anchors, strict=True), start=1):
        expected_block = f"q-{idx}"
        if anchor.get("block_id") != expected_block:
            raise ValueError(f"quote anchor {idx} must bind to {expected_block}")
        source_url = str(anchor["source_url"])
        source = source_by_url.get(source_url)
        if source is None:
            source = {
                "source_id": f"src-quote-{idx:02d}",
                "label": str(anchor["label"])[:200],
                "url": source_url,
                "verified_on": spec["verified_on"],
                "evidence": None,
            }
            source_by_url[source_url] = source
        label = str(anchor["label"])[:200]
        if label and source["label"] != label:
            source["label"] = label
        exact_anchor = str(anchor["exact_anchor"]).strip()
        language = str(anchor["source_language"]).strip()
        status = str(anchor["translation_status"]).strip()
        if not exact_anchor or not language or not status:
            raise ValueError(f"{expected_block}: anchor, source_language and translation_status are required")
        evidence_line = f"Exact {language} anchor: {exact_anchor} Translation status: {status}."
        previous = str(source.get("evidence") or "").strip()
        source["evidence"] = f"{previous} {evidence_line}".strip()[:1000]
        if not quote_block.get("credit"):
            raise ValueError(f"{expected_block}: reader-facing quote credit is required")

    for item in media:
        uri = str(item.get("uri") or "")
        if not uri.startswith("https://"):
            raise ValueError(f"media URI must be a public HTTPS URL: {uri!r}")
        source_url = str(item.get("source_url") or uri)
        if source_url not in source_by_url:
            source_by_url[source_url] = {
                "source_id": f"src-media-{len(source_by_url) + 1:02d}",
                "label": str(item.get("alt_text") or "Article image")[:200],
                "url": source_url,
                "verified_on": spec["verified_on"],
                "evidence": str(item.get("source_evidence") or "Image asset provenance recorded in the article spec.")[
                    :1000
                ],
            }

    doc = {
        "schema_name": "video-channel-manager.rich-article-document",
        "schema_version": 1,
        "document_id": spec["document_id"],
        "project_key": spec["project_key"],
        "metadata": spec["metadata"],
        "blocks": blocks,
        "media": [
            {key: value for key, value in item.items() if key in {"media_id", "kind", "uri", "alt_text"}}
            for item in media
        ],
        "sources": list(source_by_url.values()),
    }
    return RichArticleDocument.model_validate(doc).model_dump(mode="json", exclude_none=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--md", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    markdown = args.md.read_text(encoding="utf-8")
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    document = build_document(markdown, spec)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quote_count = sum(1 for block in document["blocks"] if block["type"] == "blockquote")
    media_count = sum(1 for block in document["blocks"] if block["type"] == "media")
    print(f"built {args.out} ({len(document['blocks'])} blocks, {quote_count} quotes, {media_count} inline images)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
