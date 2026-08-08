from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_release import load_release
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEDGER_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-ledger-init.yml"
CANARY_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/svodka-canary.yml"
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"
APPROVED_RELEASE = REPOSITORY_ROOT / "content/telegram/svodka/approved-release-2026-08.json"


def test_ledger_initialization_is_manual_exact_and_provider_free() -> None:
    workflow = LEDGER_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "INITIALIZE:$REQUESTED_DIGEST" in workflow
    assert "approved-release-2026-08.json" in workflow
    assert "release.release_authorized" in workflow
    assert "state/svodka-telegram" in workflow
    assert "initialize-ledger" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "send-once" not in workflow
    assert "secrets." not in workflow


def test_canary_is_one_exact_manual_dispatch_with_durable_intent_first() -> None:
    workflow = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "CANARY:$REQUESTED_PUBLICATION_ID:$REQUESTED_DIGEST" in workflow
    assert "profile.provider_writes_authorized" in workflow
    assert "release.release_authorized" in workflow
    assert "approved-release-2026-08.json" in workflow
    assert "Fresh read-only target preflight" in workflow
    assert "Persist intent before Telegram mutation" in workflow
    assert "send-once" in workflow
    assert workflow.index("Persist intent before Telegram mutation") < workflow.index("send-once")
    assert "apply-outcome" in workflow
    assert "if: always()" not in workflow
    assert "!cancelled()" in workflow
    assert "initialize-ledger" not in workflow
    assert "state/svodka-telegram" in workflow


def test_committed_live_release_if_present_is_exact_and_authorized() -> None:
    if not APPROVED_RELEASE.exists():
        return

    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)
    release = load_release(APPROVED_RELEASE)

    assert release.release_authorized is True
    assert release.project_key == profile.project_key
    assert release.channel_username == profile.channel_username
    assert release.profile_sha256 == profile.digest
    assert release.target_binding_sha256 == binding.digest
    assert release.chat_id == binding.chat_id
    assert release.bot_id == binding.bot_id
    assert release.bot_username == binding.bot_username
