from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_target_binding import TelegramTargetBinding, load_target_binding

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"


def binding_payload(profile_sha256: str) -> dict[str, object]:
    return {
        "schema_name": "video-channel-manager.telegram-target-binding",
        "schema_version": 1,
        "project_key": "svodka",
        "channel_username": "@deep_info_life",
        "profile_sha256": profile_sha256,
        "chat_id": -1002233445566,
        "chat_username": "deep_info_life",
        "bot_id": 8716602202,
        "bot_username": "preaching_mp3_bot",
        "can_post_messages": True,
        "discovered_at_utc": datetime(2026, 8, 8, 0, 30, tzinfo=UTC).isoformat(),
        "discovery_method": "getMe + getChat(@username) + getChat(numeric id) + getChatAdministrators",
        "provider_write_performed": False,
    }


def test_target_binding_is_profile_bound_and_digest_stable(tmp_path: Path) -> None:
    profile = load_channel_profile(PROFILE_PATH)
    payload = binding_payload(profile.digest)
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    binding = load_target_binding(path, profile)
    assert binding.chat_id == -1002233445566
    assert binding.bot_id == 8716602202
    assert binding.can_post_messages is True
    assert binding.provider_write_performed is False
    assert binding.digest == TelegramTargetBinding.model_validate(payload).digest


def test_target_binding_rejects_username_or_profile_drift(tmp_path: Path) -> None:
    profile = load_channel_profile(PROFILE_PATH)

    bad_username = deepcopy(binding_payload(profile.digest))
    bad_username["chat_username"] = "other_channel"
    path = tmp_path / "bad-username.json"
    path.write_text(json.dumps(bad_username), encoding="utf-8")
    with pytest.raises(ValueError, match="numeric chat and public username disagree"):
        load_target_binding(path, profile)

    bad_digest = deepcopy(binding_payload(profile.digest))
    bad_digest["profile_sha256"] = "sha256:" + "0" * 64
    path = tmp_path / "bad-digest.json"
    path.write_text(json.dumps(bad_digest), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from selected channel profile"):
        load_target_binding(path, profile)
