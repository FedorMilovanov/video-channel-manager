from __future__ import annotations

import json
from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile

ROOT = Path(__file__).resolve().parents[1]
SVODKA_PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
LORDCHRIST_PROFILE_PATH = ROOT / "content/telegram/channels/lordchrist.json"
LORDCHRIST_PRODUCTION_PATH = ROOT / "content/telegram/lordchrist/production-schedule.json"
EXPECTED_STABLE_DIGEST = "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9"


def test_svodka_profile_digest_is_stable_channel_contract_not_write_gate() -> None:
    profile = load_channel_profile(SVODKA_PROFILE_PATH)
    disabled = profile.model_copy(update={"provider_writes_authorized": False})

    assert profile.provider_writes_authorized is True
    assert disabled.provider_writes_authorized is False
    assert profile.digest == EXPECTED_STABLE_DIGEST
    assert disabled.digest == EXPECTED_STABLE_DIGEST
    assert "provider_writes_authorized" not in profile.contract_payload()


def test_every_identity_or_schedule_field_change_still_changes_profile_digest() -> None:
    profile = load_channel_profile(SVODKA_PROFILE_PATH)
    changed_values = {
        "project_key": "svodka-other",
        "channel_username": "@another_channel",
        "channel_title": "ДРУГАЯ СВОДКА",
        "publication_id_prefix": "other-",
        "timezone": "UTC",
        "daily_verified_limit": 3,
        "state_branch": "state/another-channel",
        "concurrency_group": "another-telegram-publisher",
        "bot_token_env": "OTHER_TELEGRAM_BOT_TOKEN",
        "target_chat_id_env": "OTHER_TELEGRAM_CHAT_ID",
        "target_bot_id_env": "OTHER_TELEGRAM_BOT_ID",
        "target_bot_username_env": "OTHER_TELEGRAM_BOT_USERNAME",
    }

    for field_name, value in changed_values.items():
        assert profile.model_copy(update={field_name: value}).digest != profile.digest, field_name


def test_generic_profile_model_represents_multiple_channels_without_core_constants() -> None:
    svodka = load_channel_profile(SVODKA_PROFILE_PATH)
    lordchrist = load_channel_profile(LORDCHRIST_PROFILE_PATH)

    assert svodka.project_key == "svodka"
    assert svodka.channel_username == "@deep_info_life"
    assert svodka.state_branch == "state/svodka-telegram"
    assert svodka.daily_verified_limit == 2
    assert svodka.bot_token_env == "SVODKA_TELEGRAM_BOT_TOKEN"
    assert svodka.provider_writes_authorized is True

    assert lordchrist.project_key == "lord-god-strength"
    assert lordchrist.channel_username == "@lordchrist"
    assert lordchrist.state_branch == "state/lordchrist-telegram"
    assert lordchrist.daily_verified_limit == 1
    assert lordchrist.bot_token_env == "LORDCHRIST_TELEGRAM_BOT_TOKEN"
    assert lordchrist.provider_writes_authorized is False
    assert lordchrist.digest != svodka.digest


def test_lordchrist_profile_identity_matches_quote_production_while_cadence_is_slot_owned() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    production = json.loads(LORDCHRIST_PRODUCTION_PATH.read_text(encoding="utf-8"))

    assert production["enabled"] is True
    assert profile.project_key == production["project_key"]
    assert profile.channel_username == production["channel_username"]
    assert profile.timezone == production["timezone"]
    # The generic LordChrist profile remains the one-per-day Shorts/release contract.
    # Quote cadence is now governed independently by exact durable production slots.
    assert profile.daily_verified_limit == 1
    assert "daily_verified_limit" not in production
    assert production["max_publications_per_slot"] == 1
    assert set(production["slots"]) == {"morning", "evening"}
    assert profile.state_branch == "state/lordchrist-telegram"
    assert production["bot_id"] == 8716602202
    assert production["bot_username"] == "preaching_mp3_bot"
