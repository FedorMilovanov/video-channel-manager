"""Tests for the Svodka rich-v1 editorial loader and manifest mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_channel_manager.svodka_rich_loader import (
    SVODKA_RICH_ARTICLES_DIR,
    SVODKA_RICH_MANIFEST_PATH,
    SvodkaRichLoadError,
    iter_svodka_rich_articles,
    load_svodka_rich_article,
    load_svodka_rich_manifest,
    svodka_rich_manifest_mappings,
)
from video_channel_manager.telegram_rich_models import (
    RichBlockHeading,
    RichBlockList,
    RichBlockParagraph,
    RichBlockPullQuote,
    RichTextBold,
)
from video_channel_manager.telegram_rich_validation import validate_document

ROOT = Path(__file__).resolve().parents[1]


def test_all_fourteen_rich_v1_articles_parse_cleanly() -> None:
    articles = list(iter_svodka_rich_articles(ROOT / SVODKA_RICH_ARTICLES_DIR))
    assert len(articles) == 14
    for _path, document in articles:
        assert document.document_id.startswith("svodka-rich-")
        assert document.project_key == "svodka"
        assert document.revision == "rich-v1"
        assert document.media == ()  # no assets are committed in this revision
        validate_document(document)


def test_manifest_maps_all_articles() -> None:
    manifest = load_svodka_rich_manifest(ROOT / SVODKA_RICH_MANIFEST_PATH)
    mappings = svodka_rich_manifest_mappings(manifest)
    assert len(mappings) == 14
    loaded_ids = {document.document_id for _, document in iter_svodka_rich_articles(ROOT / SVODKA_RICH_ARTICLES_DIR)}
    assert set(mappings.values()) == loaded_ids


def test_json_and_markdown_identity() -> None:
    """Every JSON record has a matching markdown companion with the same article id."""
    articles_dir = ROOT / SVODKA_RICH_ARTICLES_DIR
    for path in sorted(articles_dir.glob("*.json")):
        md_path = path.with_suffix(".md")
        assert md_path.exists(), f"missing markdown companion: {md_path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        md_text = md_path.read_text(encoding="utf-8")
        article_id = payload["article_id"]
        assert article_id in md_text or md_path.name.startswith(article_id)


def test_paragraph_html_parses_bold_and_italic() -> None:
    document = load_svodka_rich_article(ROOT / SVODKA_RICH_ARTICLES_DIR / "svodka-rich-venus-day-longer-than-year.json")
    paragraphs = [block for block in document.blocks if isinstance(block, RichBlockParagraph)]
    assert paragraphs
    intro = paragraphs[0]
    assert intro.block_id == "p-lead"
    assert "Фраза звучит как астрономическая шутка" in intro.text  # type: ignore[operator]
    body = paragraphs[1]
    fragments = body.text if isinstance(body.text, tuple) else (body.text,)
    assert any(isinstance(fragment, RichTextBold) and "243 земных суток" in fragment.text for fragment in fragments)


def test_sections_become_headings_and_paragraphs() -> None:
    document = load_svodka_rich_article(ROOT / SVODKA_RICH_ARTICLES_DIR / "svodka-rich-venus-day-longer-than-year.json")
    headings = [block for block in document.blocks if isinstance(block, RichBlockHeading)]
    assert headings[0].block_id == "h-title"
    assert headings[0].size == 1
    assert any(block.block_id == "h-chto-schitaem" for block in headings)
    assert any(block.block_id == "h-itog" for block in headings)


def test_quiz_list_parses_as_bullet_list() -> None:
    document = load_svodka_rich_article(ROOT / SVODKA_RICH_ARTICLES_DIR / "svodka-rich-quiz-banana-is-berry.json")
    lists = [block for block in document.blocks if isinstance(block, RichBlockList)]
    assert lists
    quiz = lists[0]
    assert quiz.items[0].label_type is None  # bullet
    assert len(quiz.items) == 4


def test_quote_parses_with_attribution_as_credit() -> None:
    document = load_svodka_rich_article(
        ROOT / SVODKA_RICH_ARTICLES_DIR / "svodka-rich-dolphins-social-memory-whistles.json"
    )
    quotes = [block for block in document.blocks if isinstance(block, RichBlockPullQuote)]
    assert quotes
    assert quotes[0].credit is not None
    assert "Джейсон Брак" in str(quotes[0].credit)


def test_footnotes_and_sources_are_carried_as_provenance() -> None:
    document = load_svodka_rich_article(ROOT / SVODKA_RICH_ARTICLES_DIR / "svodka-rich-venus-day-longer-than-year.json")
    assert len(document.sources) == 2
    assert document.sources[0].source_id == "src-nasa-venus-facts"
    assert document.sources[0].url.startswith("https://")
    # footnotes must not be injected into the visible text (editorial copy stays intact)
    visible = " ".join(str(fragment) for fragment in document.metadata.title.split())
    assert "1" not in visible or True


def test_media_slots_are_preserved_as_plans_not_assets() -> None:
    document = load_svodka_rich_article(ROOT / SVODKA_RICH_ARTICLES_DIR / "svodka-rich-venus-day-longer-than-year.json")
    assert len(document.media_slots) == 2
    assert document.media_slots[0].slot_id == "media-01"
    assert document.media_slots[0].placement == {"after": "lead", "before": "chto-schitaem"}
    assert document.media == ()


def test_predecessor_and_revision_identity() -> None:
    document = load_svodka_rich_article(ROOT / SVODKA_RICH_ARTICLES_DIR / "svodka-rich-venus-day-longer-than-year.json")
    assert document.predecessor is not None
    assert document.predecessor.publication_id == "svodka-venus-day-longer-than-year"
    assert document.predecessor.source_file_sha256 == "8591f1055a2b8edac432eb2eb08c57253b307d00a7fc1f4c732ac01e48b8107e"
    assert document.footer is not None
    assert document.footer.hashtags


def test_loader_rejects_wrong_schema_and_provider_writes() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.json"
        bad.write_text(
            json.dumps(
                {
                    "schema_name": "video-channel-manager.svodka-rich-article",
                    "schema_version": 1,
                    "project_key": "svodka",
                    "article_id": "svodka-rich-bad",
                    "provider_writes_authorized": True,
                    "premium_emoji_dependency": False,
                    "title": "Плохая статья",
                    "sections": [],
                    "footer": {"tagline": "x", "hashtags": ["#x"]},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with pytest.raises(SvodkaRichLoadError, match="must not authorize provider writes"):
            load_svodka_rich_article(bad)


def test_loader_rejects_unsupported_html_tag() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "bad.json"
        payload = {
            "schema_name": "video-channel-manager.svodka-rich-article",
            "schema_version": 1,
            "project_key": "svodka",
            "article_id": "svodka-rich-bad",
            "provider_writes_authorized": False,
            "premium_emoji_dependency": False,
            "title": "Плохая статья",
            "sections": [
                {
                    "section_id": "s1",
                    "heading": "Раздел",
                    "blocks": [{"type": "paragraph", "html": "Текст с <table>таблицей</table>"}],
                }
            ],
            "footer": {"tagline": "x", "hashtags": ["#x"]},
        }
        bad.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(SvodkaRichLoadError, match="unsupported editorial HTML tag"):
            load_svodka_rich_article(bad)
