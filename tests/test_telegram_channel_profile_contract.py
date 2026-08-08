from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile

ROOT = Path(__file__).resolve().parents[1]
SVODKA_PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
LORDCHRIST_PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
EXPECTED_STABLE_DIGEST = "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9"


def test_svodka_profile_digest_is_stable_channel_contract_not_write_gate() -> None:
    profile = load_channel_profile(SVODKA_PROFILE_PATH)
    activated = profile.model_copy(update={"provider_writes_authorized": True})

    assert profile.provider_writes_authorized is False
    assert activated.provider_writes_authorized is True
    assert profile.digest == EXPECTED_STABLE_DIGEST
    assert activated.digest == EXPECTED_STABLE_DIGEST
    assert "provider_writes_authorized" not in profile.contract_payload()


def test_identity_or_schedule_change_still_changes_profile_digest() -> None:
    profile = load_channel_profile(SVODKA_PROFILE_PATH)

    assert profile.model_copy(update={"channel_username": "@another_channel"}).digest != profile.digest
    assert profile.model_copy(update={"daily_verified_limit": 3}).digest != profile.digest
    assert profile.model_copy(update={"state_branch": "state/another-channel"}).digest != profile.digest


def test_generic_profile_model_represents_multiple_channels_without_core_constants() -> None:
    svodka = load_channel_profile(SVODKA_PROFILE_PATH)
    lordchrist = load_channel_profile(LORDCHRIST_PROFILE_PATH)

    assert svodka.project_key == "svodka"
    assert svodka.channel_username == "@deep_info_life"
    assert svodka.state_branch == "state/svodka-telegram"
    assert svodka.daily_verified_limit == 2
    assert svodka.bot_token_env == "SVODKA_TELEGRAM_BOT_TOKEN"

    assert lordchrist.project_key == "lord-god-strength"
    assert lordchrist.channel_username == "@lordchrist"
    assert lordchrist.state_branch == "state/lordchrist-telegram"
    assert lordchrist.daily_verified_limit == 1
    assert lordchrist.bot_token_env == "LORDCHRIST_TELEGRAM_BOT_TOKEN"
    assert lordchrist.provider_writes_authorized is False
    assert lordchrist.digest != svodka.digest
