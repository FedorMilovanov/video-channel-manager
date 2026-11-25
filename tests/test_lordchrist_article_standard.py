from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _bible_dir() -> Path:
    """Каталог с `.dat`-книгами Синодального перевода: переменная окружения, затем обычные места."""
    candidates = []
    if os.environ.get("LORDCHRIST_BIBLE_DIR"):
        candidates.append(Path(os.environ["LORDCHRIST_BIBLE_DIR"]))
    # bibleonline/rst (RSTE) — корпус, названный стандартом серии; swmail/RST —
    # другой извод того же перевода, где единичные стихи читаются иначе.
    candidates += [Path("/tmp/bible"), Path("/tmp/rste"), Path("/tmp/synodal")]
    for candidate in candidates:
        if (candidate / "john.dat").exists():
            return candidate
    return Path("/tmp/bible")


BIBLE_DIR = _bible_dir()  # корпус Синодального перевода (bibleonline/rst)
sys.path.insert(0, str(ROOT / "scripts"))

from lordchrist_article_preflight import check  # noqa: E402
from render_l2_copy_page import render  # noqa: E402

SOURCE_NOTE = (
    "Цитаты Чарнока — из книги **«Беседы о существовании и атрибутах Бога»** "
    "(*Discourses upon the Existence and Attributes of God*); "
    "текст по изданию 1853 года, оцифровка: Project Gutenberg, eBook #53527, "
    "https://www.gutenberg.org/ebooks/53527."
)

LEAD = (
    "Лид статьи с подробным описанием контекста и вводных мыслей для читателей канала. "
    "Он вводит тему и обещает предметное богословское рассуждение."
)
BODY = (
    "Это полноценный абзац раздела, который подробно раскрывает главную мысль темы и держит "
    "аргумент на протяжении нескольких предложений подряд, без лозунгов и обрывов. "
    "В нём есть богословское и историческое основание, позволяющее читателю проследить логику."
)


def _article(quote: str, body: str = BODY) -> str:
    return (
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{LEAD}\n\n## Именованный раздел без маркера\n\n{body}\n\n"
        f"{quote}\n\n{SOURCE_NOTE}\n"
    )


def test_render_sample_article_has_cite_and_no_legacy_attribution() -> None:
    sample_path = ROOT / "content/telegram/lordchrist/examples/ОБРАЗЕЦ-статья-L2.md"
    md = sample_path.read_text(encoding="utf-8")
    rich_html, _, _ = render(md)

    assert "<cite>" in rich_html
    assert rich_html.count("<cite>") >= 2
    assert "<br><i>— " not in rich_html


def test_sample_article_passes_preflight() -> None:
    sample_path = ROOT / "content/telegram/lordchrist/examples/ОБРАЗЕЦ-статья-L2.md"
    rep = check(sample_path)
    assert not rep.errors


def test_series_articles_pass_preflight() -> None:
    charnock = ROOT / "content/telegram/lordchrist/rich-v1/charnock"
    articles = sorted(path for path in charnock.glob("lordchrist-rich-charnock-*.md") if "-проверка" not in path.name)
    assert len(articles) >= 3
    for article in articles:
        rep = check(article)
        assert not rep.errors, f"{article.name}: {rep.errors}"
        # Legacy rich-lane articles predate the 2026-10-24 anti-fragmentation
        # rule; the «мелкоцитатосып» warning is a gate for new Telegraph
        # editions, not a retroactive defect of published rich articles.
        blocking = [w for w in rep.warnings if "мелкоцитатосып" not in w]
        assert not blocking, f"{article.name}: {blocking}"


def test_preflight_emoji_marker_in_heading_fails(tmp_path: Path) -> None:
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{LEAD}\n\n## 🏛 Именованный раздел\n\n{BODY}\n\n{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert any("эмодзи" in err for err in rep.errors)


def test_preflight_emoji_in_body_paragraph_is_error(tmp_path: Path) -> None:
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n"
        f"{LEAD}\n\n"
        "## Именованный раздел без маркера\n\n"
        "Обычный абзац текста, в который случайно попал эмодзи 🏛 прямо в середину текста. "
        "Такой эмодзи в теле абзаца запрещён правилами L2.\n\n"
        "Второй абзац текста продолжает рассуждение и развивает аргумент дальше без нарушений. "
        "Здесь нет никаких посторонних графических элементов.\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert any("эмодзи в тексте" in err for err in rep.errors)
    assert not any("эмодзи в тексте" in w for w in rep.warnings)


def test_preflight_emoji_inside_quote_is_error(tmp_path: Path) -> None:
    quote = "> «Точный текст цитаты 🏛, достаточно длинной для отдельного блока.»\n> — Стивен Чарнок, «О бытии Бога»"
    doc = tmp_path / "article.md"
    doc.write_text(_article(quote), encoding="utf-8")
    rep = check(doc)
    assert any("эмодзи в тексте" in err for err in rep.errors)


def test_preflight_article_without_emoji_has_no_emoji_errors(tmp_path: Path) -> None:
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n"
        f"{LEAD}\n\n"
        "## Чистый раздел без эмодзи\n\n"
        "Первый абзац статьи без каких-либо эмодзи раскрывает суть рассматриваемого вопроса. "
        "Он формулирует основные положения аргумента последовательно и ясно.\n\n"
        "Второй абзац раздела развивает начатую мысль и приводит к обоснованному заключению. "
        "Никаких эмодзи или запрещённых символов здесь нет.\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert not any("эмодзи" in err.lower() for err in rep.errors)


def test_preflight_accepts_plain_attribution_without_asterisks(tmp_path: Path) -> None:
    quote = "> «Точный текст цитаты, достаточно длинной для отдельного блока.»\n> — Стивен Чарнок, «О бытии Бога»"
    doc = tmp_path / "article.md"
    doc.write_text(_article(quote), encoding="utf-8")
    rep = check(doc)
    assert not rep.errors
    assert not rep.warnings


def test_preflight_accepts_large_quote_block(tmp_path: Path) -> None:
    """Крупная цитата — норма, а не дефект: до ~4 000 знаков одним пассажем."""
    long_quote = " ".join(["Слово о Боге и о человеке, сказанное прямо и без оговорок."] * 40)
    quote = f"> «{long_quote}»\n> — Стивен Чарнок, «О бытии Бога»"
    assert 1_000 < len(long_quote) < 3_000
    doc = tmp_path / "article.md"
    doc.write_text(_article(quote), encoding="utf-8")
    rep = check(doc)
    assert not rep.errors
    assert not any("цитата" in warning for warning in rep.warnings)


def test_preflight_accepts_bold_and_italic_in_body(tmp_path: Path) -> None:
    """С 22.10.2026 жирный и курсив разрешены: проверяется только целостность разметки."""
    doc = tmp_path / "article.md"
    doc.write_text(
        _article("Обычный абзац.", body=f"{BODY} И ещё **жирный акцент** и *курсив*."),
        encoding="utf-8",
    )
    rep = check(doc)
    assert not rep.errors


def test_preflight_rejects_unclosed_markup(tmp_path: Path) -> None:
    doc = tmp_path / "article.md"
    doc.write_text(_article("Обычный абзац.", body=f"{BODY} И ещё **жирный акцент."), encoding="utf-8")
    assert any("жирный не закрыт" in err for err in check(doc).errors)

    doc.write_text(_article("Обычный абзац.", body=f"{BODY} И ещё *курсив."), encoding="utf-8")
    assert any("курсив не закрыт" in err for err in check(doc).errors)


def test_build_l2_rich_document_keeps_markup_and_credit(tmp_path: Path) -> None:
    from build_l2_rich_document import build

    document = {
        "schema_name": "video-channel-manager.rich-article-document",
        "document_id": "test",
        "metadata": {"title": "Тест", "language": "ru"},
        "blocks": [],
    }
    doc_path = tmp_path / "doc.json"
    doc_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    md_path = tmp_path / "article.md"
    md_path.write_text(
        "# **ТЕСТ**\n\nАбзац с *курсивом* и **жирным**.\n\n> «Цитата»\n> — Стивен Чарнок, «О бытии Бога»\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )

    built = build(md_path, doc_path)
    heading, paragraph, quote = built["blocks"][:3]
    assert heading["text"] == [{"type": "bold", "text": "ТЕСТ"}] and heading["size"] == 1
    assert paragraph["text"] == [
        "Абзац с ",
        {"type": "italic", "text": "курсивом"},
        " и ",
        {"type": "bold", "text": "жирным"},
        ".",
    ]
    assert quote["credit"] == "— Стивен Чарнок, «О бытии Бога»"
    assert quote["blocks"][0]["text"] == "«Цитата»"
    assert json.loads(doc_path.read_text(encoding="utf-8"))["blocks"] == built["blocks"]


def test_build_l2_rich_document_keeps_plain_text_plain(tmp_path: Path) -> None:
    from build_l2_rich_document import build

    document = {
        "schema_name": "video-channel-manager.rich-article-document",
        "document_id": "test",
        "metadata": {"title": "Тест", "language": "ru"},
        "blocks": [],
    }
    doc_path = tmp_path / "doc.json"
    doc_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    md_path = tmp_path / "article.md"
    md_path.write_text("# **ТЕСТ**\n\nОбычный абзац без всякой разметки.\n", encoding="utf-8")

    built = build(md_path, doc_path)
    assert built["blocks"][1]["text"] == "Обычный абзац без всякой разметки."


def test_preflight_rejects_translation_note_under_quote(tmp_path: Path) -> None:
    quote = (
        "> «Точный текст цитаты, достаточно длинной для отдельного блока.»\n"
        "> — Стивен Чарнок, «О бытии Бога», перевод мой"
    )
    doc = tmp_path / "article.md"
    doc.write_text(_article(quote), encoding="utf-8")
    assert any("пометка о переводе" in err for err in check(doc).errors)


def test_preflight_rejects_italic_attribution(tmp_path: Path) -> None:
    """Подпись цитаты в L2 — plain: курсивом она не читается как подпись."""
    quote = "> «Точный текст цитаты, достаточно длинной для отдельного блока.»\n> *— Стивен Чарнок, «О бытии Бога»*"
    doc = tmp_path / "article.md"
    doc.write_text(_article(quote), encoding="utf-8")
    rep = check(doc)
    assert any("нет подписи" in err for err in rep.errors)


def test_render_puts_air_before_headings_and_around_quotes() -> None:
    article = ROOT / "content/telegram/lordchrist/rich-v1/charnock/lordchrist-rich-charnock-01.md"
    rich_html, _, stats = render(article.read_text(encoding="utf-8"))

    assert "\u200b" not in rich_html, "нулевой пробел редактор выбрасывает — воздух исчезнет при вставке"
    assert rich_html.count("\u00a0") == stats["air"]
    assert rich_html.lstrip().startswith("<h1>"), "перед первым блоком воздуха нет"
    # нигде нет двух пустых блоков подряд
    assert "\u00a0</p>\n<p>\u00a0</p>" not in rich_html
    # после заголовка воздух не ставится: текст идёт сразу за ним
    assert "</h2>\n<p>\u00a0</p>" not in rich_html
    # воздух сверху и снизу цитаты
    assert "</p>\n<p>\u00a0</p>\n<blockquote>" in rich_html
    assert "</blockquote>\n<p>\u00a0</p>\n<p>" in rich_html
    # перед цитатой не бывает двух воздухов, даже если дальше заголовок
    assert "</blockquote>\n<p>\u00a0</p>\n<p>\u00a0</p>" not in rich_html
    assert stats["air"] > stats["headings"] + stats["quotes"]


def test_render_keeps_bold_and_italic_as_html() -> None:
    article = ROOT / "content/telegram/lordchrist/rich-v1/charnock/lordchrist-rich-charnock-01.md"
    rich_html, _, _ = render(article.read_text(encoding="utf-8"))

    assert "<b>" in rich_html
    assert "<i>" in rich_html
    assert "**" not in rich_html


def test_render_keeps_connector_tight_to_its_quote() -> None:
    md = "# ТЕСТ\n\nАбзац перед связкой во всю строку, чтобы блок был не коротким.\n\nОб этом он говорит иначе:\n> «Цитата»\n> — Стивен Чарнок, «О бытии Бога»\n"
    rich_html, _, _ = render(md)
    assert "иначе:</p>\n<blockquote>" in rich_html


def test_preflight_rejects_emoji_in_the_source_note(tmp_path: Path) -> None:
    note = SOURCE_NOTE.replace("текст по изданию", "📚 текст по изданию")
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{LEAD}\n\n## Именованный раздел без маркера\n\n{BODY}\n\n{note}\n",
        encoding="utf-8",
    )
    assert any("эмодзи в тексте" in err for err in check(doc).errors)


def test_preflight_rejects_emoji_marker_before_the_source_note(tmp_path: Path) -> None:
    note = "📖 " + SOURCE_NOTE
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{LEAD}\n\n## Именованный раздел без маркера\n\n{BODY}\n\n{note}\n",
        encoding="utf-8",
    )
    assert any("эмодзи в тексте" in err for err in check(doc).errors)


def test_preflight_rejects_duplicate_quote(tmp_path: Path) -> None:
    """Правило двух прогонов: одна и та же цитата дважды в статье — дефект."""
    quote = "> «Один и тот же текст цитаты, дословно повторённый в статье.»\n> — Стивен Чарнок, «О бытии Бога»"
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{LEAD}\n\n## Именованный раздел без маркера\n\n{BODY}\n\n{quote}\n\n{BODY}\n\n{quote}\n\n{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert any("дубль цитаты" in err for err in rep.errors)


def test_reviewed_articles_have_one_anchor_per_quote() -> None:
    """Статьи, прошедшие два прогона: якорь на каждую цитату, source_id уникальны."""
    from lordchrist_article_sources_check import check as sources_check

    charnock = ROOT / "content/telegram/lordchrist/rich-v1/charnock"
    reviewed = [charnock / f"lordchrist-rich-charnock-{n}.md" for n in ("02", "03", "04", "05")]
    for article in reviewed:
        errors = sources_check(article, article.with_suffix(".json"), None, [])
        assert not errors, f"{article.name}: {errors}"


def test_reviewed_articles_keep_distinct_quotes() -> None:
    """Ни одна цитата статьи не повторяется дословно (детектор дублей preflight)."""
    charnock = ROOT / "content/telegram/lordchrist/rich-v1/charnock"
    for name in (
        "lordchrist-rich-charnock-01.md",
        "lordchrist-rich-charnock-02.md",
        "lordchrist-rich-charnock-03.md",
        "lordchrist-rich-charnock-04.md",
        "lordchrist-rich-charnock-05.md",
    ):
        article = charnock / name
        rep = check(article)
        assert not any("дубль цитаты" in err for err in rep.errors)


def test_scripture_check_rejects_a_quote_that_is_not_synodal(tmp_path: Path) -> None:
    """Цитата Писания, не совпадающая со Синодальным переводом, — дефект."""
    from lordchrist_scripture_check import check as scripture_check, load_corpus

    corpus = load_corpus(BIBLE_DIR)
    if not corpus:
        return  # корпус Синодального перевода не положен рядом с репозиторием
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТ**\n\nСлово Божие говорит: **И сотворил Бог из земли всяких зверей земных** (Быт. 2:19).\n",
        encoding="utf-8",
    )
    errors, _notes = scripture_check(doc, corpus)
    assert any("Быт. 2:19" in err for err in errors)


def test_scripture_check_accepts_a_synodal_quote(tmp_path: Path) -> None:
    """Дословный стих Синодального перевода — расхождений нет."""
    from lordchrist_scripture_check import check as scripture_check, load_corpus

    corpus = load_corpus(BIBLE_DIR)
    if not corpus:
        return
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТ**\n\nСлово Божие говорит: **Господь Бог образовал из земли всех животных полевых** (Быт. 2:19).\n",
        encoding="utf-8",
    )
    errors, _notes = scripture_check(doc, corpus)
    assert not errors


def test_reviewed_articles_have_synodal_scripture() -> None:
    """Статьи серии: цитаты Писания дословны по Синодальному переводу."""
    from lordchrist_scripture_check import check as scripture_check, load_corpus

    corpus = load_corpus(BIBLE_DIR)
    if not corpus:
        return
    # Изводы РСТ расходятся в единичных стихах (Быт. 2:19 «образовал/создал»,
    # 2:7 «в лицо/в лице»): опубликованные статьи серии держатся bibleonline/rst.
    if "образовал" not in (corpus.get("Быт", {}).get((2, 19)) or ""):
        return  # рядом лежит другой извод — сверять статьи по нему нельзя
    charnock = ROOT / "content/telegram/lordchrist/rich-v1/charnock"
    for number in ("01", "02", "03", "04", "05"):
        article = charnock / f"lordchrist-rich-charnock-{number}.md"
        errors, _notes = scripture_check(article, corpus)
        assert not errors, f"{article.name}: {errors}"


def test_preflight_accepts_multi_author_bibliographic_note(tmp_path: Path) -> None:
    """Статья-разбор нескольких свидетелей: пометка перечисляет авторов, форма та же."""
    note = (
        "Цитаты Эдвардса — из книги **«Свобода воли»** (*Freedom of the Will*), 1754; "
        "Лютера — из книги **«О рабстве воли»** (*De servo arbitrio*), 1525. "
        "Оцифровки — Project Gutenberg: https://www.gutenberg.org"
    )
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{LEAD}\n\n## Именованный раздел\n\n{BODY}\n\n{note}\n",
        encoding="utf-8",
    )
    assert not check(doc).errors


def test_preflight_rejects_bibliographic_note_without_source_url(tmp_path: Path) -> None:
    note = "Цитаты Эдвардса — из книги **«Свобода воли»** (*Freedom of the Will*), 1754."
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{LEAD}\n\n## Именованный раздел\n\n{BODY}\n\n{note}\n",
        encoding="utf-8",
    )
    assert any("gutenberg.org" in err for err in check(doc).errors)


def test_sources_check_accepts_anchors_of_several_works(tmp_path: Path) -> None:
    """Якорь цитаты — `src-NN-<труд>`: у статьи-разбора трудов несколько."""
    from lordchrist_article_sources_check import check as sources_check

    first = "Liberty is the power to do as one pleases without considering how the pleasure came to be."
    second = "Thus the human will is a beast between the two riders and it cannot choose its rider."
    corpus = tmp_path / "corpus.txt"
    corpus.write_text(f"{first}\n{second}", encoding="utf-8")

    markdown = tmp_path / "article.md"
    markdown.write_text(
        "# **ТЕСТ**\n\n"
        "> «Всякий, делающий грех, есть раб греха.»\n> — Ин. 8:34\n\n"
        "Лид статьи, который вводит тему и обещает предметное рассуждение.\n\n"
        "> «Свобода есть сила делать, что угодно.»\n> — Джонатан Эдвардс, «Свобода воли»\n\n"
        "Абзац статьи, который объясняет цитату и держит аргумент на нескольких предложениях.\n\n"
        "Цитаты Эдвардса — из книги **«Свобода воли»** (*Freedom of the Will*), Project Gutenberg: "
        "https://www.gutenberg.org\n",
        encoding="utf-8",
    )
    document = tmp_path / "article.json"
    document.write_text(
        json.dumps(
            {
                "schema_name": "video-channel-manager.rich-article-document",
                "document_id": "test",
                "blocks": [],
                "sources": [
                    {"source_id": "src-01-scripture", "label": "Ин. 8:34", "evidence": "Синодальный."},
                    {
                        "source_id": "src-02-edwards-will",
                        "label": "Джонатан Эдвардс, «Свобода воли», цитата 2",
                        "url": "https://ccel.org/ccel/edwards/will",
                        "evidence": f"EN: {first}  [смещение 0 в блоке W1 (позиция 0; {len(first)} зн.), CCEL; перевод канала]",
                    },
                    {
                        "source_id": "src-scripture-synodal",
                        "label": "Синодальный перевод: стихи статьи",
                        "url": "https://github.com/bibleonline/rst",
                        "evidence": "Ин. 8:34.",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    errors = sources_check(markdown, document, corpus, [f"W1:0:{len(first)}", f"W2:{len(first) + 1}:{len(second)}"])
    assert not errors, errors


def test_scripture_check_verifies_epigraph_of_l2_transport(tmp_path: Path) -> None:
    """Эпиграф в форме L2: атрибуция последней строкой внутри блока — стих сверяется."""
    from lordchrist_scripture_check import check as scripture_check, load_corpus

    corpus = load_corpus(BIBLE_DIR)
    if not corpus:
        return
    ok = tmp_path / "ok.md"
    ok.write_text(
        "# **ТЕСТ**\n\n"
        "> «Если Сын освободит вас, то истинно свободны будете»\n> — Ин. 8:36\n\n"
        "Абзац статьи, который продолжает мысль эпиграфа и держит аргумент.\n",
        encoding="utf-8",
    )
    errors, _notes = scripture_check(ok, corpus)
    assert not errors, errors

    bad = tmp_path / "bad.md"
    bad.write_text(
        "# **ТЕСТ**\n\n"
        "> «Если Сын освободит вас, то истинно свободными будете»\n> — Ин. 8:36\n\n"
        "Абзац статьи, который продолжает мысль эпиграфа и держит аргумент.\n",
        encoding="utf-8",
    )
    errors, _notes = scripture_check(bad, corpus)
    assert any("Ин. 8:36" in err for err in errors)


def test_scripture_check_knows_the_books_of_kings(tmp_path: Path) -> None:
    """1 Цар. и 3 Цар. проверяются: раньше эти книги молча выпадали из сверки."""
    from lordchrist_scripture_check import check as scripture_check, load_corpus

    corpus = load_corpus(BIBLE_DIR)
    if not corpus:
        return
    ok = tmp_path / "ok.md"
    ok.write_text(
        "# **ТЕСТ**\n\n"
        "Писание говорит: **Но они не слушали голоса отца своего, ибо Господь решил уже предать их смерти** (1 Цар. 2:25).\n",
        encoding="utf-8",
    )
    errors, _notes = scripture_check(ok, corpus)
    assert not errors, errors

    bad = tmp_path / "bad.md"
    bad.write_text(
        "# **ТЕСТ**\n\n"
        "Писание говорит: **Но они не слушали голоса отца своего, ибо Господь решил уже предать их казни** (1 Цар. 2:25).\n",
        encoding="utf-8",
    )
    errors, _notes = scripture_check(bad, corpus)
    assert any("1 Цар. 2:25" in err for err in errors)


def test_scripture_check_checks_plain_quotes_only_on_demand(tmp_path: Path) -> None:
    """«…» рядом со ссылкой: по умолчанию только отмечается, с --quotes — сверяется."""
    from lordchrist_scripture_check import check as scripture_check, load_corpus

    corpus = load_corpus(BIBLE_DIR)
    if not corpus:
        return
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТ**\n\nОн сказал: «Если Сын освободит вас, то истинно свободными будете» (Ин. 8:36).\n",
        encoding="utf-8",
    )
    errors, notes = scripture_check(doc, corpus)
    assert not errors  # вариантные чтения не ломают прогон
    assert any("Ин. 8:36" in note and "не сверена" in note for note in notes)

    errors, _notes = scripture_check(doc, corpus, check_quotes=True)
    assert any("Ин. 8:36" in err for err in errors)


def test_sources_check_requires_the_named_block_to_be_passed(tmp_path: Path) -> None:
    """Якорь называет блок — этот блок обязан быть в --block, иначе зачёт по чужому совпадению."""
    from lordchrist_article_sources_check import check as sources_check

    first = "Liberty is the power to do as one pleases without considering how the pleasure came to be."
    corpus = tmp_path / "corpus.txt"
    corpus.write_text(first, encoding="utf-8")

    markdown = tmp_path / "article.md"
    markdown.write_text(
        "# **ТЕСТ**\n\n"
        "> «Свобода есть сила делать, что угодно.»\n> — Джонатан Эдвардс, «Свобода воли»\n\n"
        "Цитаты Эдвардса — из книги **«Свобода воли»** (*Freedom of the Will*), Project Gutenberg: "
        "https://www.gutenberg.org\n",
        encoding="utf-8",
    )
    document = tmp_path / "article.json"
    document.write_text(
        json.dumps(
            {
                "schema_name": "video-channel-manager.rich-article-document",
                "document_id": "test",
                "blocks": [],
                "sources": [
                    {
                        "source_id": "src-01-edwards-will",
                        "label": "Джонатан Эдвардс, «Свобода воли», цитата 1",
                        "url": "https://ccel.org/ccel/edwards/will",
                        "evidence": (
                            f"EN: {first}  [смещение 0 в блоке EDW-REM (позиция 0; "
                            f"{len(first)} зн.), CCEL; перевод канала]"
                        ),
                    },
                    {"source_id": "src-02-scripture", "label": "Синодальный.", "evidence": "Ин. 8:34."},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    errors = sources_check(markdown, document, corpus, [f"OTHER:0:{len(first)}"])
    assert any("EDW-REM" in err and "не передан" in err for err in errors), errors


def test_scripture_check_ignores_stress_marks_of_digital_editions(tmp_path: Path) -> None:
    """Знаки ударения внутри слова (`Входи&#769;те`) не делают стих «несовпадающим»."""
    import re

    from lordchrist_scripture_check import check as scripture_check, load_corpus

    corpus = load_corpus(BIBLE_DIR)
    if not corpus:
        return
    # ударение должно стоять ВНУТРИ слова, перед буквой: иначе сущность
    # распадается на два слова и сверка ломается
    inside = re.compile(r"&#769;(?=[А-Яа-яЁё])|\u0301(?=[А-Яа-яЁё])")
    found = [
        (book, place, index)
        for book in corpus
        for place, text in corpus[book].items()
        for index, token in enumerate(text.split())
        if inside.search(token)
    ]
    if not found:
        return  # корпус без ударений — проверять нечего
    book, (chapter, verse), index = found[0]
    tokens = corpus[book][(chapter, verse)].split()
    fragment = " ".join(tokens[max(0, index - 1) : index + 4])
    fragment = fragment.replace("&#769;", "").replace("\u0301", "")
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТ**\n\nПисание говорит: **{fragment}** ({book}. {chapter}:{verse}).\n",
        encoding="utf-8",
    )
    errors, _notes = scripture_check(doc, corpus)
    assert not errors, errors
