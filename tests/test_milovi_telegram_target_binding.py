from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MILOVI_PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/milovi-cake.json"
MILOVI_BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/milovi-cake-target-binding.json"
SVODKA_PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
LORDCHRIST_PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/lordchrist.json"


def test_committed_milovi_binding_matches_fresh_reviewed_exact_identity() -> None:
    profile = load_channel_profile(MILOVI_PROFILE_PATH)
    binding = load_target_binding(MILOVI_BINDING_PATH, profile)

    assert profile.digest == "sha256:f1fe9e669895c553264e6127ec0d3495ffc794930616661982c786139082fbdc"
    assert binding.project_key == "milovi-cake"
    assert binding.channel_username == "@MiloviCake"
    assert binding.chat_id == -1002215328390
    assert binding.chat_username == "MiloviCake"
    assert binding.bot_id == 8716602202
    assert binding.bot_username == "preaching_mp3_bot"
    assert binding.can_post_messages is True
    assert binding.discovered_at_utc == datetime(2026, 8, 17, 20, 45, 30, 628066, tzinfo=UTC)
    assert binding.discovery_method == "getMe + getChat(public/numeric exact pair) + getChatMember(bot id)"
    assert binding.digest == "sha256:741a8b4b54d785976236c6f15ed5d82cc9ad46aeb96a80cf372f22c421ba047c"
    assert binding.provider_write_performed is False


@pytest.mark.parametrize("other_profile_path", [SVODKA_PROFILE_PATH, LORDCHRIST_PROFILE_PATH])
def test_committed_milovi_binding_fails_closed_for_other_channel_profiles(other_profile_path: Path) -> None:
    other_profile = load_channel_profile(other_profile_path)

    with pytest.raises(ValueError, match="differs from selected channel profile"):
        load_target_binding(MILOVI_BINDING_PATH, other_profile)
