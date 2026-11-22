"""Every Charnock Telegraph JSON must render back to its reviewed Markdown."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.charnock_article_render_md import iter_text, render_markdown

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock"
KEYS = ("01b", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13")
MAIN_ARTICLES = [ARTICLE_DIR / f"lordchrist-telegraph-charnock-{key}.json" for key in KEYS]


@pytest.mark.parametrize("article_path", MAIN_ARTICLES, ids=lambda path: path.stem.rsplit("-", 1)[-1])
def test_markdown_is_exactly_the_rendered_json(article_path: Path) -> None:
    article = json.loads(article_path.read_text(encoding="utf-8"))
    markdown_path = article_path.with_suffix(".md")
    markdown = markdown_path.read_text(encoding="utf-8")
    rendered = render_markdown(article)
    assert rendered.rstrip("\n") == markdown.rstrip("\n")


@pytest.mark.parametrize("article_path", MAIN_ARTICLES, ids=lambda path: path.stem.rsplit("-", 1)[-1])
def test_source_credit_is_part_of_the_telegraph_json_payload(article_path: Path) -> None:
    """A Markdown-only footer is invisible to the Telegraph JSON publisher."""
    article = json.loads(article_path.read_text(encoding="utf-8"))
    blocks = article["blocks"]
    assert blocks, article_path
    footer = blocks[-1]
    assert footer["type"] == "paragraph", article_path
    footer_text = iter_text(footer["text"])
    assert footer_text.startswith("© Цитаты Чарнока"), article_path
    assert "gutenberg.org/ebooks/53527" in footer_text, article_path
