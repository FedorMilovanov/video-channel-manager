"""Verified primary/translation chapter links for the Charnock Telegraph cycle.

These references are chapter-specific, not generic Bible-repository landing
pages. Each URL was opened against the live Synodal text on 2026-11-04.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "content/telegram/lordchrist/telegraph-v1/charnock"
QUEUE = ROOT / "content/telegram/lordchrist/telegraph-v1/article-queue.json"

# publication suffix: (book id on bible.by, chapter, exact verse)
EXPECTED_EPIGRAPHS: dict[str, tuple[int, int, int]] = {
    "01b": (65, 11, 6),  # Hebrews 11:6
    "02": (39, 1, 11),  # Malachi 1:11, NOT Haggai 1
    "03": (52, 10, 17),  # Romans 10:17, NOT Hebrews 10
    "04": (52, 1, 20),
    "05": (19, 99, 3),
    "06": (19, 103, 24),
    "07": (19, 93, 9),
    "08": (19, 103, 27),
    "09": (19, 138, 14),
    "10": (52, 2, 15),
    "11": (19, 9, 17),
    "12": (61, 6, 16),
    "13": (23, 43, 12),
    "history-01": (19, 89, 3),  # Synodal 89:3; KJV Psalm 90:2
}


def test_all_fourteen_epigraph_links_identify_the_exact_synodal_book_and_chapter() -> None:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    items = {item["publication_id"]: item for item in queue["items"]}
    assert len(EXPECTED_EPIGRAPHS) == 14
    for suffix, (book_id, chapter, verse) in EXPECTED_EPIGRAPHS.items():
        publication_id = f"lordchrist-telegraph-charnock-{suffix}"
        item = items[publication_id]
        path = ROOT / item["article"]["path"]
        assert path.name == f"lordchrist-telegraph-charnock-{suffix}.json"
        raw = path.read_bytes()
        git_blob = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
        assert item["article"]["git_blob_sha"] == git_blob, publication_id

        document = json.loads(raw)
        source = document["sources"][0]
        assert source["source_id"].startswith("src-01-")
        assert source["url"] == f"https://bible.by/syn/{book_id}/{chapter}/", publication_id
        assert f"{chapter}:{verse}" in source["label"], publication_id
        assert source["verified_on"] >= "2026-11-04"
        assert "Синодальн" in source["evidence"]


def test_historical_epigraph_credit_and_rebuild_spec_use_psalm_89_3() -> None:
    stem = "lordchrist-telegraph-charnock-history-01"
    markdown = (BASE / f"{stem}.md").read_text(encoding="utf-8")
    document = json.loads((BASE / f"{stem}.json").read_text(encoding="utf-8"))
    spec = json.loads((BASE / f"{stem}.quotes.json").read_text(encoding="utf-8"))

    assert "> — Пс. 89:3" in markdown
    assert "> — Пс. 89:2" not in markdown
    assert document["blocks"][1]["credit"] == "— Пс. 89:3"
    assert spec["epigraph_source"] == document["sources"][0]
    assert spec["scripture_source"]["evidence"].startswith("Пс. 89:3;")
    assert document["sources"][0]["url"] == "https://bible.by/syn/19/89/"
