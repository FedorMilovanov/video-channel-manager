"""The verified 2026-10-29 manual quiz canary authorizes the same target in Series 02.

Provider-inert regression coverage: never send a Telegram poll from these tests.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_cli import main
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import (
    initialize_ledger,
    mark_published,
    prepare_next,
    skip_expired_pending,
    load_ledger,
    save_ledger,
)
from video_channel_manager.telegram_multichannel_transport import GenericSendReceipt, GenericTargetProof
from video_channel_manager.telegram_target_binding import load_target_binding

ROOT = Path(__file__).resolve().parents[1]
QUIZ_DIR = ROOT / "content/telegram/lordchrist/quiz"
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist-rich.json"
BINDING_PATH = ROOT / "content/telegram/channels/lordchrist-target-binding.json"
WORKFLOW_PATH = ROOT / ".github/workflows/lordchrist-quiz-series-poster.yml"
GITHUB_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40


def _target(profile, binding, now):
    return GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        chat_title="LordChrist",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )


def _case(*, published_canary=True):
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    old_release = load_release(QUIZ_DIR / "lordchrist-quiz-city-of-palms-runtime.json")
    new_release = load_release(QUIZ_DIR / "lordchrist-quiz-series-02-runtime.json")
    old_ledger = initialize_ledger(old_release)
    new_ledger = initialize_ledger(new_release)

    if published_canary:
        old_time = datetime(2026, 10, 29, 17, 10, tzinfo=UTC)
        manual = prepare_next(
            profile,
            old_release,
            old_ledger,
            run_id="123",
            run_attempt="1",
            github_sha=GITHUB_SHA,
            github_workflow_sha=WORKFLOW_SHA,
            mode="manual",
            target=_target(profile, binding, old_time),
            expected_publication_id=old_release.items[0].publication_id,
            now=old_time,
        )
        assert manual.envelope is not None
        receipt = GenericSendReceipt(
            schema_name="video-channel-manager.telegram-generic-send-receipt",
            schema_version=1,
            project_key=profile.project_key,
            publication_id=manual.envelope.publication_id,
            provider_payload_sha256=manual.envelope.provider_payload_sha256,
            chat_id=binding.chat_id,
            chat_username=binding.chat_username,
            message_id=1591,
            message_url="https://t.me/lordchrist/1591",
            verified_at_utc=datetime(2026, 10, 29, 17, 23, tzinfo=UTC),
        )
        mark_published(old_ledger, manual.envelope, receipt)

    due = datetime(2026, 11, 14, 10, 17, tzinfo=UTC)
    assert skip_expired_pending(new_release, new_ledger, now=due) == (
        "lordchrist-quiz-s02-hagar",
        "lordchrist-quiz-s02-ahab",
    )
    return profile, binding, old_release, old_ledger, new_release, new_ledger, due


def _prepare(case, *, canary=True, now=None, canary_release=None, canary_ledger=None):
    profile, binding, old_release, old_ledger, release, ledger, due = case
    effective_now = now or due
    return prepare_next(
        profile,
        release,
        ledger,
        run_id="456",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=_target(profile, binding, effective_now),
        now=effective_now,
        verified_canary=((canary_release or old_release, canary_ledger or old_ledger) if canary else None),
    )


def test_series02_accepts_verified_manual_canary_from_reviewed_original_release():
    case = _case()
    without = _prepare(case, canary=False)
    assert without.envelope is None
    assert without.reason == "scheduled execution requires a verified manual canary"

    with_canary = _prepare(case)
    assert with_canary.envelope is not None
    assert with_canary.envelope.publication_id == "lordchrist-quiz-s02-jephthah"
    assert with_canary.envelope.dispatch_mode == "scheduled"
    assert case[5].entries["lordchrist-quiz-s02-jephthah"].state == "dispatching"
    assert case[3].entries["lordchrist-quiz-city-of-palms"].state == "published"


def test_unverified_external_canary_cannot_unlock_series02():
    case = _case(published_canary=False)
    blocked = _prepare(case)
    assert blocked.envelope is None
    assert blocked.reason == "scheduled execution requires a verified manual canary"
    assert case[5].entries["lordchrist-quiz-s02-jephthah"].state == "pending"


def test_wrong_bot_binding_cannot_unlock_series02():
    case = _case()
    foreign_release = case[2].model_copy(update={"bot_id": 1234567890})
    with pytest.raises(ValueError, match="ledger identity differs|external manual canary release differs"):
        _prepare(case, canary_release=foreign_release)
    assert case[5].entries["lordchrist-quiz-s02-jephthah"].state == "pending"


def test_external_canary_does_not_open_a_future_quiz_slot():
    case = _case()
    before = datetime(2026, 11, 13, 19, 0, tzinfo=UTC)
    not_due = _prepare(case, now=before)
    assert not_due.envelope is None
    assert "does not open until" in not_due.reason
    assert case[5].entries["lordchrist-quiz-s02-jephthah"].state == "pending"


def test_production_workflow_uses_old_verified_ledger_without_changing_release():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert (
        '--verified-manual-canary-release "content/telegram/lordchrist/quiz/lordchrist-quiz-city-of-palms-runtime.json"'
        in workflow
    )
    assert (
        '--verified-manual-canary-ledger "$STATE_DIR/content/telegram/lordchrist/quiz/lordchrist-quiz-city-of-palms-ledger.json"'
        in workflow
    )
    assert "SERIES_ID: lordchrist-quiz-series-02" in workflow
    assert 'MAX_PUBLICATION_LAG_MINUTES: "360"' in workflow
    assert "Send exactly once through the canonical generic Telegram runtime" in workflow


def test_real_cli_prepare_consumes_historical_verified_canary_without_provider(monkeypatch, tmp_path, capsys):
    case = _case()
    profile, binding, _old_release, old_ledger, release, new_ledger, due = case
    old_path = tmp_path / "old-ledger.json"
    new_path = tmp_path / "series-ledger.json"
    target_path = tmp_path / "target.json"
    envelope_path = tmp_path / "dispatch.json"
    save_ledger(old_path, old_ledger)
    save_ledger(new_path, new_ledger)
    target_path.write_text(_target(profile, binding, due).model_dump_json(indent=2), encoding="utf-8")
    monkeypatch.setattr("video_channel_manager.telegram_multichannel_state.utc_now", lambda: due)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_multichannel_cli",
            "prepare",
            "--profile",
            str(PROFILE_PATH),
            "--release",
            str(QUIZ_DIR / "lordchrist-quiz-series-02-runtime.json"),
            "--ledger",
            str(new_path),
            "--target-proof",
            str(target_path),
            "--mode",
            "scheduled",
            "--verified-manual-canary-release",
            str(QUIZ_DIR / "lordchrist-quiz-city-of-palms-runtime.json"),
            "--verified-manual-canary-ledger",
            str(old_path),
            "--run-id",
            "456",
            "--run-attempt",
            "1",
            "--github-sha",
            GITHUB_SHA,
            "--github-workflow-sha",
            WORKFLOW_SHA,
            "--envelope-output",
            str(envelope_path),
        ],
    )

    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["prepared"] is True
    assert result["publication_id"] == "lordchrist-quiz-s02-jephthah"
    assert envelope_path.is_file()
    verified_new = load_ledger(new_path, release)
    assert verified_new.entries["lordchrist-quiz-s02-jephthah"].state == "dispatching"
    assert old_ledger.entries["lordchrist-quiz-city-of-palms"].state == "published"


def test_scheduled_workflow_omits_manual_only_publication_id_argument():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert 'case "${{ steps.gate.outputs.dispatch_mode }}" in' in workflow
    assert 'publication_args=(--publication-id "${{ steps.due.outputs.publication_id }}")' in workflow
    mode_case = workflow.split('case "${{ steps.gate.outputs.dispatch_mode }}" in', 1)[1].split("esac", 1)[0]
    assert mode_case.split("scheduled)", 1)[1].split(";;", 1)[0].strip() == ""
    assert '"${publication_args[@]}" \\' in workflow
    assert workflow.count("--publication-id") == 1
    # This is a genuine fail-closed contract in the generic dispatch state machine.
    case = _case()
    profile, binding, _old_release, old_ledger, release, ledger, due = case
    blocked = prepare_next(
        profile,
        release,
        ledger,
        run_id="456",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="scheduled",
        target=_target(profile, binding, due),
        now=due,
        expected_publication_id="lordchrist-quiz-s02-jephthah",
        verified_canary=(
            load_release(QUIZ_DIR / "lordchrist-quiz-city-of-palms-runtime.json"),
            old_ledger,
        ),
    )
    assert blocked.envelope is None
    assert blocked.reason == "scheduled execution must not carry a manual publication_id"
    assert ledger.entries["lordchrist-quiz-s02-jephthah"].state == "pending"
