from __future__ import annotations

import json
import sys
from pathlib import Path

from video_channel_manager.telegram_rich_models import RichArticleDocument

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_lordchrist_telegraph_history_article import build_document  # noqa: E402

ARTICLE_DIR = ROOT / "content/telegram/lordchrist/telegraph-v1/history"
MARKDOWN_PATH = ARTICLE_DIR / "lordchrist-reformation-polished-draft.md"
SPEC_PATH = ARTICLE_DIR / "lordchrist-reformation-polished-draft.spec.json"
DOCUMENT_PATH = ARTICLE_DIR / "lordchrist-reformation-polished-draft.json"


def test_polished_reformation_article_is_reproducible_and_preserves_structure() -> None:
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    built = build_document(markdown, spec)
    checked = json.loads(DOCUMENT_PATH.read_text(encoding="utf-8"))

    assert built == checked
    article = RichArticleDocument.model_validate(built)
    assert article.document_id == "lordchrist-telegraph-history-reformation-1517-01"
    assert article.metadata.title == "РЕФОРМАЦИЯ: ЕВАНГЕЛИЕ, ПИСАНИЕ И СПОРЫ XVI ВЕКА"
    assert sum(block.type == "blockquote" for block in article.blocks) == 6
    assert sum(block.type == "media" for block in article.blocks) == 4
    assert sum(block.type == "heading" and block.size == 1 for block in article.blocks) == 1
    assert sum(block.type == "heading" and block.size == 3 for block in article.blocks) == 9

    # The cover is provided by the publisher's cover field, not duplicated as
    # an inline photo block; all four historical photos remain in article flow.
    assert spec["cover_uri"] not in {media.uri for media in article.media}
    assert len(article.media) == 4

    evidence = {source.url: source.evidence or "" for source in article.sources}
    assert len(spec["quote_anchors"]) == 6
    for anchor in spec["quote_anchors"]:
        recorded_anchor = anchor.get("exact_anchor") or anchor.get("source_locator")
        assert recorded_anchor in evidence[anchor["source_url"]]
        assert anchor["translation_status"] in evidence[anchor["source_url"]]

    assert "молотком" in markdown
    assert "Мари Дентьер" in markdown
    assert "анабаптист" in markdown
    assert "Тридентский собор" in markdown
