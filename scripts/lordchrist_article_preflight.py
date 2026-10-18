#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preflight длинной статьи @lordchrist для редактора «Статья» (lane L2).

Проверяет Markdown-источник (L2-MD). Воздух вокруг заголовков живёт
в HTML-артефакте и проверяется отдельно: --html файл.html.

Проверяет ровно те правила, которые записаны в
`content/telegram/lordchrist/RICH_EDITOR_ARTICLE_STANDARD.md`.

    python3 lordchrist_article_preflight.py статья.md
    python3 lordchrist_article_preflight.py статья.md --json

Код возврата: 0 — ошибок нет (предупреждения допустимы), 1 — есть ошибки.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MAX_CHARS = 32_768
SOFT_CHARS = 30_000
MAX_BLOCKS = 500
MAX_H1 = 120
MAX_H2 = 80
MAX_CONNECTOR = 120
MAX_QUOTE = 600
MAX_ITEM = 400
HASHTAGS_MIN, HASHTAGS_MAX = 4, 6
# Эмодзи-маркер раздела не ставится на коротких рубриках короче этого порога
# (RICH_EDITOR_ARTICLE_STANDARD, §3).
MARKER_MIN_SECTION_CHARS = 600

ZWSP = "\u200b"
WJ = "\u2060"

BANNED = (
    "certainty =",
    "source_ids",
    "fact-check anchors",
    "нейросеть",
    "как ии",
    "как искусственный интеллект",
)

EMOJI_RE = re.compile(
    "[\U0001f300-\U0001faff\U00002300-\U000023ff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff\U00002b00-\U00002bff]"
)
HASHTAG_RE = re.compile(r"#[0-9A-Za-zА-Яа-яЁё_]+")
ATTRIBUTION_RE = re.compile(r"^\*— .+\*$")
ITEM_RE = re.compile(r"^(• |\d+\. )")
MD_LIST_RE = re.compile(r"^[-*+] ")
HEADING_RE = re.compile(r"^#{1,6}\s")
NUMBERED_H2_RE = re.compile(r"^\d+[.)]")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def is_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def sentence_count(text: str) -> int:
    return max(1, len(re.findall(r"[.!?…](?:\s|$)", text)))


def blocks_of(lines: list[str]) -> list[tuple[int, int]]:
    """Возвращает (start, end) — границы абзацев по пустым строкам."""
    spans, start = [], None
    for i, line in enumerate(lines):
        if line.strip():
            if start is None:
                start = i
        else:
            if start is not None:
                spans.append((start, i))
                start = None
    if start is not None:
        spans.append((start, len(lines)))
    return spans


def check(path: Path, allow_hashtags: bool = False) -> Report:
    rep = Report()
    raw = path.read_text(encoding="utf-8")
    text = raw.replace("\r\n", "\n")
    lines = text.split("\n")
    stripped = [ln.rstrip() for ln in lines]

    # ---------- 1. транспорт и длина ----------
    if ZWSP in text:
        rep.error(f"найден U+200B (zero-width space): {text.count(ZWSP)} шт. В L2 запрещён")
    if WJ in text:
        rep.error(f"найден U+2060 (word joiner): {text.count(WJ)} шт. В L2 запрещён, это транспорт L1")
    chars = len(text)
    rep.stats["chars"] = chars
    if chars > MAX_CHARS:
        rep.error(f"длина {chars} > {MAX_CHARS} символов")
    elif chars > SOFT_CHARS:
        rep.warn(f"длина {chars}: близко к лимиту, оставьте запас (мягкий потолок {SOFT_CHARS})")
    if "\t" in text:
        rep.error("в тексте есть табуляция")
    for i, ln in enumerate(lines, 1):
        if ln != ln.rstrip():
            rep.error(f"строка {i}: висячие пробелы в конце")
            break

    spans = blocks_of(stripped)
    rep.stats["blocks_estimate"] = len(spans)
    if len(spans) > MAX_BLOCKS:
        rep.error(f"блоков ≈{len(spans)} > {MAX_BLOCKS}")

    # ---------- 2. H1 ----------
    heads = [(s, e) for s, e in spans if re.match(r"^#\s", stripped[s])]
    h2s = [(s, e) for s, e in spans if re.match(r"^##\s", stripped[s])]
    h3s = [(s, e) for s, e in spans if re.match(r"^###\s", stripped[s])]
    rep.stats.update(h1=len(heads), h2=len(h2s), h3=len(h3s))

    if len(heads) != 1:
        rep.error(f"заголовков H1 должно быть ровно один, найдено {len(heads)}")
    else:
        s, _ = heads[0]
        if s != 0:
            rep.error("H1 должен быть первым блоком файла")
        title = stripped[s][2:].strip()
        plain_title = title.replace("**", "").strip()
        if not is_caps(plain_title):
            rep.error("H1 должен быть набран ЗАГЛАВНЫМИ")
        if len(plain_title) > MAX_H1:
            rep.error(f"H1 длиннее {MAX_H1} символов ({len(plain_title)})")
        if not (title.startswith("**") and title.endswith("**")):
            rep.warn("H1 лучше делать жирным: `# **ЗАГОЛОВОК**` (требование RICH_EDITORIAL_STANDARD §2)")
        if EMOJI_RE.search(plain_title):
            rep.error(
                "в H1 не должно быть эмодзи — маркер допускается только в начале строки H2 и только по правилу §3"
            )

    # ---------- 3. H2: регистр, длина, воздух, эмодзи-маркер ----------
    h2_titles = [stripped[s][3:].strip().replace("**", "") for s, _ in h2s]
    numbered = [t for t in h2_titles if NUMBERED_H2_RE.match(EMOJI_RE.sub("", t).lstrip())]
    rep.stats.update(h2_numbered=len(numbered))
    for (s, _), title in zip(h2s, h2_titles, strict=True):
        if len(title) > MAX_H2:
            rep.error(f"H2 «{title[:40]}…» длиннее {MAX_H2} символов")
        if is_caps(title):
            rep.error(f"H2 «{title}» набран ЗАГЛАВНЫМИ: в L2 заголовки разделов обычным регистром")

        next_h = len(stripped)
        for j in range(s + 1, len(stripped)):
            if HEADING_RE.match(stripped[j]):
                next_h = j
                break
        section_chars = len("\n".join(stripped[s + 1 : next_h]).strip())
        is_numbered = bool(NUMBERED_H2_RE.match(EMOJI_RE.sub("", title).lstrip()))

        markers = EMOJI_RE.findall(title)
        if markers:
            if is_numbered:
                rep.error(
                    f"H2 «{title[:40]}»: раздел в нумерованной лесенке — номера уже маркируют место, эмодзи не нужен"
                )
            elif len(markers) > 1:
                rep.error(f"H2 «{title[:40]}»: {len(markers)} эмодзи — маркер может быть только один, в начале строки")
            elif not EMOJI_RE.match(title):
                rep.error(f"H2 «{title[:40]}»: эмодзи должен вести строку — это маркер раздела, а не украшение")
            elif section_chars < MARKER_MIN_SECTION_CHARS:
                rep.error(
                    f"H2 «{title[:40]}»: раздел короче ~{MARKER_MIN_SECTION_CHARS} знаков ({section_chars}) — "
                    "маркер на короткой рубрике не ставится"
                )
        if s == 0:
            rep.error("статья начинается с H2: первым блоком должен быть H1")
        else:
            if stripped[s - 1].strip():
                rep.warn(f"перед H2 «{title[:40]}…» нет пустой строки — в Markdown заголовок лучше отделять")

    for s, e in spans:
        if HEADING_RE.match(stripped[s]):
            if e - s > 1:
                rep.error(f"заголовок «{stripped[s][:40]}» разбит на несколько строк")
    for (s1, _), (s2, _) in zip(spans, spans[1:], strict=False):
        if HEADING_RE.match(stripped[s1]) and HEADING_RE.match(stripped[s2]):
            rep.error("два заголовка подряд без текста между ними")
    if spans and HEADING_RE.match(stripped[spans[-1][0]]):
        rep.error("статья заканчивается заголовком")

    # ---------- 4. списки ----------
    items = 0
    for i, ln in enumerate(stripped):
        if MD_LIST_RE.match(ln) and not ln.startswith("— "):
            rep.error(
                f"строка {i + 1}: Markdown-список «{ln[:20]}…» — в L2 запрещён "
                "(редактор склеивает пункты без воздуха). Используйте `• ` или `1. ` отдельными абзацами"
            )
        if ITEM_RE.match(ln):
            items += 1
            if i > 0 and stripped[i - 1].strip():
                rep.error(f"строка {i + 1}: пункт списка не отделён пустой строкой от предыдущего текста")
            if i + 1 < len(stripped) and stripped[i + 1].strip() and ITEM_RE.match(stripped[i + 1]):
                rep.error(f"строка {i + 1}: два пункта списка в одном блоке — каждый пункт отдельным абзацем")
            if len(ln) > MAX_ITEM:
                rep.warn(f"строка {i + 1}: пункт длиннее {MAX_ITEM} символов — возможно, это уже абзац")
    rep.stats["list_items"] = items

    # ---------- 5. цитаты ----------
    # L2: подпись — ПОСЛЕДНЯЯ строка внутри блока цитаты (`> *— …*`).
    # Отдельный абзац под цитатой даёт блочный отступ редактора и лишний воздух.
    quotes, i = 0, 0
    while i < len(stripped):
        if stripped[i].startswith(">"):
            quotes += 1
            start = i
            while i + 1 < len(stripped) and stripped[i + 1].startswith(">"):
                i += 1
            end = i
            body = [ln.lstrip(">").strip() for ln in stripped[start : end + 1]]
            has_attr = bool(body) and bool(ATTRIBUTION_RE.match(body[-1]))
            quote_text = " ".join(body[:-1] if has_attr else body)

            if not has_attr:
                rep.error(
                    f"строка {end + 1}: у цитаты нет подписи последней строкой. "
                    "В L2 правильно: `> *— Автор, «Труд»*` внутри блока"
                )

            if len(quote_text) > MAX_QUOTE:
                rep.warn(
                    f"строка {start + 1}: цитата {len(quote_text)} символов (> {MAX_QUOTE}) — разбейте авторским текстом"
                )

            # подпись отдельным блоком — ошибка L2: даёт разрыв под цитатой
            nxt_idx = end + 1
            while nxt_idx < len(stripped) and not stripped[nxt_idx].strip():
                nxt_idx += 1
            if nxt_idx < len(stripped) and ATTRIBUTION_RE.match(stripped[nxt_idx].strip()):
                rep.error(
                    f"строка {nxt_idx + 1}: подпись стоит отдельным блоком после цитаты — "
                    "в L2 она должна быть последней строкой блока: `> *— Автор, «Труд»*`"
                )

            if ">" in quote_text:
                rep.error(f"строка {start + 1}: вложенная цитата (второй уровень `>`) запрещена")

            # воздух перед цитатой: короткая связка в том же блоке — исключение
            connector_in_block = start > 0 and stripped[start - 1].strip() and not stripped[start - 1].startswith(">")
            has_blank_before = start > 0 and not stripped[start - 1].strip()
            if connector_in_block:
                conn = stripped[start - 1].strip()
                if not (conn.endswith(":") and len(conn) <= MAX_CONNECTOR):
                    rep.error(
                        f"строка {start + 1}: цитата приклеена к абзацу без воздуха (и это не короткая связка с двоеточием)"
                    )
            elif has_blank_before and start >= 2 and not stripped[start - 2].strip():
                rep.error(f"строка {start + 1}: две пустые строки перед цитатой — лишний воздух")
            i = end + 1
        else:
            i += 1
    rep.stats["quotes"] = quotes

    # ---------- 6. хэштеги ----------
    all_tags = HASHTAG_RE.findall(text)
    rep.stats["hashtags"] = len(all_tags)
    if all_tags and not allow_hashtags:
        rep.error(
            f"в L2 хэштегов быть не должно, найдено {len(all_tags)}: "
            "хэштеги остаются в коротких постах (L1). Если они действительно нужны — флаг --allow-hashtags"
        )
    if all_tags and allow_hashtags:
        if spans:
            last_s, _ = spans[-1]
            last = stripped[last_s]
            tags = HASHTAG_RE.findall(last)
            if tags:
                if not (HASHTAGS_MIN <= len(tags) <= HASHTAGS_MAX):
                    rep.error(f"хэштегов {len(tags)}: нужно {HASHTAGS_MIN}–{HASHTAGS_MAX}")
                if len(set(tags)) != len(tags):
                    rep.error("повторяющиеся хэштеги")
                if HASHTAG_RE.sub("", last).strip():
                    rep.error("строка хэштегов содержит лишний текст")
                for tag in tags:
                    if not tag[1:2].isupper():
                        rep.error(f"хэштег {tag}: должен начинаться с заглавной буквы")

    # ---------- 6б. эмодзи в теле ----------
    for s0, e0 in spans:
        if HEADING_RE.match(stripped[s0]) or stripped[s0].startswith(">"):
            continue
        para = " ".join(stripped[s0:e0])
        if EMOJI_RE.search(para):
            rep.error(
                f"строка {s0 + 1}: эмодзи в обычном абзаце — в тексте их не ставят; маркер живёт только в начале заголовка H2"
            )

    # ---------- 7. служебные маркеры и мусор ----------
    low = text.casefold()
    for marker in BANNED:
        if marker in low:
            rep.error(f"служебный/машинный маркер в публичном тексте: «{marker}»")
    raw_urls = re.findall(r"https?://\S+", text)
    if raw_urls:
        rep.warn(f"в тексте {len(raw_urls)} сырых URL: для L2 обычно не нужны")

    # ---------- 8. ритм: лесенка лозунгов ----------
    paras = [
        " ".join(stripped[s:e]).strip()
        for s, e in spans
        if not HEADING_RE.match(stripped[s]) and not ITEM_RE.match(stripped[s]) and not stripped[s].startswith(">")
    ]
    short = [p for p in paras if len(p) < 80 and sentence_count(p) < 2]
    if paras:
        share = len(short) / len(paras)
        rep.stats["short_paragraph_share"] = round(share, 2)
        if share > 0.25:
            rep.warn(
                f"{len(short)} из {len(paras)} абзацев короче 80 символов и в одно предложение — похоже на лозунговую лесенку"
            )

    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description="Preflight статьи @lordchrist (lane L2)")
    ap.add_argument("file", type=Path)
    ap.add_argument("--json", action="store_true", help="вывести отчёт в JSON")
    ap.add_argument("--allow-hashtags", action="store_true", help="разрешить хэштеги (по стандарту L2 их нет)")
    args = ap.parse_args()

    if not args.file.is_file():
        print(f"файл не найден: {args.file}", file=sys.stderr)
        return 2

    rep = check(args.file, allow_hashtags=args.allow_hashtags)

    if args.json:
        print(
            json.dumps(
                {
                    "file": str(args.file),
                    "ok": not rep.errors,
                    "errors": rep.errors,
                    "warnings": rep.warnings,
                    "stats": rep.stats,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Файл: {args.file}")
        print(
            f"Символов: {rep.stats.get('chars')} / {MAX_CHARS} · блоков ≈{rep.stats.get('blocks_estimate')} / {MAX_BLOCKS}"
        )
        print(
            f"H1: {rep.stats.get('h1')} · H2: {rep.stats.get('h2')} · пунктов: {rep.stats.get('list_items')} · "
            f"цитат: {rep.stats.get('quotes')} · хэштегов: {rep.stats.get('hashtags')}"
        )
        print()
        if rep.errors:
            print(f"ОШИБКИ ({len(rep.errors)}):")
            for e in rep.errors:
                print(f"  ✗ {e}")
        if rep.warnings:
            print(f"ПРЕДУПРЕЖДЕНИЯ ({len(rep.warnings)}):")
            for w in rep.warnings:
                print(f"  ! {w}")
        if not rep.errors and not rep.warnings:
            print("Всё чисто: правила L2 соблюдены.")
        elif not rep.errors:
            print("Ошибок нет. Предупреждения не блокируют публикацию.")

    return 0 if not rep.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
