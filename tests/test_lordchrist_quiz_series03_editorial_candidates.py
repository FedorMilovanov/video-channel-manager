"""Provider-inert editorial proposals for the eight pending Series 03 Telegram quizzes.

These are *not* a new release and cannot authorize publication. Historical
published items and the protected Telegram ledger must remain unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUIZ = ROOT / "content/telegram/lordchrist/quiz"
CANDIDATES = QUIZ / "SERIES_03_PENDING_EDITORIAL_CANDIDATES_20261117.json"
IMMUTABLE_RELEASE = QUIZ / "lordchrist-quiz-series-03-runtime.json"
BAD_READER_COPY = (
    "укрепить близкое к смерти",
    "общине с репутацией живой",
    "обращение веры",
    "назначили нового судью",
    "внешнее имя",
)


def test_pending_rewrites_are_source_bound_and_never_publication_approval() -> None:
    draft = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    release = json.loads(IMMUTABLE_RELEASE.read_text(encoding="utf-8"))
    assert draft["schema_name"] == "video-channel-manager.lordchrist-quiz-editorial-candidates"
    assert draft["origin_release_id"] == release["release_id"] == "lordchrist-quiz-series-03-v1"
    assert draft["project_key"] == release["project_key"] == "lord-god-strength"
    assert draft["channel_username"] == release["channel_username"] == "@lordchrist"
    assert draft["publication_authorized"] is False
    assert draft["release_authorized"] is False
    assert draft["review_status"] == "DRAFT_HOLD"
    assert draft["preserve_published"] == [item["publication_id"] for item in release["items"][:2]]
    assert len(draft["items"]) == len(release["items"][2:]) == 8
    assert [item["source_publication_id"] for item in draft["items"]] == [
        item["publication_id"] for item in release["items"][2:]
    ]
    for candidate, original in zip(draft["items"], release["items"][2:], strict=True):
        assert candidate["source_sha256"] == original["source_sha256"]
        assert candidate["review_status"] == "pending_independent_review"
        assert all(key not in candidate for key in ("scheduled_at", "provider_payload_sha256", "release_id"))
        assert candidate["source_url"].startswith("https://")
        assert len(candidate["editorial_findings"]) > 40
        assert 45 <= len(candidate["question"]) <= 300
        assert len(candidate["options"]) == 4
        assert len(set(option.casefold() for option in candidate["options"])) == 4
        assert all(0 < len(option) <= 100 for option in candidate["options"])
        assert 0 <= candidate["correct_option_index"] <= 3
        assert 100 <= len(candidate["explanation"]) <= 200
        assert any(
            x in candidate["explanation"]
            for x in ("Евр.", "1 Пар.", "Ин.", "Чис.", "Мк.", "Иак.", "Рим.")
        )
        assert candidate["editorial_metrics"] == {
            "question_characters": len(candidate["question"]),
            "explanation_characters": len(candidate["explanation"]),
            "options_characters": [len(x) for x in candidate["options"]],
        }
        reader_text = " ".join((candidate["question"], *candidate["options"], candidate["explanation"])).lower()
        assert not any(bad in reader_text for bad in BAD_READER_COPY)


def test_published_sardis_is_not_mutated_in_the_new_editorial_draft() -> None:
    draft = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    release = json.loads(IMMUTABLE_RELEASE.read_text(encoding="utf-8"))
    published = release["items"][1]["payload"]
    assert "укрепить близкое к смерти" in published["explanation"].lower()
    assert published["correct_option_ids"] == [2]
    assert "lordchrist-quiz-s03-sardis-vigil" not in {
        candidate["source_publication_id"] for candidate in draft["items"]
    }
