#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сверка библейских цитат статьи с Синодальным переводом.

Правило серии: цитата Писания в статье — дословно по Синодальному переводу
(§10 `content/telegram/lordchrist/RICH_EDITOR_ARTICLE_STANDARD.md`).

Скрипт проверяет каждую цитату Писания, у которой в статье есть ссылка на
стих, и требует, чтобы стоящий рядом с ней текст был дословным фрагментом
этого стиха. Цитаты Писания без ссылки перечисляются отдельно: их оператор
сверяет глазами (правило §11, проход 2).

    python3 scripts/lordchrist_scripture_check.py статья.md --bible /tmp/bible
    python3 scripts/lordchrist_scripture_check.py статья.md --bible /tmp/bible --strict

Корпус: `bibleonline/rst` (Русский синодальный перевод) — файлы `genesis.dat`,
`psalms.dat`, `romans.dat` и т. п. с разметкой `#глава:стих#текст`.
Без корпуса проверка пропускается (код 0), с `--strict` — код 2.

Код возврата: 0 — расхождений нет, 1 — есть расхождения, 2 — проверка пропущена.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BOOKS = {
    "Быт": "genesis",
    "Исх": "exodus",
    "Лев": "leviticus",
    "Чис": "numbers",
    "Вт": "deuteronomy",
    "Ис": "isaiah",
    "Иер": "jeremiah",
    "Иов": "job",
    "Пс": "psalms",
    "Прит": "proverbs",
    "Мф": "matthew",
    "Мк": "mark",
    "Лк": "luke",
    "Ин": "john",
    "Деян": "acts",
    "Рим": "romans",
    "1 Кор": "1corinthians",
    "2 Кор": "2corinthians",
    "Еф": "ephesians",
    "Кол": "colossians",
    "1 Тим": "1timothy",
    "2 Тим": "2timothy",
    "Тит": "titus",
    "1 Пет": "1peter",
    "2 Пет": "2peter",
    "Иуд": "jude",
    "Евр": "hebrews",
    "1 Ин": "1john",
    "Откр": "revelation",
    "Мал": "malachi",
}

BOOK_RE = "|".join(sorted((re.escape(name) for name in BOOKS), key=len, reverse=True))
ABBR_RE = re.compile(rf"(?P<book>{BOOK_RE})\.")
REF_RE = re.compile(
    rf"(?P<book>{BOOK_RE})\.?\s*(?P<ch>\d+):(?P<vs>\d+)"
    rf"(?P<tail>[^0-9А-Яа-я]{{0,3}}(?:\d+(?:\s*[-–,]\s*\d+)*)?)"
)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
QUOTE_RE = re.compile(r"«([^»]{4,})»", re.S)
SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")
ENTITY_RE = re.compile(r"&[a-z]+;|&#\d+;")
TAG_RE = re.compile(r"<[^>]+>")
MARK = "\x00"
HEAD = 4  # сколько слов в начале стиха опознают цитату


def words(text: str) -> list[str]:
    text = ENTITY_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"[^0-9A-Za-zА-Яа-яЁё\s]", " ", text)
    return [word for word in text.lower().split() if word]


def load_corpus(directory: Path) -> dict[str, dict[tuple[int, int], str]]:
    corpus: dict[str, dict[tuple[int, int], str]] = {}
    for name, file_name in BOOKS.items():
        path = directory / f"{file_name}.dat"
        if not path.exists():
            continue
        verses: dict[tuple[int, int], str] = {}
        for line in path.read_text(encoding="utf-8").split("\n"):
            match = re.match(r"^#(\d+):(\d+)#(.*)$", line)
            if match:
                verses[(int(match.group(1)), int(match.group(2)))] = match.group(3).strip()
        corpus[name] = verses
    return corpus


def reference_places(match: re.Match[str]) -> list[tuple[int, int]]:
    """Стихи, названные ссылкой: `10:9-10` — диапазон, `18:2,4` — список."""
    chapter, verse = int(match.group("ch")), int(match.group("vs"))
    tail = match.group("tail") or ""
    numbers = [int(number) for number in re.findall(r"\d+", tail)]
    if not numbers:
        return [(chapter, verse)]
    if tail.lstrip()[:1] in {"-", "–"}:
        return [(chapter, number) for number in range(verse, numbers[-1] + 1)]
    return [(chapter, verse)] + [(chapter, number) for number in numbers]


def verse_text(verses: dict[tuple[int, int], str], places: list[tuple[int, int]]) -> str:
    parts = []
    for place in places:
        text = verses.get(place)
        if text is None:
            return ""
        parts.append(text)
    return " ".join(parts)


def is_run_of(fragment: list[str], verse_words: list[str]) -> bool:
    """Фрагмент цитаты — непрерывный кусок стиха?"""
    if not fragment or len(fragment) > len(verse_words):
        return False
    for start in range(len(verse_words) - len(fragment) + 1):
        if verse_words[start : start + len(fragment)] == fragment:
            return True
    return False


def body_sentences(text: str) -> list[str]:
    """Предложения основного текста (без строк цитат `>`)."""
    out: list[str] = []
    for line in text.split("\n"):
        if line.startswith(">") or not line.strip() or line.startswith("# "):
            continue
        protected = ABBR_RE.sub(lambda match: match.group(0)[:-1] + MARK, line)
        for match in SENTENCE_RE.finditer(protected):
            out.append(match.group(0).replace(MARK, "."))
    return out


def epigraph_quotes(text: str) -> list[tuple[str, str]]:
    """Цитаты-эпиграфы: блок `>` с подписью-ссылкой на стих."""
    out: list[tuple[str, str]] = []
    lines = text.split("\n")
    block: list[str] = []
    for line in lines:
        if line.startswith(">"):
            block.append(line[1:].strip())
            continue
        if block:
            attribution = line.strip()
            if REF_RE.search(attribution):
                out.append((" ".join(block), attribution))
            block = []
    if block and REF_RE.search(lines[-1] if lines else ""):
        out.append((" ".join(block), lines[-1].strip()))
    return out


def head_index(corpus: dict[str, dict[tuple[int, int], str]]) -> dict[tuple[str, ...], str]:
    """Начала стихов: четыре первых слова → текст стиха."""
    index: dict[tuple[str, ...], str] = {}
    for verses in corpus.values():
        for text in verses.values():
            verse_words = words(text)
            if len(verse_words) >= HEAD:
                index.setdefault(tuple(verse_words[:HEAD]), text)
    return index


def check(markdown: Path, corpus: dict[str, dict[tuple[int, int], str]]) -> tuple[list[str], list[str]]:
    text = markdown.read_text(encoding="utf-8")
    errors: list[str] = []
    notes: list[str] = []
    index = head_index(corpus)

    for fragment, attribution in epigraph_quotes(text):
        match = REF_RE.search(attribution)
        if not match:
            continue
        verses = corpus.get(match.group("book"))
        if not verses:
            continue
        source = verse_text(verses, reference_places(match))
        if not source:
            continue
        if not is_run_of(words(fragment), words(source)):
            errors.append(f"эпиграф ({match.group(0).strip()}): текст не совпадает со стихом — {fragment[:80]}")

    for sentence in body_sentences(text):
        refs = list(REF_RE.finditer(sentence))
        bold = [(match.start(), match.group(1)) for match in BOLD_RE.finditer(sentence)]
        quoted = [(match.start(), match.group(1)) for match in QUOTE_RE.finditer(sentence)]
        for position, content in bold:
            if len(words(content)) < 3:
                continue
            if not refs:
                if tuple(words(content)[:HEAD]) in index:
                    notes.append(f"цитата Писания без ссылки на стих: {content[:70]}")
                continue
            end = position + len(content)
            following = [item for item in refs if item.start() >= end]
            if following:
                best = following[0]
            else:
                before = [item for item in refs if item.end() <= position]
                if not before:
                    continue
                best = before[-1]
            verses = corpus.get(best.group("book"))
            if not verses:
                continue
            source = verse_text(verses, reference_places(best))
            if not source:
                continue
            if not is_run_of(words(content), words(source)):
                errors.append(f"{best.group(0).strip()}: цитата не совпадает со стихом — {content[:80]}")
        for _, content in quoted:
            if len(words(content)) >= HEAD and tuple(words(content)[:HEAD]) in index:
                notes.append(f"цитата Писания без ссылки на стих: {content[:70]}")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Сверка цитат Писания с Синодальным переводом.")
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--bible", type=Path, default=Path("/tmp/bible"), help="каталог с корпусом *.dat")
    parser.add_argument("--strict", action="store_true", help="корпус обязателен")
    parser.add_argument("--quiet", action="store_true", help="не печатать цитаты без ссылки")
    args = parser.parse_args()

    corpus = load_corpus(args.bible) if args.bible.exists() else {}
    if not corpus:
        print(f"корпус Синодального перевода не найден в {args.bible} — проверка пропущена")
        return 2 if args.strict else 0

    errors, notes = check(args.markdown, corpus)
    if notes and not args.quiet:
        print(f"{args.markdown.name}: цитат Писания без ссылки — {len(notes)} (сверяются глазами):")
        for note in notes:
            print(f"  ? {note}")
    if errors:
        print(f"Расхождения в {args.markdown.name}:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"{args.markdown.name}: расхождений с Синодальным переводом нет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
