"""Provider-free regressions for the rejected and retired native QUIZ lanes.

The historical release is read, never dispatched. All ledgers/targets/receipts
below are synthetic, local, and do not constitute editorial or owner approval.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from quiz_fixture_helpers import fake_one, fake_profile_binding

from video_channel_manager import lordchrist_quiz as quiz
from video_channel_manager import telegram_multichannel_cli as cli
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_editorial_hold import (
    EditorialExecutionHold,
    require_execution_not_held,
    require_quiz_target_not_held,
)
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_multichannel_state import (
    GenericLedgerEntry,
    GenericPublicationLedger,
    initialize_ledger,
    prepare_next,
    save_ledger,
    skip_expired_pending,
)
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof, send_poll_once
from video_channel_manager.telegram_publication_freshness import skip_expired_pending_by_freshness
from video_channel_manager.telegram_target_binding import load_target_binding

SERIES = "lordchrist-quiz-series-03"
NOW = datetime(2026, 12, 12, 12, 0, tzinfo=UTC)


def _ledger(release):
    return GenericPublicationLedger(
        schema_name="video-channel-manager.telegram-generic-publication-ledger",
        schema_version=1,
        release_digest=release.digest,
        release_id=release.release_id,
        project_key=release.project_key,
        channel_username=release.channel_username,
        profile_sha256=release.profile_sha256,
        entries={
            item.publication_id: GenericLedgerEntry(
                publication_id=item.publication_id, provider_payload_sha256=item.payload.provider_payload_sha256
            )
            for item in release.items
        },
    )


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
        chat_title=profile.channel_title,
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )


def test_historical_and_copied_ids_cannot_initialize_even_in_a_renamed_release() -> None:
    paths = [quiz.series_runtime_path(x) for x in ("lordchrist-quiz-series-01", "lordchrist-quiz-series-02", SERIES)]
    paths.append(quiz.runtime_path("lordchrist-quiz-city-of-palms"))
    profile = load_channel_profile(quiz.PROFILE_PATH)
    binding = load_target_binding(quiz.BINDING_PATH, profile)
    unpublished_spec = quiz.load_quiz_spec(quiz.spec_path("lordchrist-quiz-book-without-gods-name"))
    with pytest.raises(EditorialExecutionHold):
        initialize_ledger(quiz.build_quiz_candidate(profile, unpublished_spec, binding))
    for path in paths:
        release = load_release(path)
        with pytest.raises(EditorialExecutionHold, match="Historical QUIZ"):
            initialize_ledger(release)
        # Renaming the envelope is not a new editorial identity for old items.
        copied = release.model_copy(update={"release_id": "renamed-historical-release"})
        with pytest.raises(EditorialExecutionHold, match="Historical QUIZ"):
            require_execution_not_held(copied)


def test_rejected_series_cannot_advance_any_local_state_machine() -> None:
    release = load_release(quiz.series_runtime_path(SERIES))
    profile = load_channel_profile(quiz.PROFILE_PATH)
    binding = load_target_binding(quiz.BINDING_PATH, profile)
    ledger = _ledger(release)
    before = ledger.model_dump_json()
    target = _target(profile, binding, NOW)
    with pytest.raises(EditorialExecutionHold):
        skip_expired_pending(release, ledger, now=NOW)
    with pytest.raises(EditorialExecutionHold):
        skip_expired_pending_by_freshness(release, ledger, now=NOW)
    with pytest.raises(EditorialExecutionHold):
        prepare_next(
            profile,
            release,
            ledger,
            run_id="1",
            run_attempt="1",
            github_sha="a" * 40,
            github_workflow_sha="b" * 40,
            mode="manual",
            target=target,
            expected_publication_id=release.items[0].publication_id,
            now=NOW,
        )
    assert ledger.model_dump_json() == before


def test_retired_state_remains_readable_but_is_not_publishable(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    pub_id = "lordchrist-quiz-city-of-palms"
    release = load_release(quiz.runtime_path(pub_id))
    path = tmp_path / quiz.ledger_relative_path(pub_id)
    path.parent.mkdir(parents=True)
    save_ledger(path, _ledger(release))
    before = path.read_bytes()
    quiz.state_check(pub_id, tmp_path)
    assert quiz.main(["state-check", "--publication-id", pub_id, "--state-checkout", str(tmp_path)]) == 0
    assert "publication authority has not been established" in capsys.readouterr().out
    with pytest.raises(EditorialExecutionHold):
        quiz.state_check(pub_id, tmp_path, require_publishable=True)
    with pytest.raises(EditorialExecutionHold):
        quiz.state_init(pub_id, tmp_path)
    assert path.read_bytes() == before


def test_generic_cli_blocks_init_skip_prepare_and_send_before_any_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_path = quiz.series_runtime_path(SERIES)
    release = load_release(release_path)
    ledger_path = tmp_path / "ledger.json"
    save_ledger(ledger_path, _ledger(release))
    before = ledger_path.read_bytes()
    output = tmp_path / "output.json"
    common = ["--release", str(release_path)]
    commands = [
        ["initialize-ledger", *common, "--output", str(output), "--confirm", f"INITIALIZE:{release.digest}"],
        ["skip-expired", *common, "--ledger", str(ledger_path)],
        [
            "prepare",
            *common,
            "--profile",
            "missing",
            "--ledger",
            str(ledger_path),
            "--target-proof",
            "missing",
            "--mode",
            "manual",
            "--run-id",
            "1",
            "--run-attempt",
            "1",
            "--github-sha",
            "a" * 40,
            "--github-workflow-sha",
            "b" * 40,
            "--envelope-output",
            str(output),
        ],
        [
            "send-once",
            *common,
            "--profile",
            "missing",
            "--ledger",
            str(ledger_path),
            "--envelope",
            "missing",
            "--outcome-output",
            str(output),
        ],
    ]
    for command in commands:
        monkeypatch.setattr(sys, "argv", ["telegram_multichannel_cli", *command])
        with pytest.raises(EditorialExecutionHold):
            cli.main()
        assert ledger_path.read_bytes() == before
        assert not output.exists()
    # Validation/reconciliation remains available, rather than rewriting history.
    monkeypatch.setattr(
        sys, "argv", ["telegram_multichannel_cli", "validate-ledger", *common, "--ledger", str(ledger_path)]
    )
    assert cli.main() == 0
    assert ledger_path.read_bytes() == before


def test_hold_after_a_claim_does_not_convert_may_exist_into_retryable_absence() -> None:
    profile, binding = fake_profile_binding()
    _, release = fake_one(profile, binding)
    ledger = initialize_ledger(release)
    when = release.items[0].scheduled_at.astimezone(UTC)
    prepared = prepare_next(
        profile,
        release,
        ledger,
        run_id="1",
        run_attempt="1",
        github_sha="a" * 40,
        github_workflow_sha="b" * 40,
        mode="manual",
        target=_target(profile, binding, when),
        expected_publication_id=release.items[0].publication_id,
        now=when,
    )
    assert prepared.envelope is not None
    assert ledger.entries[release.items[0].publication_id].provider_effect == "may_exist"
    before = ledger.model_dump_json()
    held = release.model_copy(update={"release_id": "lordchrist-quiz-series-03-v1"})
    with pytest.raises(EditorialExecutionHold):
        cli._send_exact_payload(profile, held, ledger, prepared.envelope, now=when)
    assert ledger.model_dump_json() == before


def test_native_quiz_target_hold_cannot_be_bypassed_by_renamed_ids_or_direct_transport() -> None:
    profile = load_channel_profile(quiz.PROFILE_PATH)
    binding = load_target_binding(quiz.BINDING_PATH, profile)
    release = load_release(quiz.series_runtime_path(SERIES))
    target = _target(profile, binding, NOW)
    payload = release.items[0].payload
    calls = []

    def fake_http(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, request=request)

    with httpx.Client(transport=httpx.MockTransport(fake_http)) as client:
        with pytest.raises(EditorialExecutionHold, match="QUIZ requires"):
            send_poll_once(profile, target, payload, token="test-only", client=client, now=NOW)
    assert calls == []
    # Either immutable chat id or channel username is sufficient to stop a quiz.
    with pytest.raises(EditorialExecutionHold):
        require_quiz_target_not_held(channel_username="@otherchannel", chat_id=binding.chat_id, poll_type="quiz")
    with pytest.raises(EditorialExecutionHold):
        require_quiz_target_not_held(channel_username="@LORDCHRIST", chat_id=-1001234567890, poll_type="quiz")
    # This narrow guard does not disable ordinary polls or unrelated channels.
    require_quiz_target_not_held(channel_username="@lordchrist", chat_id=binding.chat_id, poll_type="regular")
    require_quiz_target_not_held(channel_username="@otherchannel", chat_id=-1001234567890, poll_type="quiz")
