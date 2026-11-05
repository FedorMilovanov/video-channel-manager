"""The v6 quote reader preview is source-bound but never a provider release."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from scripts.lordchrist_quote_v6_preview import (
    DEFAULT_OUTPUT,
    ROOT,
    V5_INDEX,
    V5_PREVIEW,
    make_reader_preview,
)

FILE = ROOT / DEFAULT_OUTPUT


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_preview_is_deterministic_and_matches_committed_data() -> None:
    actual = make_reader_preview(ROOT)
    frozen = _read(FILE)
    assert actual == frozen
    assert len(actual["posts"]) == 30
    assert len({p["publication_id"] for p in actual["posts"]}) == 30
    assert actual["read_only"] is True
    assert actual["new_release_digest"] is None
    assert actual["approved_new_queue"] is False
    assert actual["provider_write_authorization"] is False
    assert actual["rights_review_complete"] is False
    assert actual["full_bilingual_review_complete"] is False
    assert actual["responsible_editor_approval"] is False


def test_each_rendered_quote_keeps_exact_v5_wording_and_historical_anchors() -> None:
    original = _read(ROOT / V5_PREVIEW)["posts"]
    index = _read(ROOT / V5_INDEX)["entries"]
    frozen = _read(FILE)["posts"]
    for num, (before, record, post) in enumerate(zip(original, index, frozen, strict=True), 1):
        assert before["sequence"] == record["sequence"] == post["sequence"] == num
        assert before["publication_id"] == post["publication_id"]
        assert before["source"]["url"] == post["source_url"]
        assert before["source"]["anchor_start"] == post["source_anchor_start"]
        assert before["source"]["anchor_end"] == post["source_anchor_end"]
        assert post["quote_sha256"] == record["candidate_body_sha256"]
        assert post["rights_review_status"] == "pending"
        assert post["final_editor_approval"] is False
        assert post["provider_write_authorization"] is False
        assert 0 < post["visible_char_count"] <= 4096
        text = before["text"]
        quote = text.split("\n\n© ", 1)[0]
        assert _sha(quote[1:-1]) == post["quote_sha256"]
        escaped = html.escape(quote)
        assert post["reader_html_preview"].startswith(f"<blockquote>{escaped}</blockquote>\n")
        assert "<i>— " in post["reader_html_preview"]
        assert "© " not in post["reader_html_preview"]
        assert post["candidate_render_html_sha256"] == _sha(post["reader_html_preview"])


def test_editorial_context_never_enters_quote_entity_or_published_message() -> None:
    posts = {entry["sequence"]: entry for entry in _read(FILE)["posts"]}
    assert set(posts) == set(range(1, 31))
    assert posts[8]["research_notes_excluded_from_reader_message"]
    assert posts[21]["research_notes_excluded_from_reader_message"]
    assert all(not x["research_notes_excluded_from_reader_message"] for num, x in posts.items() if num not in (8, 21))
    for post in posts.values():
        content = post["reader_html_preview"]
        assert "Контекст:" not in content
        assert "Примечание редакции:" not in content
        assert content.count("<blockquote>") == content.count("</blockquote>") == 1
        assert content.count("<i>") == content.count("</i>") == 1
    assert posts[20]["quoted_paragraph_count"] == 4


def test_v6_is_never_promoted_to_an_executable_queue_by_its_build_step() -> None:
    artifact = _read(FILE)
    assert artifact["schema_name"] != "video-channel-manager.telegram-quote-queue"
    assert "new_release_digest" in artifact and artifact["new_release_digest"] is None
    assert "release_id" not in artifact
    assert "activation" not in artifact
    assert all(post["provider_write_authorization"] is False for post in artifact["posts"])
