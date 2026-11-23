"""Every Charnock Telegraph JSON must render back to its reviewed Markdown."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.charnock_article_render_md import iter_text, render_markdown

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock"
CANDIDATE_DIR = ROOT / "content/research/charnock-source-credit-candidates-20261123"
KEYS = ("01b", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13")
LEGACY_WITH_MISSING_LIVE_CREDIT = {
    "11": "d42392bb593de4f89d36a12a3548f459efe41090",
    "12": "e7ea215bcea907747363f41dc0bc4443f58269a8",
    "13": "eedc00889bb2e907bbcc91de914d8ddf68f1737c",
}


def approved_article_path(key: str) -> Path:
    return ARTICLE_DIR / f"lordchrist-telegraph-charnock-{key}.json"


def reviewed_article_path(key: str) -> Path:
    if key in LEGACY_WITH_MISSING_LIVE_CREDIT:
        return CANDIDATE_DIR / f"charnock-{key}.json"
    return approved_article_path(key)


@pytest.mark.parametrize("key", KEYS)
def test_reviewed_markdown_is_exactly_the_rendered_json(key: str) -> None:
    """All 13 reviewed forms match; 11–13 are separate, unreleased candidates."""
    document = json.loads(reviewed_article_path(key).read_text(encoding="utf-8"))
    markdown = approved_article_path(key).with_suffix(".md").read_text(encoding="utf-8")
    assert render_markdown(document).rstrip("\n") == markdown.rstrip("\n")


@pytest.mark.parametrize("key", KEYS)
def test_source_credit_is_part_of_the_reviewed_json(key: str) -> None:
    document = json.loads(reviewed_article_path(key).read_text(encoding="utf-8"))
    footer = document["blocks"][-1]
    assert footer["type"] == "paragraph", key
    footer_text = iter_text(footer["text"])
    assert footer_text.startswith("© Цитаты Чарнока"), key
    assert "gutenberg.org/ebooks/53527" in footer_text, key


@pytest.mark.parametrize("key,blob_sha", LEGACY_WITH_MISSING_LIVE_CREDIT.items())
def test_legacy_live_source_is_unchanged_and_not_mistaken_for_candidate(key: str, blob_sha: str) -> None:
    """Do not rewrite immutable Telegram source IDs to paper over live defects."""
    approved_path = approved_article_path(key)
    raw = approved_path.read_bytes()
    actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    assert actual_blob == blob_sha
    approved = json.loads(raw)
    candidate = json.loads(reviewed_article_path(key).read_text(encoding="utf-8"))
    # Only editorial metadata and the final source-credit block differ.
    assert len(candidate["blocks"]) == len(approved["blocks"]) + 1
    assert candidate["blocks"][:-1] == approved["blocks"]
    for field in ("document_id", "sources", "media", "media_slots", "project_key"):
        assert candidate[field] == approved[field]
    assert candidate["revision"].endswith("-source-credit-candidate-20261123")
    assert not iter_text(approved["blocks"][-1].get("text", "")).startswith("©")
    assert iter_text(candidate["blocks"][-1]["text"]).startswith("©")
    # The canonical reviewed MD documents the desired credit but never authorizes
    # a new source blob, protected queue update, Telegraph edit, or Telegram send.
    reviewed_markdown = approved_path.with_suffix(".md").read_text(encoding="utf-8")
    assert render_markdown(approved).rstrip("\n") != reviewed_markdown.rstrip("\n")


def test_markdown_footer_fallback_is_rejected() -> None:
    incomplete = {"blocks": [{"type": "paragraph", "block_id": "p-1", "text": "Body"}]}
    with pytest.raises(ValueError, match="source credit must be authored in JSON blocks"):
        render_markdown(incomplete, footer="© Citation that exists only in Markdown")
