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
from quiz_fixture_helpers import FIXTURE_ONE, fake_one, fake_profile_binding, fake_series

from video_channel_manager import lordchrist_quiz as quiz
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_editorial_hold import EditorialExecutionHold
from video_channel_manager.telegram_target_binding import load_target_binding

ONE = "lordchrist-quiz-city-of-palms"
SERIES = "lordchrist-quiz-series-02"


def _profile_binding():
    profile = load_channel_profile(quiz.PROFILE_PATH)
    return profile, load_target_binding(quiz.BINDING_PATH, profile)


def test_historical_quiz_releases_remain_reviewable_but_never_executable() -> None:
    series = quiz.validate_series(SERIES, require_release_authorized=True)
    assert series["series_id"] == SERIES
    assert series["items"] == 10
    assert series["release_authorized"] is True
    with pytest.raises(ValueError, match="retired quiz series"):
        quiz.validate_series(SERIES, require_execution_authorized=True)

    single = quiz.validate_quiz(ONE, require_release_authorized=True)
    assert single["publication_id"] == ONE
    assert single["payload_kind"] == "quiz"
    assert single["release_authorized"] is True
    with pytest.raises(ValueError, match="retired one-off quiz"):
        quiz.validate_quiz(ONE, require_execution_authorized=True)


def test_series_state_init_is_local_idempotent_and_checked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile, binding = fake_profile_binding()
    series, release = fake_series(profile, binding)
    monkeypatch.setattr(quiz, "_load_series_bundle", lambda _id: (series, release))
    fixture_id = "synthetic-series-for-test"
    with pytest.raises(ValueError, match="not initialized"):
        quiz.series_state_check(fixture_id, tmp_path)
    path = quiz.series_state_init(fixture_id, tmp_path)
    before = path.read_bytes()
    assert quiz.series_state_check(fixture_id, tmp_path) == {"pending": 10}
    assert quiz.series_state_init(fixture_id, tmp_path) == path
    assert path.read_bytes() == before
    data = json.loads(path.read_text("utf-8"))
    data["release_digest"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        quiz.series_state_check(fixture_id, tmp_path)
    with pytest.raises(ValueError):
        quiz.series_state_init(fixture_id, tmp_path)


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
    profile, binding = fake_profile_binding()
    spec, release = fake_one(profile, binding)
    monkeypatch.setattr(quiz, "_load_bundle", lambda _id: (spec, release))
    path = tmp_path / quiz.ledger_relative_path(FIXTURE_ONE)
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        quiz,
        "load_ledger",
        lambda _path, _release: SimpleNamespace(entries={FIXTURE_ONE: SimpleNamespace(state="published")}),
    )
    with pytest.raises(ValueError, match="replay is forbidden"):
        quiz.state_check(FIXTURE_ONE, tmp_path, require_publishable=True)


def test_historical_cli_is_readable_but_cannot_resign_or_initialize(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stamp = "2026-11-04T16:00:00+03:00"
    assert quiz.main(["validate", "--publication-id", ONE, "--require-release-authorized"]) == 0
    assert quiz.main(["validate-series", "--series-id", SERIES, "--require-release-authorized"]) == 0
    for kind, ident in (("runtime", ONE), ("series-runtime", SERIES)):
        output = tmp_path / f"{kind}.json"
        with pytest.raises(EditorialExecutionHold, match="Historical QUIZ"):
            quiz.main(
                [
                    f"build-{kind}",
                    "--publication-id" if kind == "runtime" else "--series-id",
                    ident,
                    "--reviewed-by",
                    "fixture",
                    "--reviewed-at",
                    stamp,
                    "--output",
                    str(output),
                ]
            )
        assert not output.exists()
    with pytest.raises(EditorialExecutionHold, match="Historical QUIZ"):
        quiz.main(["state-init", "--publication-id", ONE, "--state-checkout", str(tmp_path)])
    with pytest.raises(EditorialExecutionHold, match="Historical QUIZ"):
        quiz.main(["series-state-init", "--series-id", SERIES, "--state-checkout", str(tmp_path)])
    assert "lordchrist-quiz" in capsys.readouterr().out


def test_local_cli_build_and_state_use_synthetic_channel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile, binding = fake_profile_binding()
    spec, _ = fake_one(profile, binding)
    series, _ = fake_series(profile, binding)
    profile_path, binding_path = tmp_path / "profile.json", tmp_path / "binding.json"
    spec_path, one_runtime = tmp_path / "one-spec.json", tmp_path / "one-runtime.json"
    series_spec, series_runtime = tmp_path / "series-spec.json", tmp_path / "series-runtime.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")
    binding_path.write_text(binding.model_dump_json(), encoding="utf-8")
    spec_path.write_text(spec.model_dump_json(), encoding="utf-8")
    series_spec.write_text(series.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(quiz, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(quiz, "BINDING_PATH", binding_path)
    monkeypatch.setattr(quiz, "spec_path", lambda _id: spec_path)
    monkeypatch.setattr(quiz, "runtime_path", lambda _id: one_runtime)
    monkeypatch.setattr(quiz, "series_spec_path", lambda _id: series_spec)
    monkeypatch.setattr(quiz, "series_runtime_path", lambda _id: series_runtime)
    # Only tests CLI plumbing, not editorial approval.
    monkeypatch.setattr(quiz, "require_future_series_editorial_signoff", lambda *_a, **_kw: None)
    stamp = "2026-11-04T16:00:00+03:00"
    assert (
        quiz.main(
            [
                "build-runtime",
                "--publication-id",
                FIXTURE_ONE,
                "--reviewed-by",
                "test-fixture",
                "--reviewed-at",
                stamp,
                "--output",
                str(one_runtime),
            ]
        )
        == 0
    )
    assert (
        quiz.main(
            [
                "build-series-runtime",
                "--series-id",
                series.series_id,
                "--reviewed-by",
                "test-fixture",
                "--reviewed-at",
                stamp,
                "--output",
                str(series_runtime),
            ]
        )
        == 0
    )
    assert quiz.main(["validate", "--publication-id", FIXTURE_ONE, "--require-release-authorized"]) == 0
    assert quiz.main(["validate-series", "--series-id", series.series_id, "--require-release-authorized"]) == 0
    with pytest.raises(ValueError, match="not initialized"):
        quiz.state_check(FIXTURE_ONE, tmp_path)
    assert quiz.main(["state-init", "--publication-id", FIXTURE_ONE, "--state-checkout", str(tmp_path)]) == 0
    # An already valid ledger is read without recreating or replacing it.
    one_ledger = tmp_path / quiz.ledger_relative_path(FIXTURE_ONE)
    before = one_ledger.read_bytes()
    assert quiz.main(["state-init", "--publication-id", FIXTURE_ONE, "--state-checkout", str(tmp_path)]) == 0
    assert one_ledger.read_bytes() == before
    assert quiz.main(["series-state-init", "--series-id", series.series_id, "--state-checkout", str(tmp_path)]) == 0
    assert quiz.main(["series-state-check", "--series-id", series.series_id, "--state-checkout", str(tmp_path)]) == 0
    assert (
        quiz.main(
            ["state-check", "--publication-id", FIXTURE_ONE, "--state-checkout", str(tmp_path), "--require-publishable"]
        )
        == 0
    )
