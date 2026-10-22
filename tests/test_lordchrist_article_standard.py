from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lordchrist_article_preflight import check  # noqa: E402
from render_l2_copy_page import render  # noqa: E402

SOURCE_NOTE = (
    "📖 Цитаты Чарнока — из книги «Беседы о существовании и атрибутах Бога»; "
    "текст по изданию 1853 года, оцифровка: Project Gutenberg, eBook #53527, "
    "https://www.gutenberg.org/ebooks/53527."
)


def test_render_sample_article_has_cite_and_no_legacy_attribution() -> None:
    sample_path = ROOT / "content/telegram/lordchrist/examples/ОБРАЗЕЦ-статья-L2.md"
    md = sample_path.read_text(encoding="utf-8")
    rich_html, _, _ = render(md)

    assert "<cite>" in rich_html
    assert rich_html.count("<cite>") >= 2
    assert "<br><i>— " not in rich_html


def test_preflight_numbered_section_with_emoji_fails(tmp_path: Path) -> None:
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n"
        "Лид статьи с подробным описанием контекста и вводных мыслей для читателей канала.\n\n"
        "## 🏛 1. Раздел\n\n"
        "Текст первого раздела статьи.\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert any("номера уже маркируют место" in err for err in rep.errors)


def test_preflight_short_named_section_with_emoji_fails(tmp_path: Path) -> None:
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n"
        "Лид статьи с подробным описанием контекста и вводных мыслей для читателей канала.\n\n"
        "## 🏛 Короткая рубрика\n\n"
        "Короткая вставка всего в одно предложение.\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert any("короткой рубрике" in err or "короче ~600" in err for err in rep.errors)


def test_preflight_full_named_section_with_emoji_succeeds(tmp_path: Path) -> None:
    lead = (
        "Лид статьи с подробным описанием контекста и вводных мыслей для читателей канала. "
        "Он вводит тему и обещает предметное богословское рассуждение."
    )
    p1 = (
        "Это первый полноценный абзац раздела, который подробно и основательно раскрывает главную мысль всей темы. "
        "В нём содержатся необходимые богословские и исторические основания для читателя, позволяющие понять контекст "
        "и проследить логику дальнейшего повествования без каких-либо пропусков или недосказанностей. "
        "Каждое предложение опирается на факты и развивает аргументацию последовательно."
    )
    p2 = (
        "Это второй полноценный абзац раздела, продолжающий начатое рассуждение и делающий ясный и доказательный вывод. "
        "Вся мысль выстроена последовательно и не распадается на короткие отдельные лозунги, а образует единый связный "
        "текст нормальной статьи, готовый к публикации в канале для внимательного чтения. "
        "Здесь формулируется завершённый богословский тезис."
    )
    assert len(p1 + "\n\n" + p2) >= 600

    doc = tmp_path / "article.md"
    doc.write_text(
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{lead}\n\n## 🏛 Именованный раздел\n\n{p1}\n\n{p2}\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert not rep.errors


def test_preflight_emoji_in_body_paragraph_is_error(tmp_path: Path) -> None:
    lead = (
        "Лид статьи с подробным описанием контекста и вводных мыслей для читателей канала. "
        "Он вводит тему и обещает предметное богословское рассуждение."
    )
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n"
        f"{lead}\n\n"
        "## Именованный раздел без маркера\n\n"
        "Обычный абзац текста, в который случайно попал эмодзи 🏛 прямо в середину текста. "
        "Такой эмодзи в теле абзаца запрещён правилами L2.\n\n"
        "Второй абзац текста продолжает рассуждение и развивает аргумент дальше без нарушений. "
        "Здесь нет никаких посторонних графических элементов.\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert any("эмодзи в обычном абзаце" in err for err in rep.errors)
    assert not any("эмодзи в обычном абзаце" in w for w in rep.warnings)


def test_preflight_article_without_emoji_has_no_emoji_errors(tmp_path: Path) -> None:
    lead = (
        "Лид статьи с подробным описанием контекста и вводных мыслей для читателей канала. "
        "Он вводит тему и обещает предметное богословское рассуждение."
    )
    doc = tmp_path / "article.md"
    doc.write_text(
        "# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n"
        f"{lead}\n\n"
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
        f"# ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ\n\n{LEAD}\n\n## Именованный раздел без маркера\n\n{body}\n\n"
        f"{quote}\n\n{SOURCE_NOTE}\n"
    )


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


def test_preflight_rejects_bold_and_italic_in_body(tmp_path: Path) -> None:
    doc = tmp_path / "article.md"
    doc.write_text(_article("Обычный абзац.", body=f"{BODY} И ещё **жирный акцент**."), encoding="utf-8")
    assert any("жирный шрифт" in err for err in check(doc).errors)

    doc.write_text(_article("Обычный абзац.", body=f"{BODY} И ещё *курсив*."), encoding="utf-8")
    assert any("курсив" in err for err in check(doc).errors)


def test_build_l2_rich_document_strips_markup_and_keeps_credit(tmp_path: Path) -> None:
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
        "# **ТЕСТ**\n\nАбзац с *курсивом* и **жирным**.\n\n> «Цитата»\n> *— Стивен Чарнок, «О бытии Бога»*\n\n"
        f"{SOURCE_NOTE}\n",
        encoding="utf-8",
    )

    built = build(md_path, doc_path)
    heading, paragraph, quote = built["blocks"][:3]
    assert heading["text"] == "ТЕСТ" and heading["size"] == 1
    assert paragraph["text"] == "Абзац с курсивом и жирным."
    assert quote["credit"] == "— Стивен Чарнок, «О бытии Бога»"
    assert quote["blocks"][0]["text"] == "«Цитата»"
    assert json.loads(doc_path.read_text(encoding="utf-8"))["blocks"] == built["blocks"]


def test_preflight_rejects_translation_note_under_quote(tmp_path: Path) -> None:
    quote = (
        "> «Точный текст цитаты, достаточно длинной для отдельного блока.»\n"
        "> — Стивен Чарнок, «О бытии Бога», перевод мой"
    )
    doc = tmp_path / "article.md"
    doc.write_text(_article(quote), encoding="utf-8")
    assert any("пометка о переводе" in err for err in check(doc).errors)


def test_preflight_rejects_italic_attribution(tmp_path: Path) -> None:
    quote = "> «Точный текст цитаты, достаточно длинной для отдельного блока.»\n> *— Стивен Чарнок, «О бытии Бога»*"
    doc = tmp_path / "article.md"
    doc.write_text(_article(quote), encoding="utf-8")
    rep = check(doc)
    assert any("нет подписи" in err for err in rep.errors)
    assert any("курсив" in err for err in rep.errors)


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


def test_render_keeps_connector_tight_to_its_quote() -> None:
    md = "# ТЕСТ\n\nАбзац перед связкой во всю строку, чтобы блок был не коротким.\n\nОб этом он говорит иначе:\n> «Цитата»\n> — Стивен Чарнок, «О бытии Бога»\n"
    rich_html, _, _ = render(md)
    assert "иначе:</p>\n<blockquote>" in rich_html


def test_preflight_rejects_second_emoji_in_the_source_note(tmp_path: Path) -> None:
    note = SOURCE_NOTE.replace("текст по изданию", "📚 текст по изданию")
    doc = tmp_path / "article.md"
    doc.write_text(
        f"# ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ\n\n{LEAD}\n\n## Именованный раздел без маркера\n\n{BODY}\n\n{note}\n",
        encoding="utf-8",
    )
    assert any("только один значок" in err for err in check(doc).errors)
