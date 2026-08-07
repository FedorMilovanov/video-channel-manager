from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/svodka-telegram-preflight.yml"
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka-target-binding.json"


def test_svodka_target_binding_is_exact_and_profile_bound() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)

    assert binding.channel_username == "@deep_info_life"
    assert binding.chat_id == -1003527567039
    assert binding.bot_id == 8716602202
    assert binding.bot_username == "preaching_mp3_bot"
    assert binding.can_post_messages is True
    assert binding.provider_write_performed is False


def test_svodka_preflight_uses_pinned_binding_and_shared_bot_secret_without_mutation() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "BINDING_PATH: content/telegram/channels/svodka-target-binding.json" in workflow
    assert "load_target_binding" in workflow
    assert "secrets.LORDCHRIST_TELEGRAM_BOT_TOKEN" in workflow
    assert "--expected-chat-id \"$SVODKA_TELEGRAM_CHAT_ID\"" in workflow
    assert "--expected-bot-id \"$SVODKA_TELEGRAM_BOT_ID\"" in workflow
    assert "--expected-bot-username \"$SVODKA_TELEGRAM_BOT_USERNAME\"" in workflow
    assert "sendMessage" not in workflow
    assert "sendPoll" not in workflow
    assert "schedule:" not in workflow


def test_svodka_workflow_keeps_colon_bearing_pip_command_in_block_scalar() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "run: python -m pip install --disable-pip-version-check --only-binary=:all:" not in workflow
    assert "run: |\n          python -m pip install --disable-pip-version-check --only-binary=:all:" in workflow
