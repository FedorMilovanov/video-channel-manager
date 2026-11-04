"""Provider-inert regression proof for both QUIZ release/state/CLI control planes.

These tests use already reviewed fixtures and temporary local ledgers only.
No bot, network, workflow dispatch, or publication attempt is performed.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from video_channel_manager import lordchrist_quiz as quiz
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

ONE = "lordchrist-quiz-city-of-palms"
SERIES = "lordchrist-quiz-series-02"


def _profile_binding():
    profile = load_channel_profile(quiz.PROFILE_PATH)
    return profile, load_target_binding(quiz.BINDING_PATH, profile)


def test_series_and_trial_accept_exact_reviewed_release_without_provider_call() -> None:
    series = quiz.validate_series(SERIES, require_release_authorized=True, require_execution_authorized=True)
    assert series["series_id"] == SERIES
    assert series["items"] == 10
    assert series["release_authorized"] is True

    single = quiz.validate_quiz(ONE, require_release_authorized=True, require_execution_authorized=True)
    assert single["publication_id"] == ONE
    assert single["payload_kind"] == "quiz"
    assert single["release_authorized"] is True


def test_series_state_init_is_local_idempotent_and_checked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not initialized"):
        quiz.series_state_check(SERIES, tmp_path)

    path = quiz.series_state_init(SERIES, tmp_path)
    assert path.is_file()
    before = path.read_bytes()
    assert quiz.series_state_check(SERIES, tmp_path) == {"pending": 10}
    assert quiz.series_state_init(SERIES, tmp_path) == path
    assert path.read_bytes() == before

    data = json.loads(path.read_text("utf-8"))
    data["release_digest"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        quiz.series_state_check(SERIES, tmp_path)
    with pytest.raises(ValueError):
        quiz.series_state_init(SERIES, tmp_path)


def test_quiz_spec_validator_rejects_ambiguous_and_unsafe_specs() -> None:
    raw = json.loads(quiz.spec_path(ONE).read_text("utf-8"))
    bad = [
        ({"scheduled_at": "2026-11-04T13:00:00"}, "timezone-aware"),
        ({"correct_option_index": len(raw["options"])}, "outside the options"),
        ({"options": [raw["options"][0], raw["options"][0]]}, "unique"),
        ({"options": [" ", "Неверно"]}, "visible characters"),
        ({"hashtags": ""}, "require hashtags"),
        ({"scripture_references": [""]}, "non-empty"),
    ]
    for patch, expected in bad:
        with pytest.raises(ValidationError, match=expected):
            quiz.LordchristQuizSpec.model_validate({**raw, **patch})

    v2 = json.loads(quiz.spec_path("lordchrist-quiz-book-without-gods-name").read_text("utf-8"))
    with pytest.raises(ValidationError, match="post-vote explanation"):
        quiz.LordchristQuizSpec.model_validate({**v2, "explanation": "Без подтверждающей ссылки."})


def test_series_spec_rejects_duplicates_wrong_layout_and_wrong_cadence() -> None:
    series = json.loads(quiz.series_spec_path(SERIES).read_text("utf-8"))
    cases = [
        (1, "publication_id", series["items"][0]["publication_id"], "unique"),
        (1, "layout", "v1", "clean layout v2"),
        (
            1,
            "scheduled_at",
            (datetime.fromisoformat(series["items"][0]["scheduled_at"]) + timedelta(days=3)).isoformat(),
            "two days apart",
        ),
    ]
    for i, field, value, expected in cases:
        candidate = json.loads(json.dumps(series))
        candidate["items"][i][field] = value
        if field == "layout":
            candidate["items"][i]["hashtags"] = "#Библия"  # valid v1 item; invalid v2-only series
        with pytest.raises(ValidationError, match=expected):
            quiz.LordchristQuizSeriesSpec.model_validate(candidate)


def test_loaders_fail_closed_on_missing_or_malformed_inputs(tmp_path: Path) -> None:
    absent = tmp_path / "absent.json"
    for loader in (quiz.load_quiz_spec, quiz.load_quiz_series, quiz.load_quiz_release):
        with pytest.raises(ValueError, match="invalid lordchrist quiz"):
            loader(absent)
    absent.write_text("{not-json", encoding="utf-8")
    for loader in (quiz.load_quiz_spec, quiz.load_quiz_series, quiz.load_quiz_release):
        with pytest.raises(ValueError, match="invalid lordchrist quiz"):
            loader(absent)


def test_both_candidate_builders_reject_wrong_target_identity() -> None:
    profile, binding = _profile_binding()
    bad = binding.model_copy(update={"project_key": "not-this-project"})
    single = quiz.load_quiz_spec(quiz.spec_path(ONE))
    series = quiz.load_quiz_series(quiz.series_spec_path(SERIES))
    with pytest.raises(ValueError, match="differs"):
        quiz.build_quiz_candidate(profile, single, bad)
    with pytest.raises(ValueError, match="differs"):
        quiz.build_series_candidate(profile, series, bad)

    bad_channel = binding.model_copy(update={"channel_username": "@different"})
    with pytest.raises(ValueError, match="channel differs"):
        quiz.build_quiz_candidate(profile, single, bad_channel)
    with pytest.raises(ValueError, match="channel differs"):
        quiz.build_series_candidate(profile, series, bad_channel)


def test_series_runtime_mismatch_fails_before_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    series, release = quiz._load_series_bundle(SERIES)
    tampered = release.model_copy(update={"items": release.items[:-1]})
    monkeypatch.setattr(quiz, "_load_series_bundle", lambda _id: (series, tampered))
    with pytest.raises(ValueError, match="item count differs"):
        quiz.validate_series(SERIES, require_execution_authorized=True)


def test_one_off_published_receipt_blocks_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = quiz.state_init(ONE, tmp_path)
    assert path.exists()
    monkeypatch.setattr(
        quiz,
        "load_ledger",
        lambda _path, _release: SimpleNamespace(entries={ONE: SimpleNamespace(state="published")}),
    )
    with pytest.raises(ValueError, match="replay is forbidden"):
        quiz.state_check(ONE, tmp_path, require_publishable=True)


def test_local_cli_commands_prove_release_and_state_without_sending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stamp = "2026-11-04T16:00:00+03:00"
    single_output = tmp_path / "one.json"
    series_output = tmp_path / "series.json"
    assert quiz.main(["validate", "--publication-id", ONE, "--require-release-authorized"]) == 0
    assert quiz.main(["validate-series", "--series-id", SERIES, "--require-release-authorized"]) == 0

    assert (
        quiz.main(
            [
                "build-runtime",
                "--publication-id",
                ONE,
                "--reviewed-by",
                "regression-test",
                "--reviewed-at",
                stamp,
                "--output",
                str(single_output),
            ]
        )
        == 0
    )
    assert (
        quiz.main(
            [
                "build-series-runtime",
                "--series-id",
                SERIES,
                "--reviewed-by",
                "regression-test",
                "--reviewed-at",
                stamp,
                "--output",
                str(series_output),
            ]
        )
        == 0
    )
    assert single_output.is_file() and series_output.is_file()
    assert quiz.main(["state-init", "--publication-id", ONE, "--state-checkout", str(tmp_path)]) == 0
    assert (
        quiz.main(["state-check", "--publication-id", ONE, "--state-checkout", str(tmp_path), "--require-publishable"])
        == 0
    )
    assert quiz.main(["series-state-init", "--series-id", SERIES, "--state-checkout", str(tmp_path)]) == 0
    assert quiz.main(["series-state-check", "--series-id", SERIES, "--state-checkout", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "lordchrist-quiz" in output
