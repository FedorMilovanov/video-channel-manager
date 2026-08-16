from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseQueue, load_release, save_release
from video_channel_manager.telegram_release_binding import bind_release_candidate
from video_channel_manager.telegram_release_binding_cli import main
from video_channel_manager.telegram_release_review import authorize_release_candidate
from video_channel_manager.telegram_research import load_research_queue
from video_channel_manager.telegram_research_release import build_research_release_candidate
from video_channel_manager.telegram_target_binding import TelegramTargetBinding, load_target_binding

ROOT = Path(__file__).parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
BINDING_PATH = ROOT / "content/telegram/channels/lordchrist-target-binding.json"
QUEUE_PATH = ROOT / "content/telegram/lordchrist/research-queues/calvin-spurgeon-macarthur-v2.json"


def contract() -> tuple[TelegramChannelProfile, TelegramTargetBinding, GenericReleaseQueue]:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    research = load_research_queue(QUEUE_PATH)
    candidate = build_research_release_candidate(
        profile,
        research,
        release_id="lordchrist-release-binding-test-v1",
        start_at=datetime(2026, 8, 10, 19, 17, tzinfo=ZoneInfo("Europe/Moscow")),
    )
    assert candidate.target_binding_sha256 is None
    assert candidate.release_authorized is False
    return profile, binding, candidate


def bind(
    profile: TelegramChannelProfile,
    binding: TelegramTargetBinding,
    candidate: GenericReleaseQueue,
    *,
    expected: str | None = None,
) -> GenericReleaseQueue:
    return bind_release_candidate(
        candidate,
        profile=profile,
        binding=binding,
        expected_unbound_candidate_sha256=expected or candidate.candidate_digest(),
    )


def test_exact_unbound_candidate_can_be_bound_without_authorization_or_provider_effect() -> None:
    profile, binding, candidate = contract()
    original_digest = candidate.candidate_digest()

    bound = bind(profile, binding, candidate)

    assert bound.release_authorized is False
    assert bound.reviewed_candidate_sha256 is None
    assert bound.reviewed_by is None
    assert bound.reviewed_at is None
    assert bound.target_binding_sha256 == binding.digest
    assert bound.chat_id == binding.chat_id
    assert bound.bot_id == binding.bot_id
    assert bound.bot_username == binding.bot_username
    assert bound.items == candidate.items
    assert bound.candidate_digest() != original_digest
    assert candidate.target_binding_sha256 is None


def test_binding_rejects_digest_profile_binding_and_rebind_drift() -> None:
    profile, binding, candidate = contract()

    with pytest.raises(ValueError, match="expected unbound digest"):
        bind(profile, binding, candidate, expected="sha256:" + "0" * 64)

    changed_profile = profile.model_copy(update={"channel_title": profile.channel_title + " changed"})
    with pytest.raises(ValueError, match="selected Telegram channel profile"):
        bind(changed_profile, binding, candidate)

    changed_binding = binding.model_copy(update={"profile_sha256": "sha256:" + "0" * 64})
    changed_binding = TelegramTargetBinding.model_validate(changed_binding.model_dump(mode="json"))
    with pytest.raises(ValueError, match="selected Telegram channel profile"):
        bind(profile, changed_binding, candidate)

    bound = bind(profile, binding, candidate)
    with pytest.raises(ValueError, match="already target-bound"):
        bind_release_candidate(
            bound,
            profile=profile,
            binding=binding,
            expected_unbound_candidate_sha256=bound.candidate_digest(),
        )


def test_binding_rejects_already_authorized_release() -> None:
    profile, binding, candidate = contract()
    bound = bind(profile, binding, candidate)
    approved = authorize_release_candidate(
        bound,
        profile=profile,
        binding=binding,
        expected_candidate_sha256=bound.candidate_digest(),
        reviewed_by="FedorMilovanov",
        reviewed_at=datetime(2026, 8, 17, 0, 30, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="already authorized"):
        bind_release_candidate(
            approved,
            profile=profile,
            binding=binding,
            expected_unbound_candidate_sha256=approved.candidate_digest(),
        )


def test_release_binding_cli_writes_exact_unauthorized_bound_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    profile, binding, candidate = contract()
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "bound.json"
    save_release(candidate_path, candidate)
    expected = candidate.candidate_digest()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telegram_release_binding_cli",
            "--profile",
            str(PROFILE_PATH),
            "--binding",
            str(BINDING_PATH),
            "--candidate",
            str(candidate_path),
            "--expected-unbound-candidate-sha256",
            expected,
            "--output",
            str(output_path),
        ],
    )

    assert main() == 0
    summary = json.loads(capsys.readouterr().out)
    bound = load_release(output_path)
    assert summary["bound"] is True
    assert summary["authorized"] is False
    assert summary["provider_write_performed"] is False
    assert summary["unbound_candidate_sha256"] == expected
    assert summary["bound_candidate_sha256"] == bound.candidate_digest()
    assert summary["target_binding_sha256"] == binding.digest
    assert bound.profile_sha256 == profile.digest
    assert bound.items == candidate.items
    assert bound.release_authorized is False


def test_release_binding_runtime_has_no_provider_or_secret_dependency() -> None:
    source = (ROOT / "src/video_channel_manager/telegram_release_binding.py").read_text(encoding="utf-8")
    cli = (ROOT / "src/video_channel_manager/telegram_release_binding_cli.py").read_text(encoding="utf-8")
    combined = source + "\n" + cli
    for forbidden in (
        "httpx",
        "preflight_channel",
        "getMe",
        "getChat",
        "getChatMember",
        "sendMessage",
        "sendPhoto",
        "sendPoll",
        "BOT_TOKEN",
        "os.environ",
    ):
        assert forbidden not in combined
