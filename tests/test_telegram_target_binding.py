from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from video_channel_manager.telegram_channel_profile import load_channel_profile
from video_channel_manager.telegram_models import DispatchEnvelope
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof
from video_channel_manager.telegram_target_binding import (
    TelegramTargetBinding,
    load_target_binding,
    target_binding_from_legacy_dispatch,
    target_binding_from_proof,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/svodka.json"
LORDCHRIST_PROFILE_PATH = REPOSITORY_ROOT / "content/telegram/channels/lordchrist.json"
LORDCHRIST_BINDING_PATH = REPOSITORY_ROOT / "content/telegram/channels/lordchrist-target-binding.json"


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


def test_read_only_target_proof_can_be_frozen_as_lordchrist_binding() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    proof = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Господь Бог - Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime(2026, 8, 8, 8, 30, tzinfo=UTC),
    )

    binding = target_binding_from_proof(profile, proof)
    assert binding.project_key == profile.project_key
    assert binding.profile_sha256 == profile.digest
    assert binding.chat_id == -1001295216957
    assert binding.chat_username == "lordchrist"
    assert binding.bot_id == 8716602202
    assert binding.provider_write_performed is False
    assert binding.discovered_at_utc == proof.checked_at_utc
    assert binding.digest.startswith("sha256:")


def test_verified_legacy_dispatch_can_be_reused_as_lordchrist_binding_evidence() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    dispatch = DispatchEnvelope.model_validate(
        {
            "schema_name": "video-channel-manager.telegram-dispatch",
            "schema_version": 4,
            "project_key": "lord-god-strength",
            "channel_username": "@lordchrist",
            "queue_digest": "sha256:" + "1" * 64,
            "publication_id": "lordchrist-binding-regression",
            "sequence": 2,
            "intent_id": "binding-regression-intent",
            "workflow_run_id": "31245659459",
            "workflow_run_attempt": "1",
            "github_sha": "2" * 40,
            "github_workflow_sha": "2" * 40,
            "payload_sha256": "sha256:" + "3" * 64,
            "text": "Проверочный текст durable dispatch для теста target binding. " * 3,
            "dispatch_mode": "scheduled",
            "target": {
                "schema_name": "video-channel-manager.telegram-target-proof",
                "schema_version": 2,
                "bot_id": 8716602202,
                "bot_username": "preaching_mp3_bot",
                "chat_id": -1001295216957,
                "chat_username": "lordchrist",
                "chat_title": "† Господь Бог - Сила Моя †",
                "chat_type": "channel",
                "member_status": "administrator",
                "can_post_messages": True,
                "checked_at_utc": "2026-08-08T07:13:09.125496Z",
            },
            "prepared_at_utc": "2026-08-08T07:13:10.387473Z",
        }
    )

    binding = target_binding_from_legacy_dispatch(profile, dispatch)
    assert binding.chat_id == -1001295216957
    assert binding.bot_id == 8716602202
    assert binding.discovered_at_utc == dispatch.target.checked_at_utc
    assert binding.discovery_method == "getMe + getChat(numeric id) + getChat(@username) + getChatAdministrators"
    assert binding.provider_write_performed is False


def test_committed_lordchrist_binding_matches_production_proven_identity() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    binding = load_target_binding(LORDCHRIST_BINDING_PATH, profile)

    assert binding.profile_sha256 == "sha256:0de6ac7a664b4a7bfad6815f543357a2c78809b776f1c6a054cf2aaf9ef01ba6"
    assert binding.chat_id == -1001295216957
    assert binding.chat_username == "lordchrist"
    assert binding.bot_id == 8716602202
    assert binding.bot_username == "preaching_mp3_bot"
    assert binding.discovered_at_utc == datetime(2026, 8, 8, 7, 13, 9, 125496, tzinfo=UTC)
    assert binding.digest == "sha256:4d4bd46405080512aaf31b4ee4bbeeca22eb1703642b585efc656b8f95e15bcd"
    assert binding.provider_write_performed is False


def test_target_binding_identity_digest_survives_write_gate_change() -> None:
    profile = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    enabled = profile.model_copy(update={"provider_writes_authorized": True})

    assert profile.provider_writes_authorized is False
    assert enabled.provider_writes_authorized is True
    assert enabled.digest == profile.digest
    assert enabled.contract_payload() == profile.contract_payload()


def test_target_proof_cannot_be_bound_to_different_profile() -> None:
    lordchrist = load_channel_profile(LORDCHRIST_PROFILE_PATH)
    svodka = load_channel_profile(PROFILE_PATH)
    proof = GenericTargetProof(
        schema_name="video-channel-manager.telegram-generic-target-proof",
        schema_version=1,
        project_key=lordchrist.project_key,
        channel_username=lordchrist.channel_username,
        profile_sha256=lordchrist.digest,
        bot_id=8716602202,
        bot_username="preaching_mp3_bot",
        chat_id=-1001295216957,
        chat_username="lordchrist",
        chat_title="Господь Бог - Сила Моя",
        chat_type="channel",
        member_status="administrator",
        can_post_messages=True,
        checked_at_utc=datetime(2026, 8, 8, 8, 30, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="proof differs"):
        target_binding_from_proof(svodka, proof)
