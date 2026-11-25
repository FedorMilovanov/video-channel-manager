from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from video_channel_manager.svodka_queue import load_svodka_draft
from video_channel_manager.svodka_release import authorize_svodka_release, build_svodka_release_candidate
from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_cli import (
    _preflight_release_target,
    _send_exact_payload,
    _send_persisted_once,
    main,
    parser,
)
from video_channel_manager.telegram_multichannel_outcome import GenericProviderOutcome, apply_provider_outcome
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue, save_release
from video_channel_manager.telegram_multichannel_state import initialize_ledger, load_ledger, prepare_next, save_ledger
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
QUEUE_PATH = REPOSITORY_ROOT / "content/telegram/svodka/draft-14-posts-2026-08.json"
GITHUB_SHA = "1" * 40
WORKFLOW_SHA = "2" * 40


def _candidate_release() -> GenericReleaseQueue:
    profile = load_channel_profile(PROFILE_PATH)
    draft = load_svodka_draft(QUEUE_PATH, profile)
    binding = load_target_binding(BINDING_PATH, profile)
    return build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-cli-test",
        binding=binding,
    )


def _authorized_release() -> GenericReleaseQueue:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    candidate = _candidate_release()
    return authorize_svodka_release(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="runtime-test",
        reviewed_at=datetime(2026, 8, 8, 0, 0, tzinfo=UTC),
    )


def _prepared_runtime():
    base_profile = load_channel_profile(PROFILE_PATH)
    profile = base_profile.model_copy(update={"provider_writes_authorized": True})
    draft = load_svodka_draft(QUEUE_PATH, profile)
    binding = load_target_binding(BINDING_PATH, base_profile).model_copy(update={"profile_sha256": profile.digest})
    candidate = build_svodka_release_candidate(
        profile,
        draft,
        release_id="svodka-pilot-2026-08-send-test",
        binding=binding,
    )
    release = authorize_svodka_release(
        candidate,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=candidate.candidate_digest(),
        reviewed_by="runtime-test",
        reviewed_at=datetime(2026, 8, 8, 0, 0, tzinfo=UTC),
    )
    ledger = initialize_ledger(release)
    now = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
    target = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=binding.bot_id,
        bot_username=binding.bot_username,
        chat_id=binding.chat_id,
        chat_username=binding.chat_username,
        chat_title="СВОДКА",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=now,
    )
    first_id = release.items[0].publication_id
    prepared = prepare_next(
        profile,
        release,
        ledger,
        run_id="777",
        run_attempt="1",
        github_sha=GITHUB_SHA,
        github_workflow_sha=WORKFLOW_SHA,
        mode="manual",
        target=target,
        expected_publication_id=first_id,
        now=now,
    )
    assert prepared.envelope is not None
    return profile, release, ledger, prepared.envelope


def test_missing_token_becomes_retryable_not_dispatched_outcome(monkeypatch) -> None:
    profile, release, ledger, envelope = _prepared_runtime()

    monkeypatch.delenv(profile.bot_token_env, raising=False)
    monkeypatch.delenv("MAX_PUBLICATION_LAG_MINUTES", raising=False)
    outcome = _send_exact_payload(profile, release, ledger, envelope)

    assert outcome.provider_effect == "not_dispatched"
    assert outcome.retryable is True
    assert outcome.receipt is None
    assert outcome.error == f"missing Telegram token in {profile.bot_token_env}"

    entry = apply_provider_outcome(ledger, envelope, outcome)
    assert entry.state == "pending"
    assert entry.provider_effect == "not_dispatched"
    assert entry.intent_id is None


def test_pre_provider_intent_mismatch_becomes_retryable_not_dispatched_outcome(monkeypatch) -> None:
    profile, release, ledger, envelope = _prepared_runtime()
    ledger.entries[envelope.publication_id].intent_id = "different-persisted-intent"
    monkeypatch.delenv("MAX_PUBLICATION_LAG_MINUTES", raising=False)

    outcome = _send_exact_payload(profile, release, ledger, envelope)

    assert outcome.provider_effect == "not_dispatched"
    assert outcome.retryable is True
    assert outcome.receipt is None
    assert "persisted ledger intent differs" in (outcome.error or "")


def test_expired_last_mile_freshness_proves_absence_without_provider_call(monkeypatch) -> None:
    profile, release, ledger, envelope = _prepared_runtime()
    monkeypatch.setenv(profile.bot_token_env, "provider-token-must-not-be-used")
    monkeypatch.setenv("MAX_PUBLICATION_LAG_MINUTES", "120")

    def unexpected_provider_call(*args, **kwargs):
        raise AssertionError("provider transport must not run after the last-mile freshness deadline")

    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli.send_message_once", unexpected_provider_call)
    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli.send_poll_once", unexpected_provider_call)
    after_deadline = release.items[0].scheduled_at + timedelta(minutes=120)

    outcome = _send_exact_payload(profile, release, ledger, envelope, now=after_deadline)

    assert outcome.provider_effect == "confirmed_absent"
    assert outcome.retryable is True
    assert outcome.receipt is None
    assert outcome.error == "publication freshness gate closed before provider mutation: publication_too_stale"

    entry = apply_provider_outcome(ledger, envelope, outcome)
    assert entry.state == "pending"
    assert entry.provider_effect == "confirmed_absent"
    assert entry.intent_id is None


def test_initialize_ledger_confirmation_is_exact_release_digest(monkeypatch, tmp_path: Path) -> None:
    release = _authorized_release()
    release_path = tmp_path / "release.json"
    ledger_path = tmp_path / "ledger.json"
    save_release(release_path, release)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_multichannel_cli",
            "initialize-ledger",
            "--release",
            str(release_path),
            "--output",
            str(ledger_path),
            "--confirm",
            f"INITIALIZE:{release.digest}",
        ],
    )

    assert main() == 0
    ledger = load_ledger(ledger_path, release)
    assert ledger.release_digest == release.digest
    assert len(ledger.entries) == len(release.items)


def test_initialize_ledger_rejects_legacy_or_wrong_confirmation(monkeypatch, tmp_path: Path) -> None:
    release = _authorized_release()
    release_path = tmp_path / "release.json"
    ledger_path = tmp_path / "ledger.json"
    save_release(release_path, release)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_multichannel_cli",
            "initialize-ledger",
            "--release",
            str(release_path),
            "--output",
            str(ledger_path),
            "--confirm",
            f"INITIALIZE:{release.release_id}:{release.digest}",
        ],
    )

    with pytest.raises(ValueError, match="exact release digest"):
        main()
    assert not ledger_path.exists()


def test_initialize_ledger_rejects_unauthorized_candidate(monkeypatch, tmp_path: Path) -> None:
    candidate = _candidate_release()
    release_path = tmp_path / "candidate.json"
    ledger_path = tmp_path / "ledger.json"
    save_release(release_path, candidate)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_multichannel_cli",
            "initialize-ledger",
            "--release",
            str(release_path),
            "--output",
            str(ledger_path),
            "--confirm",
            f"INITIALIZE:{candidate.digest}",
        ],
    )

    with pytest.raises(ValueError, match="authorized immutable release"):
        main()
    assert not ledger_path.exists()


def test_low_level_initialize_ledger_rejects_unauthorized_candidate() -> None:
    candidate = _candidate_release()

    with pytest.raises(ValueError, match="authorized immutable release"):
        initialize_ledger(candidate)


def test_integrated_preflight_uses_exact_release_binding(monkeypatch) -> None:
    profile = load_channel_profile(PROFILE_PATH)
    release = _authorized_release()
    binding = load_target_binding(BINDING_PATH, profile)
    _, _, _, envelope = _prepared_runtime()
    calls = []

    def preflight(selected, **kwargs):
        calls.append((selected, kwargs))
        return envelope.target

    monkeypatch.setenv(profile.bot_token_env, "offline-test-token")
    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli.preflight_channel", preflight)
    assert _preflight_release_target(profile, release, BINDING_PATH) == envelope.target
    assert calls == [
        (
            profile,
            {
                "token": "offline-test-token",
                "expected_chat_id": binding.chat_id,
                "expected_bot_id": binding.bot_id,
                "expected_bot_username": binding.bot_username,
            },
        )
    ]


@pytest.mark.parametrize("case", ["disabled", "unauthorized", "wrong_digest", "wrong_chat"])
def test_integrated_preflight_rejects_invalid_authority_before_network(monkeypatch, case: str) -> None:
    profile = load_channel_profile(PROFILE_PATH)
    release = _authorized_release()
    if case == "disabled":
        profile = profile.model_copy(update={"provider_writes_authorized": False})
    elif case == "unauthorized":
        release = _candidate_release()
    elif case == "wrong_digest":
        release = release.model_copy(update={"target_binding_sha256": "sha256:" + "0" * 64})
    else:
        release = release.model_copy(update={"chat_id": -12345})

    def unexpected(*args, **kwargs):
        pytest.fail("invalid profile or release must not reach the provider")

    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli.preflight_channel", unexpected)
    with pytest.raises(ValueError, match="write-disabled|not authorized|binding differs"):
        _preflight_release_target(profile, release, BINDING_PATH)


def test_prepare_accepts_one_target_source_without_extra_flags() -> None:
    args = [
        "prepare",
        "--profile",
        "profile.json",
        "--release",
        "release.json",
        "--ledger",
        "ledger.json",
        "--mode",
        "manual",
        "--publication-id",
        "sample-id",
        "--run-id",
        "1",
        "--run-attempt",
        "1",
        "--github-sha",
        GITHUB_SHA,
        "--github-workflow-sha",
        WORKFLOW_SHA,
        "--envelope-output",
        "envelope.json",
    ]
    assert parser().parse_args(args + ["--binding", "binding.json"]).binding == Path("binding.json")
    assert parser().parse_args(args + ["--target-proof", "proof.json"]).target_proof == Path("proof.json")
    with pytest.raises(SystemExit):
        parser().parse_args(args)
    with pytest.raises(SystemExit):
        parser().parse_args(args + ["--binding", "binding.json", "--target-proof", "proof.json"])


@pytest.mark.parametrize("interrupted", [False, True])
def test_persisted_send_claim_blocks_replay_even_with_new_output_path(
    monkeypatch, tmp_path: Path, interrupted: bool
) -> None:
    profile, release, ledger, envelope = _prepared_runtime()
    ledger_path = tmp_path / "ledger.json"
    output = tmp_path / "outcome.json"
    save_ledger(ledger_path, ledger)
    calls = []

    def send(*args):
        calls.append(args)
        if interrupted:
            raise RuntimeError("simulated crash after possible provider dispatch")
        return GenericProviderOutcome(
            schema_name="video-channel-manager.telegram-generic-provider-outcome",
            schema_version=1,
            publication_id=envelope.publication_id,
            provider_payload_sha256=envelope.provider_payload_sha256,
            provider_effect="may_exist",
            retryable=False,
            error="offline ambiguous effect",
        )

    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli._send_exact_payload", send)
    if interrupted:
        with pytest.raises(RuntimeError, match="simulated crash"):
            _send_persisted_once(profile, release, ledger_path, envelope, output)
        assert not output.exists()
    else:
        outcome = _send_persisted_once(profile, release, ledger_path, envelope, output)
        assert GenericProviderOutcome.model_validate_json(output.read_text(encoding="utf-8")) == outcome

    with pytest.raises(ValueError, match="intent already claimed"):
        _send_persisted_once(profile, release, ledger_path, envelope, tmp_path / "other-outcome.json")
    assert len(calls) == 1
    assert load_ledger(ledger_path, release).entries[envelope.publication_id].provider_effect == "may_exist"


def test_persisted_send_rejects_wrong_intent_before_claim(monkeypatch, tmp_path: Path) -> None:
    profile, release, ledger, envelope = _prepared_runtime()
    ledger_path = tmp_path / "ledger.json"
    ledger.entries[envelope.publication_id].intent_id = "different-persisted-intent"
    save_ledger(ledger_path, ledger)

    def unexpected(*args):
        pytest.fail("invalid intent must not reach the sender")

    monkeypatch.setattr("video_channel_manager.telegram_multichannel_cli._send_exact_payload", unexpected)
    with pytest.raises(ValueError, match="persisted ledger intent differs"):
        _send_persisted_once(profile, release, ledger_path, envelope, tmp_path / "outcome.json")
    assert not (tmp_path / ".ledger.json.dispatch-claims").exists()
