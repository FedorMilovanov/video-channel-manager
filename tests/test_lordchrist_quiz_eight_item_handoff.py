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


def test_future_release_cannot_be_signed_without_independent_exact_item_reviews(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Structural signoff gate, not evidence of an actual human's approval."""
    from video_channel_manager import lordchrist_quiz as quiz

    raw = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    series = LordchristQuizSeriesSpec.model_validate(
        {**raw, "series_id": "lordchrist-quiz-series-04", "items": raw["items"][2:]}
    )
    monkeypatch.setattr(quiz, "QUIZ_DIR", tmp_path)
    with pytest.raises(ValueError, match="requires per-item independent editorial signoff"):
        quiz.require_future_series_editorial_signoff(series)
    requirements = (
        "scripture_context_checked",
        "russian_reader_checked",
        "single_correct_answer_checked",
        "three_distractors_checked",
        "post_vote_explanation_checked",
    )
    fake_review_fixture = {
        "series_id": series.series_id,
        "approval_state": "independent_human_approved",
        "items": [
            {
                "publication_id": item.publication_id,
                "source_sha256": quiz.spec_source_sha256(item),
                "status": "approved",
                "reviewer_type": "human",
                "prepared_by": "Fixture Author",
                "reviewed_by": "Fixture Reviewer",
                "review_url": "https://github.com/FedorMilovanov/video-channel-manager/pull/123#pullrequestreview-456",
                **{field: True for field in requirements},
            }
            for item in series.items
        ],
    }
    signoff_file = tmp_path / "lordchrist-quiz-series-04-editorial-signoff.json"
    signoff_file.write_text(json.dumps(fake_review_fixture, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance is not independently verified"):
        quiz.require_future_series_editorial_signoff(series)
    fake_review_fixture["items"][0]["source_sha256"] = "sha256:wrong"
    signoff_file.write_text(json.dumps(fake_review_fixture, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="missing exact independent evidence"):
        quiz.require_future_series_editorial_signoff(series)

    signoff_file.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        quiz.require_future_series_editorial_signoff(series)

    signoff_file.write_text(
        json.dumps({"series_id": series.series_id, "approval_state": "pending", "items": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wrong series, state or item count"):
        quiz.require_future_series_editorial_signoff(series)

    fake_review_fixture["items"][0] = None
    signoff_file.write_text(json.dumps(fake_review_fixture, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="item review must be an object"):
        quiz.require_future_series_editorial_signoff(series)
