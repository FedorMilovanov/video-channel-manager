"""History-01: pending editorial correction must not impersonate a live receipt."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock/lordchrist-telegraph-charnock-history-01.json"
MARKDOWN = ARTICLE.with_suffix(".md")
QUEUE = ROOT / "content/telegram/lordchrist/telegraph-v1/article-queue.json"
REPLACEMENTS = ROOT / "docs/audits/2026-11-04-charnock-publication-link-replacement-map.json"
PUBLICATION_ID = "lordchrist-telegraph-charnock-history-01"


def test_birth_claim_source_is_attributed_and_year_approximate() -> None:
    article = json.loads(ARTICLE.read_text(encoding="utf-8"))
    blocks = {block["block_id"]: block for block in article["blocks"]}
    intro = blocks["p-2"]["text"][0]
    paragraph = blocks["p-4"]["text"][0]
    assert "(ок. 1628–1680)" in intro
    assert "Энтони Вуд" in paragraph and "1691" in paragraph
    assert "приблизительной датой" in paragraph
    assert "запись о рождении или крещении пока не установлена" in paragraph
    assert "Чарнок родился в Лондоне в 1628 году" not in paragraph
    markdown = MARKDOWN.read_text(encoding="utf-8")
    assert "(ок. 1628–1680)" in markdown
    assert paragraph in markdown


def test_historical_public_receipt_is_not_transferred_to_pending_revision() -> None:
    raw = ARTICLE.read_bytes()
    current_blob = hashlib.sha1(f"blob {len(raw)}".encode() + bytes([0]) + raw).hexdigest()
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    item = next(row for row in queue["items"] if row["publication_id"] == PUBLICATION_ID)
    assert item["article"]["git_blob_sha"] == current_blob
    registry = json.loads(REPLACEMENTS.read_text(encoding="utf-8"))
    witness = next(row for row in registry["targets"] if row["publication_id"] == PUBLICATION_ID)
    assert witness["corrected_document_git_blob_sha"] == current_blob
    assert witness["previous_publicly_verified_document_git_blob_sha"] != current_blob
    assert witness["previous_publicly_verified_document_git_blob_sha"] == "a288b15d403fe2e261c1409c1f424a66c5d82548"
    assert witness["provider_writes_authorized"] is False
    assert witness["editorial_revision_status"] == "verified_in_place"  # Historical 15 Nov evidence only
    assert witness["pending_editorial_change"].startswith("2026-11-17:")
    assert "SOURCE ONLY" in witness["pending_editorial_change"]
    assert witness["replacement_telegraph_url"].endswith("izdanie-11-05")
