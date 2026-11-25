from pathlib import Path

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_target_binding import load_target_binding, target_binding_from_proof

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/legendary-poet.json"
BINDING_PATH = ROOT / "content/telegram/channels/legendary-poet-target-binding.json"


def test_existing_shared_bot_has_pinned_isolated_legendary_poet_target() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    binding = load_target_binding(BINDING_PATH, profile)

    assert profile.project_key == "legendary-poet"
    assert profile.channel_username == "@thelegendarypoet"
    assert profile.provider_writes_authorized is False
    assert profile.state_branch == "state/legendary-poet-telegram"
    assert profile.concurrency_group == "legendary-poet-telegram-publisher"
    assert profile.bot_token_env == "LEGENDARY_POET_TELEGRAM_BOT_TOKEN"
    assert profile.digest == "sha256:9c98dcd3a008d66a7fd5731acf4b5151b01d39f1fce2e20d21c4b2f31c0e0ef4"
    assert binding.digest == "sha256:f15d25ea9abec32327d88e819575441f0194ff6fd8adae63f6627d803ef688a3"
    assert binding.chat_id == -1003345085810
    assert binding.bot_id == 8716602202
    assert binding.bot_username == "preaching_mp3_bot"
    assert binding.can_post_messages is True
    assert binding.provider_write_performed is False


def test_other_channel_evidence_cannot_be_rebound_to_legendary_poet() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    proof = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key="lord-god-strength",
        channel_username="@lordchrist",
        profile_sha256="sha256:" + "0" * 64,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="LordChrist",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=load_target_binding(BINDING_PATH, profile).discovered_at_utc,
    )
    with pytest.raises(ValueError, match="proof differs"):
        target_binding_from_proof(profile, proof)


def test_legendary_poet_onboarding_does_not_demand_second_bot() -> None:
    text = (ROOT / "docs/operations/legendary-poet-telegram-audio-onboarding.md").read_text(encoding="utf-8")
    assert "never borrow the LordChrist or Milovi Cake bot" not in text
    assert "@preaching_mp3_bot" in text
    assert "provider_writes_authorized=false" in text
    assert "No Telegram write request occurred" in text
