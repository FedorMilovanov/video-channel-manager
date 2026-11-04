from __future__ import annotations

import json
import sys
from pathlib import Path

from video_channel_manager.telegram_rich_models import RichArticleDocument

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_lordchrist_telegraph_history_article import build_document  # noqa: E402

ARTICLE_DIR = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock"
MARKDOWN_PATH = ARTICLE_DIR / "lordchrist-telegraph-charnock-history-02.md"
SPEC_PATH = ARTICLE_DIR / "lordchrist-telegraph-charnock-history-02.quotes.json"
DOCUMENT_PATH = ARTICLE_DIR / "lordchrist-telegraph-charnock-history-02.json"


def test_history_article_document_is_reproducible_and_carries_quote_evidence() -> None:
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    built = build_document(markdown, spec)
    checked = json.loads(DOCUMENT_PATH.read_text(encoding="utf-8"))

    assert built == checked
    article = RichArticleDocument.model_validate(built)
    assert article.document_id == "lordchrist-telegraph-charnock-history-02"
    assert len([block for block in article.blocks if block.type == "blockquote"]) == 6
    assert len([block for block in article.blocks if block.type == "media"]) == 4
    assert sum(1 for block in article.blocks if block.type == "heading" and block.size == 1) == 1

    evidence = {source.url: source.evidence for source in article.sources}
    assert len(spec["quote_anchors"]) == 6
    for anchor in spec["quote_anchors"]:
        source_evidence = evidence[anchor["source_url"]]
        assert anchor["exact_anchor"] in source_evidence
        assert anchor["translation_status"] in source_evidence
