"""Provider-inert constraints for the eight-item editorial handoff.

These tests verify only source identity, non-execution and the series size;
they do NOT certify Russian prose or Bible interpretation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_channel_manager.lordchrist_quiz import LordchristQuizSeriesSpec

ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / "content/telegram/lordchrist/quiz"
BUNDLE = QUIZ / "SERIES_03_PENDING_EDITORIAL_CANDIDATES_20261117.json"
HANDOFF = QUIZ / "SERIES_04_EIGHT_ITEM_EDITORIAL_HANDOFF_20261117.json"
ORIGINAL = QUIZ / "lordchrist-quiz-series-03.json"


def test_editorial_handoff_is_source_pinned_and_non_executable() -> None:
    raw = BUNDLE.read_bytes()
    git_blob_sha = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    draft = json.loads(raw)
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    assert handoff["source_blob_sha"] == git_blob_sha
    assert handoff["independent_human_signoff"] == "not_obtained"
    assert handoff["publication_authorized"] is False
    assert handoff["release_authorized"] is False
    assert draft["publication_authorized"] is False
    assert draft["release_authorized"] is False
    assert draft["review_status"] == "DRAFT_HOLD"
    assert len(draft["items"]) == len(handoff["prepared_items"]) == 8
    for candidate, tracked in zip(draft["items"], handoff["prepared_items"], strict=True):
        assert tracked["from"] == candidate["source_publication_id"]
        assert tracked["to"] == tracked["from"].replace("-s03-", "-s04-")
        assert tracked["reference"] == candidate["exegesis_notes"]["source_passage"]
        assert candidate["review_status"] == "pending_independent_review"
        assert candidate["exegesis_notes"]["editorial_decision"] == "ACCEPT_FOR_HUMAN_SIGNOFF_ONLY"
        assert 100 <= len(candidate["explanation"]) <= 200


def test_eight_item_series_schema_can_be_reviewed_without_padding_or_provider_writes() -> None:
    historical = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    draft = {**historical, "series_id": "lordchrist-quiz-series-04", "items": historical["items"][2:]}
    model = LordchristQuizSeriesSpec.model_validate(draft)
    assert len(model.items) == 8
    assert len(LordchristQuizSeriesSpec.model_validate(historical).items) == 10
    with pytest.raises(ValidationError):
        LordchristQuizSeriesSpec.model_validate({**draft, "items": draft["items"][:7]})
