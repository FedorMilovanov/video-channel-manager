"""Proposed replacement quotations are evidence-bound, not production releases."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "docs/audits/2026-11-04-lordchrist-contiguous-quote-redrafts.json"
QUEUE = ROOT / "content/telegram/lordchrist/verified-30-posts.json"


def test_five_redrafts_bind_the_same_signed_quote_queue_and_remain_inert() -> None:
    source = QUEUE.read_text(encoding="utf-8")
    posts = json.loads(source)["posts"]
    packet = json.loads(DRAFTS.read_text(encoding="utf-8"))
    assert packet["schema_name"] == "video-channel-manager.lordchrist-v5-source-grounded-quote-redrafts"
    assert packet["schema_version"] == 1
    assert packet["source_queue_sha256"] == "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert packet["release_id"] is None
    assert packet["release_digest"] is None
    assert packet["editorial_approval"] is False
    assert packet["provider_write_authorization"] is False

    drafts = packet["drafts"]
    assert [d["sequence"] for d in drafts] == [12, 15, 18, 19, 22]
    for candidate in drafts:
        source_post = posts[candidate["sequence"] - 1]
        assert candidate["previous_publication_id"] == source_post["publication_id"]
        assert (
            candidate["previous_text_sha256"]
            == "sha256:" + hashlib.sha256(source_post["text"].encode("utf-8")).hexdigest()
        )
        assert (
            candidate["draft_text_sha256"]
            == "sha256:" + hashlib.sha256(candidate["translation_ru"].encode("utf-8")).hexdigest()
        )
        assert candidate["draft_word_count_ru"] == len(re.findall(r"\w+", candidate["translation_ru"]))
        assert candidate["draft_paragraph_count"] == len(candidate["translation_ru"].split("\n\n"))
        assert 100 <= candidate["draft_word_count_ru"] <= 240
        assert "\u2026" not in candidate["translation_ru"]
        assert candidate["release_authorized"] is False
        assert candidate["editorial_status"] == "draft_not_approved"
        assert candidate["source_probe"]["status"] == 200
        assert candidate["source_probe"]["both_anchor_exact_matches"] is True
        assert candidate["source_probe"]["semantic_translation_certified"] is False
        assert candidate["source_probe"]["english_span_words"] > 100
        assert candidate["anchor_start"] and candidate["anchor_end"]
        assert candidate["author_ru"] and candidate["source_url"].startswith("https://")


def test_quote_drafts_do_not_reenable_the_current_live_queue() -> None:
    packet = json.loads(DRAFTS.read_text(encoding="utf-8"))
    for candidate in packet["drafts"]:
        assert candidate["previous_text_sha256"] != candidate["draft_text_sha256"]
        assert "published" not in candidate["editorial_status"]
        assert candidate["source_probe"]["semantic_translation_certified"] is False
