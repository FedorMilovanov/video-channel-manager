#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собрать нормализованный корпус первоисточников и сверить с ним якоря цитат.

Корпус — это склейка нормализованных оцифровок в порядке блоков; именно в него
`scripts/lordchrist_article_sources_check.py` смотрит по `--source` и `--block`.
Раньше корпус собирался одноразовым скриптом во временном каталоге и терялся
вместе с песочницей; теперь он собирается воспроизводимо из одного коммита.

    python3 scripts/build_lordchrist_source_corpus.py \
        --vault /tmp/ecl/vault \
        --commit d16898fa04838f1060219e25865b4df8709b2655 \
        --block EDW-REM="07 Revival (1700–1800)/…/Freedom of the Will - 46 Sec 15 Remarks on Morality Essays.md" \
        ... \
        --out /tmp/art/corpus.txt \
        --article content/…/lordchrist-rich-rabstvo-svobody.json

`--article` пересчитывает смещения якорей в `evidence` по фактическому корпусу:
смещение — это позиция самой длинной части якоря внутри своего блока, ровно по
той же арифметике, по которой её читает проверка.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path

FOLD = {"‑": "-", "’": "'", "‘": "'", "“": '"', "”": '"'}
BLOCK_RE = re.compile(r"в блоке\s+([^\s(]+)")
OFFSET_RE = re.compile(r"смещение (\d+)")
POSITION_RE = re.compile(r"позиция (\d+)")


def load_checker() -> tuple[object, object]:
    """Нормализация берётся из самой проверки: два разных правила разъедутся."""
    path = Path(__file__).with_name("lordchrist_article_sources_check.py")
    spec = importlib.util.spec_from_file_location("lordchrist_sources_check", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"не читается проверка: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalize, module.fold


def find_offset(text: str, needle: str) -> int:
    """Позиция якоря в координатах проверки.

    Оцифровка ставит markdown-акценты внутри фразы («a being *able*»), а якорь
    их не содержит, поэтому ищем по тексту без акцентов и возвращаем индекс
    в исходной строке: смещение обязано считаться по той же строке, которую
    режет проверка.
    """
    stripped: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(text):
        if char in "*`":
            continue
        stripped.append(char)
        index_map.append(index)
    position = "".join(stripped).find(needle)
    return index_map[position] if position >= 0 else -1


def read_file(vault: Path, commit: str | None, path: str) -> str:
    if commit is None:
        return (vault / path).read_text(encoding="utf-8")
    result = subprocess.run(
        ["git", "-C", str(vault), "show", f"{commit}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"не читается {path!r} в {commit}: {result.stderr.strip()}")
    return result.stdout


def anchor_text(evidence: str) -> str:
    en = re.split(r"\s*\[", evidence[3:])[0].strip() if evidence.startswith("EN:") else ""
    if "…" in en:
        en = max((part.strip() for part in en.split("…")), key=len)
    return en


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--commit", default=None)
    parser.add_argument("--block", action="append", default=[], metavar="ИМЯ=ПУТЬ")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--article", type=Path, default=None)
    args = parser.parse_args()

    normalize, fold = load_checker()
    blocks: list[tuple[str, str]] = []
    for spec in args.block:
        name, _, path = spec.partition("=")
        text = fold(normalize(read_file(args.vault, args.commit, path))).strip()
        blocks.append((name, text))

    corpus = " ".join(text for _, text in blocks)
    if normalize(corpus) != corpus:
        raise SystemExit("корпус не нормализован: проверка срежет символы и сместит якоря")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(corpus, encoding="utf-8")

    starts: dict[str, tuple[int, int]] = {}
    position = 0
    for name, text in blocks:
        starts[name] = (position, len(text))
        position += len(text) + 1

    print(f"корпус: {len(corpus)} знаков → {args.out}")
    for name, (start, length) in starts.items():
        print(f"--block {name}:{start}:{length}")

    if args.article is not None:
        document = json.loads(args.article.read_text(encoding="utf-8"))
        moved = 0
        for entry in document.get("sources", []):
            evidence = entry.get("evidence") or ""
            if not evidence.startswith("EN:"):
                continue
            block_match = BLOCK_RE.search(evidence)
            if not block_match or block_match.group(1) not in starts:
                continue
            needle = fold(anchor_text(evidence))
            text = dict(blocks)[block_match.group(1)]
            offset = find_offset(text, needle)
            if offset < 0:
                print(f"{entry['source_id']}: якорь не найден в блоке — смещение не менялось")
                continue
            new_evidence = OFFSET_RE.sub(f"смещение {offset}", evidence, count=1)
            new_evidence = POSITION_RE.sub(f"позиция {offset}", new_evidence, count=1)
            if new_evidence != evidence:
                entry["evidence"] = new_evidence
                moved += 1
        args.article.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"смещения пересчитаны: {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
