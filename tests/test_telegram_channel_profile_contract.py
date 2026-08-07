from __future__ import annotations

from pathlib import Path

from video_channel_manager.telegram_channel_profile import load_channel_profile

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "content/telegram/channels/svodka.json"
EXPECTED_STABLE_DIGEST = "sha256:bbfd1a0b354a3ba874595a6397477498ba28f5dd5bdc2de298b1ef23649575d9"


def test_svodka_profile_digest_is_stable_channel_contract_not_write_gate() -> None:
    profile = load_channel_profile(PROFILE_PATH)
    activated = profile.model_copy(update={"provider_writes_authorized": True})

    assert profile.provider_writes_authorized is False
    assert activated.provider_writes_authorized is True
    assert profile.digest == EXPECTED_STABLE_DIGEST
    assert activated.digest == EXPECTED_STABLE_DIGEST
    assert "provider_writes_authorized" not in profile.contract_payload()


def test_identity_or_schedule_change_still_changes_profile_digest() -> None:
    profile = load_channel_profile(PROFILE_PATH)

    assert profile.model_copy(update={"channel_username": "@another_channel"}).digest != profile.digest
    assert profile.model_copy(update={"daily_verified_limit": 3}).digest != profile.digest
    assert profile.model_copy(update={"state_branch": "state/another-channel"}).digest != profile.digest
