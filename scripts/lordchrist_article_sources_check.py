#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка списка `sources` rich-документа против цитат статьи.

Проверяет провенанс цитат (правило двух прогонов, §11
`content/telegram/lordchrist/RICH_EDITOR_ARTICLE_STANDARD.md`):

  * каждый блок цитаты статьи (эпиграф = блок 1) имеет ровно один якорь
    `src-NN-charnock`, и номер якоря равен номеру блока;
  * подпись якоря совпадает с его номером («цитата NN»);
  * `source_id` уникальны;
  * сводка стихов одна и стоит последней в списке;
  * если передан текст источника (`--source`, оцифровка Project Gutenberg
    #53527), EN-текст каждого якоря дословно лежит в блоке источника по
    указанному смещению.

    python3 scripts/lordchrist_article_sources_check.py статья.md статья.json
    python3 scripts/lordchrist_article_sources_check.py статья.md статья.json \
        --source 53527-0.txt --block B1:73582:23690 --block B2:97144:16083

Конвенция блоков: текст источника нормализуется (метки `{a1}`, `[12]`,
подчёркивания убраны, пробелы схлопнуты), блок — срез нормализованного
текста: `START` — позиция среза, `LENGTH` — его длина; смещение якоря
отсчитывается от начала блока.

Код возврата: 0 — расхождений нет, 1 — есть расхождения.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CHARNOCK_RE = re.compile(r"^src-(\d+)-charnock$")
LABEL_RE = re.compile(r"цитата (\d+)")
OFFSET_RE = re.compile(r"\[смещение (\d+) в блоке")
FOLD = {"‑": "-", "’": "'", "‘": "'", "“": '"', "”": '"'}


def normalize(text: str) -> str:
    """Нормализация оцифровки Gutenberg: без меток, без подчёркиваний."""
    text = re.sub(r"\{[a-zA-Z]\d+\}", "", text)
    text = re.sub(r"\[\d+\]", "", text)
    text = text.replace("_", "")
    return re.sub(r"\s+", " ", text)


def fold(text: str) -> str:
    """Свёртка типографики: дефис U+2011 и типографские кавычки."""
    for src, dst in FOLD.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text)


def quote_blocks(markdown: str) -> list[tuple[str, str]]:
    """Блоки цитат статьи: (текст, подпись)."""
    lines = markdown.split("\n")
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("> ") and not lines[i].startswith("> —"):
            buf = [lines[i][2:]]
            j = i + 1
            while j < len(lines) and lines[j].startswith("> ") and not lines[j].startswith("> —"):
                buf.append(lines[j][2:])
                j += 1
            attr = lines[j][2:].strip() if j < len(lines) and lines[j].startswith("> —") else ""
            out.append((" ".join(buf).strip(), attr))
            i = j + 1
        else:
            i += 1
    return out


def parse_blocks(specs: list[str]) -> dict[str, tuple[int, int]]:
    """`--block B1:start:length` → блок нормализованного источника."""
    out: dict[str, tuple[int, int]] = {}
    for spec in specs:
        name, start, length = spec.split(":")
        out[name] = (int(start), int(length))
    return out


def check(markdown: Path, document: Path, source: Path | None, specs: list[str]) -> list[str]:
    errors: list[str] = []
    md = markdown.read_text(encoding="utf-8")
    doc = json.loads(document.read_text(encoding="utf-8"))
    blocks = quote_blocks(md)
    sources = doc.get("sources", [])

    ids = [s.get("source_id", "") for s in sources]
    for source_id in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"дубль source_id: {source_id}")

    summary = [s for s in sources if not CHARNOCK_RE.match(s.get("source_id", ""))]
    if len(summary) != 2:
        errors.append(f"ожидались эпиграф и сводка стихов, получено записей: {len(summary)}")
    elif sources[-1].get("source_id") != "src-scripture-synodal":
        errors.append("сводка стихов должна быть последней в списке")

    anchors: dict[int, tuple[str, int]] = {}
    for entry in sources:
        source_id = entry.get("source_id", "")
        match = CHARNOCK_RE.match(source_id)
        if not match:
            continue
        number = int(match.group(1))
        evidence = entry.get("evidence", "")
        offset_match = OFFSET_RE.search(evidence)
        if not offset_match:
            errors.append(f"{source_id}: в evidence нет смещения в блоке источника")
            continue
        en = re.split(r"\s*\[", evidence[3:])[0].strip() if evidence.startswith("EN:") else ""
        if not en:
            errors.append(f"{source_id}: в evidence нет EN-текста якоря")
            continue
        label_match = LABEL_RE.search(entry.get("label", ""))
        if not label_match:
            errors.append(f"{source_id}: в подписи нет номера цитаты")
        elif int(label_match.group(1)) != number:
            errors.append(f"{source_id}: подпись «цитата {label_match.group(1)}» ≠ номер якоря {number}")
        if number in anchors:
            errors.append(f"{source_id}: номер якоря {number} уже использован")
        anchors[number] = (en, int(offset_match.group(1)))

    for number in range(2, len(blocks) + 1):
        if number not in anchors:
            errors.append(f"блок цитаты {number}: нет якоря в sources")
    for number in sorted(anchors):
        if number > len(blocks):
            errors.append(f"якорь цитаты {number}: такого блока цитат в статье нет")

    if source is not None:
        raw = normalize(source.read_text(encoding="utf-8"))
        ranges = parse_blocks(specs)
        for number, (en, offset) in sorted(anchors.items()):
            # смещение якоря отсчитывается от начала блока источника
            found = False
            for _name, (start, length) in ranges.items():
                text = fold(raw[start : start + length])
                if text[offset:].startswith(fold(en)[:40]):
                    found = True
                    break
            if not found:
                errors.append(f"якорь цитаты {number}: EN-текст не найден в блоках источника по смещению {offset}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка провенанса цитат (sources ↔ статья).")
    parser.add_argument("markdown", type=Path)
    parser.add_argument("document", type=Path)
    parser.add_argument("--source", type=Path, default=None, help="оцифровка источника (53527-0.txt)")
    parser.add_argument(
        "--block",
        action="append",
        default=[],
        metavar="ИМЯ:НАЧАЛО:ДЛИНА",
        help="блок нормализованного источника, например B1:73582:23690",
    )
    args = parser.parse_args()

    errors = check(args.markdown, args.document, args.source, args.block)
    if errors:
        print(f"Расхождения в {args.document.name}:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"{args.document.name}: провенанс цитат в порядке — якорь на каждую цитату, source_id уникальны.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
