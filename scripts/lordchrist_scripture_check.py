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
    python3 scripts/lordchrist_scripture_check.py статья.md --bible /tmp/bible --quotes
    python3 scripts/lordchrist_scripture_check.py статья.md --bible /tmp/bible --strict

Сверяются жирные цитаты (`**…**`) и эпиграф — в том числе эпиграф в форме L2,
где атрибуция `> — Ин. 8:36` стоит последней строкой блока. Фрагменты в
кавычках («…») сверяются только с `--quotes`: в статьях серии встречаются
вариантные чтения (кетив, «в лицо/в лице»), и без флага они не должны валить
прогон — но и молчать о них нельзя, поэтому они попадают в отчёт как
«не сверена без --quotes».

Корпус: `bibleonline/rst` (Русский синодальный перевод) — файлы `genesis.dat`,
`psalms.dat`, `romans.dat` и т. п. с разметкой `#глава:стих#текст`. Годятся
оба цифровых извода РСТ: они расходятся в единичных стихах (Быт. 2:19
«образовал/создал», 2:7 «в лицо/в лице»), поэтому статью лучше прогонять по
корпусу, названному в её источниках. Знаки ударения (`&#769;`, U+0301) не
считаются расхождением.
Без корпуса проверка пропускается (код 0), с `--strict` — код 2.

Код возврата: 0 — расхождений нет, 1 — есть расхождения, 2 — проверка пропущена.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
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
    # Синодальная нумерация Царств: 1–2 Цар = 1–2 Samuel, 3–4 Цар = 1–2 Kings.
    "1 Цар": "1samuel",
    "2 Цар": "2samuel",
    "3 Цар": "1kings",
    "4 Цар": "2kings",
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
NUMERIC_ENTITY_RE = re.compile(r"&#(\d+);")
TAG_RE = re.compile(r"<[^>]+>")
MARK = "\x00"
HEAD = 4  # сколько слов в начале стиха опознают цитату


def words(text: str) -> list[str]:
    # Числовые сущности (`&#769;`) — знаки ударения в цифровых изданиях
    # Синодального: снимаем их вместе с комбинирующими знаками, иначе
    # «Входи&#769;те» рассыпается на два слова и стих «не совпадает».
    text = NUMERIC_ENTITY_RE.sub(lambda m: chr(int(m.group(1))), text)
    text = ENTITY_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    text = "".join(char for char in unicodedata.normalize("NFD", text) if not unicodedata.combining(char))
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


def ref_label(match: re.Match[str]) -> str:
    """`Быт. 2:19).` → `Быт. 2:19` — для отчёта, без хвостовой пунктуации."""
    return f"{match.group('book')}. {match.group('ch')}:{match.group('vs')}"


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
    """Цитаты-эпиграфы: блок `>` с подписью-ссылкой на стих.

    Подпись ищется в двух местах: строкой ниже блока (транспорт L1) и последней
    строкой самого блока (транспорт L2, `> — Ин. 8:34–36`). Без второго случая
    эпиграф длинной статьи не проверялся вовсе.
    """
    out: list[tuple[str, str]] = []
    lines = text.split("\n")
    block: list[str] = []

    def flush(attribution: str) -> None:
        body = list(block)
        if body and REF_RE.search(body[-1]) and body[-1].lstrip().startswith("—"):
            attribution = attribution or body.pop()
        if body and attribution and REF_RE.search(attribution):
            out.append((" ".join(body), attribution))
        block.clear()

    for line in lines:
        if line.startswith(">"):
            block.append(line[1:].strip())
            continue
        if block:
            flush(line.strip())
    if block:
        flush("")
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


def check(
    markdown: Path,
    corpus: dict[str, dict[tuple[int, int], str]],
    check_quotes: bool = False,
) -> tuple[list[str], list[str]]:
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
            errors.append(f"эпиграф ({ref_label(match)}): текст не совпадает со стихом — {fragment[:80]}")

    for sentence in body_sentences(text):
        refs = list(REF_RE.finditer(sentence))
        bold = [(match.start(), match.group(1)) for match in BOLD_RE.finditer(sentence)]
        bold_spans = [(match.start(), match.start() + len(match.group(1))) for match in BOLD_RE.finditer(sentence)]

        def check_fragment(position: int, content: str, refs: list[re.Match[str]] = refs) -> None:
            """Сверить фрагмент с ближайшей ссылкой; без ссылки — только заметка."""
            if len(words(content)) < 3:
                return
            end = position + len(content)
            following = [item for item in refs if item.start() >= end]
            if following:
                best = following[0]
            else:
                before = [item for item in refs if item.end() <= position]
                if not before:
                    if tuple(words(content)[:HEAD]) in index:
                        notes.append(f"цитата Писания без ссылки на стих: {content[:70]}")
                    return
                best = before[-1]
            verses = corpus.get(best.group("book"))
            if not verses:
                return
            source = verse_text(verses, reference_places(best))
            if not source:
                return
            if not is_run_of(words(content), words(source)):
                errors.append(f"{ref_label(best)}: цитата не совпадает со стихом — {content[:80]}")

        for position, content in bold:
            check_fragment(position, content)
        # Кавычки «…»: с флагом `--quotes` сверяются так же, как жирный текст
        # (Писание в L2 цитируется и без жирного). По умолчанию — только
        # заметка: в опубликованных статьях серии встречаются вариантные
        # чтения (кетив, «в лицо/в лице»), которые нельзя считать ошибкой
        # перевода, а без флага они не должны валить проверку.
        for match in QUOTE_RE.finditer(sentence):
            start = match.start()
            if any(left <= start < right for left, right in bold_spans):
                continue
            if check_quotes:
                check_fragment(start, match.group(1))
                continue
            # По умолчанию фрагмент в кавычках не сверяется, но если рядом есть
            # ссылка на стих, об этом надо сказать прямо: иначе отчёт читается
            # как «всё проверено», а фрагмент остался непроверенным.
            end = start + len(match.group(0))
            following = [item for item in refs if item.start() >= end]
            before = [item for item in refs if item.end() <= start]
            if following or before:
                ref = following[0] if following else before[-1]
                notes.append(f"цитата в кавычках не сверена без --quotes: {ref_label(ref)} — {match.group(1)[:60]}")
            elif len(words(match.group(1))) >= HEAD and tuple(words(match.group(1))[:HEAD]) in index:
                notes.append(f"цитата Писания без ссылки на стих: {match.group(1)[:70]}")
    return errors, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Сверка цитат Писания с Синодальным переводом.")
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--bible", type=Path, default=Path("/tmp/bible"), help="каталог с корпусом *.dat")
    parser.add_argument("--strict", action="store_true", help="корпус обязателен")
    parser.add_argument("--quiet", action="store_true", help="не печатать цитаты без ссылки")
    parser.add_argument(
        "--quotes",
        action="store_true",
        help="сверять и обычные кавычки «…» рядом со ссылкой, а не только жирный текст",
    )
    args = parser.parse_args()

    corpus = load_corpus(args.bible) if args.bible.exists() else {}
    if not corpus:
        print(f"корпус Синодального перевода не найден в {args.bible} — проверка пропущена")
        return 2 if args.strict else 0

    errors, notes = check(args.markdown, corpus, check_quotes=args.quotes)
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
