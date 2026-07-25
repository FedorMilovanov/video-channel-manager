from __future__ import annotations

from copy import deepcopy

import pytest

from video_channel_manager.editorial.article_sources import (
    parse_article_front_matter,
    validate_article_source_bundle,
    validate_article_source_ledger,
)


def _article() -> str:
    return '''---
title: "Статья"
slug: "article-slug"
status: "editorial-review"
youtube_video_id: "youtube-id"
vk_video_id: "-235216998_1"
keywords:
  - "ключ"
---

# Статья
'''


def _ledger() -> dict[str, object]:
    return {
        "schema_name": "video-manager.video-article-source-ledger",
        "schema_version": 1,
        "status": "editorial-review",
        "proposed_slug": "article-slug",
        "youtube_video_id": "youtube-id",
        "vk_video_id": "-235216998_1",
        "article_url": None,
        "claims": [
            {
                "claim_id": "claim-one",
                "claim": "Проверяемое утверждение.",
                "source_ids": ["primary-one"],
            }
        ],
        "sources": [
            {
                "source_id": "primary-one",
                "kind": "academic_primary_text_edition",
                "title": "Академический текст",
                "url": "https://example.org/source",
            }
        ],
        "editorial_rules": {
            "facts_require_claim_source_mapping": True,
            "interpretation_must_be_labeled": True,
            "automatic_literary_rewriting": False,
            "publish_only_after_human_review": True,
        },
    }


def test_article_source_bundle_is_valid() -> None:
    summary = validate_article_source_bundle(_article(), _ledger())

    assert summary["claims"] == 1
    assert summary["sources"] == 1
    assert summary["ledger_sha256"].startswith("sha256:")


def test_front_matter_parser_ignores_nested_keyword_items() -> None:
    parsed = parse_article_front_matter(_article())

    assert parsed["slug"] == "article-slug"
    assert parsed["youtube_video_id"] == "youtube-id"
    assert "ключ" not in parsed.values()


def test_ledger_rejects_unknown_source_id() -> None:
    ledger = _ledger()
    claims = ledger["claims"]
    assert isinstance(claims, list)
    claim = claims[0]
    assert isinstance(claim, dict)
    claim["source_ids"] = ["missing"]

    with pytest.raises(ValueError, match="unknown source IDs"):
        validate_article_source_ledger(ledger)


def test_ledger_requires_primary_or_author_note_source() -> None:
    ledger = _ledger()
    sources = ledger["sources"]
    assert isinstance(sources, list)
    source = sources[0]
    assert isinstance(source, dict)
    source["kind"] = "academic_secondary_research"

    with pytest.raises(ValueError, match="primary or author-note"):
        validate_article_source_ledger(ledger)


def test_ledger_rejects_automatic_literary_rewriting() -> None:
    ledger = _ledger()
    rules = ledger["editorial_rules"]
    assert isinstance(rules, dict)
    rules["automatic_literary_rewriting"] = True

    with pytest.raises(ValueError, match="must be false"):
        validate_article_source_ledger(ledger)


def test_bundle_rejects_video_identity_mismatch() -> None:
    ledger = deepcopy(_ledger())
    ledger["vk_video_id"] = "-235216998_2"

    with pytest.raises(ValueError, match="identity mismatch"):
        validate_article_source_bundle(_article(), ledger)
