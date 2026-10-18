from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lordchrist_article_preflight import check  # noqa: E402
from render_l2_copy_page import render  # noqa: E402


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
        "Текст первого раздела статьи.\n",
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
        "Короткая вставка всего в одно предложение.\n",
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
        f"# **ТЕСТОВАЯ СТАТЬЯ ДЛЯ ПРОВЕРКИ ПРАВИЛ**\n\n{lead}\n\n## 🏛 Именованный раздел\n\n{p1}\n\n{p2}\n",
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
        "Здесь нет никаких посторонних графических элементов.\n",
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
        "Никаких эмодзи или запрещённых символов здесь нет.\n",
        encoding="utf-8",
    )
    rep = check(doc)
    assert not any("эмодзи" in err.lower() for err in rep.errors)
