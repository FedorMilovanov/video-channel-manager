#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L2-MD → `blocks` документа rich-article-document.

Markdown статьи — единственный источник текста: копи-страница и документ для
провайдера собираются из одного и того же файла, поэтому расхождение между ними
невозможно по построению. Скрипт пересобирает только `blocks`, а `metadata`,
`media`, `media_slots` и `sources` статьи (провенанс цитат) сохраняет из
существующего JSON: они правятся руками, а не выводятся из разметки.

    python3 scripts/build_l2_rich_document.py статья.md статья.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ZWSP = "\u200b"
ATTRIBUTION_RE = re.compile(r"^(?:\*— .+?\*|— .+)$")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")


def plain(text: str) -> str:
    """Текст без разметки — для сверки и для plain-проекции."""
    text = BOLD_RE.sub(r"\1", text)
    text = ITALIC_RE.sub(r"\1", text)
    return text.replace(ZWSP, "").strip()


INLINE_RE = re.compile(r"\*\*(.+?)\*\*|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")


def rich_text(text: str):
    """Разметка Markdown → rich-текст документа (решение оператора 2026-10-22).

    Жирный и курсив разрешены, поэтому они не снимаются, а становятся узлами
    RichText: так форматирование доезжает до провайдера тем же, что видит
    читатель на копи-странице. Без разметки возвращается обычная строка.
    """
    text = text.replace(ZWSP, "").strip()
    nodes: list = []
    pos = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > pos:
            nodes.append(text[pos : match.start()])
        if match.group(1) is not None:
            nodes.append({"type": "bold", "text": match.group(1)})
        else:
            nodes.append({"type": "italic", "text": match.group(2)})
        pos = match.end()
    if pos < len(text):
        nodes.append(text[pos:])
    if not nodes:
        return ""
    if all(isinstance(node, str) for node in nodes):
        return "".join(nodes)
    return nodes


def parse_blocks(md: str) -> list[dict]:
    blocks: list[dict] = []
    counters = {"heading": 0, "paragraph": 0, "blockquote": 0, "quote_paragraph": 0}
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in md.replace("\r\n", "\n").split("\n"):
        if line.strip():
            current.append(line.rstrip())
        elif current:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)

    for chunk in chunks:
        index = 0
        while index < len(chunk):
            line = chunk[index]
            if line.startswith("> "):
                quote: list[str] = []
                while index < len(chunk) and chunk[index].startswith(">"):
                    quote.append(plain(chunk[index].lstrip("> ").strip()))
                    index += 1
                credit = None
                if quote and ATTRIBUTION_RE.match(quote[-1]):
                    raw_credit = quote.pop()
                    # курсивная подпись «*— Автор*» остаётся курсивом и в документе
                    if raw_credit.startswith("*") and raw_credit.endswith("*"):
                        credit = [{"type": "italic", "text": raw_credit[1:-1]}]
                    else:
                        credit = raw_credit
                counters["blockquote"] += 1
                counters["quote_paragraph"] += 1
                blocks.append(
                    {
                        "type": "blockquote",
                        "block_id": f"q-{counters['blockquote']}",
                        "blocks": [
                            {
                                "type": "paragraph",
                                "block_id": f"qp-{counters['quote_paragraph']}",
                                "text": rich_text("\n".join(quote)),
                            }
                        ],
                        **({"credit": credit} if credit else {}),
                    }
                )
                continue
            for level, size in (("# ", 1), ("## ", 2), ("### ", 3)):
                if line.startswith(level):
                    counters["heading"] += 1
                    blocks.append(
                        {
                            "type": "heading",
                            "block_id": f"h-{counters['heading']}",
                            "text": rich_text(line[len(level) :]),
                            "size": size,
                        }
                    )
                    break
            else:
                counters["paragraph"] += 1
                # маркер пункта («• ») остаётся в тексте: копи-страница тоже его печатает
                blocks.append(
                    {
                        "type": "paragraph",
                        "block_id": f"p-{counters['paragraph']}",
                        "text": rich_text(line),
                    }
                )
            index += 1
    return blocks


def build(md_path: Path, document_path: Path) -> dict:
    document = json.loads(document_path.read_text(encoding="utf-8"))
    document["blocks"] = parse_blocks(md_path.read_text(encoding="utf-8"))
    document_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("document", type=Path, help="существующий rich-article-document JSON")
    args = parser.parse_args(argv)
    document = build(args.markdown, args.document)
    print(json.dumps({"document_id": document["document_id"], "blocks": len(document["blocks"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
