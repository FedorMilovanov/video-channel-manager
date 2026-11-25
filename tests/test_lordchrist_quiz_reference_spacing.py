"""Provider-inert typography contract for future @lordchrist native QUIZ drafts.

The sealed Series03 release and protected Telegram ledger are historical evidence
and MUST NOT be modified merely to reformat an already published message.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ_DIR = ROOT / "content/telegram/lordchrist/quiz"
CANDIDATES = QUIZ_DIR / "SERIES_03_PENDING_EDITORIAL_CANDIDATES_20261117.json"
HANDOFF = QUIZ_DIR / "SERIES_04_EIGHT_ITEM_EDITORIAL_HANDOFF_20261117.json"
REFERENCE = re.compile(r"(?:1 Пар|Евр|Чис|Мк|Иак|Рим)\. [^\n]+$", re.UNICODE)


def test_eight_pending_quiz_explanations_keep_scripture_on_separate_paragraph() -> None:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    assert data["publication_authorized"] is False
    assert data["release_authorized"] is False
    assert handoff["publication_authorized"] is False
    assert handoff["release_authorized"] is False
    assert len(data["items"]) == len(handoff["prepared_items"]) == 8
    handoff_by_id = {item["from"]: item for item in handoff["prepared_items"]}

    for item in data["items"]:
        explanation = item["explanation"]
        assert explanation.count("\n\n") == 1, item["source_publication_id"]
        body, reference = explanation.split("\n\n")
        assert body.endswith("."), item["source_publication_id"]
        assert REFERENCE.fullmatch(reference), item["source_publication_id"]
        assert not body.endswith(" "), item["source_publication_id"]
        assert 100 <= len(explanation) <= 200, item["source_publication_id"]
        assert item["editorial_metrics"]["explanation_characters"] == len(explanation)
        assert handoff_by_id[item["source_publication_id"]]["explanation_characters"] == len(explanation)

    raw = CANDIDATES.read_bytes()
    git_blob_sha = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()
    assert handoff["source_blob_sha"] == git_blob_sha
