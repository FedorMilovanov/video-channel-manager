from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.telegram_channel_profile import TelegramChannelProfile
from video_channel_manager.telegram_models import DispatchEnvelope
from video_channel_manager.telegram_multichannel_transport import GenericTargetProof

DiscoveryMethod = Literal[
    "getMe + getChat(@username) + getChat(numeric id) + getChatAdministrators",
    "getMe + getChat(numeric id) + getChat(@username) + getChatAdministrators",
]


class TelegramTargetBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-target-binding"]
    schema_version: Literal[1]
    project_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    channel_username: str = Field(pattern=r"^@[A-Za-z0-9_]{5,32}$")
    profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    chat_id: int = Field(lt=0)
    chat_username: str = Field(min_length=5, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    bot_id: int = Field(gt=0)
    bot_username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    can_post_messages: Literal[True]
    discovered_at_utc: datetime
    discovery_method: DiscoveryMethod
    provider_write_performed: Literal[False]

    @model_validator(mode="after")
    def validate_binding(self) -> "TelegramTargetBinding":
        if self.discovered_at_utc.tzinfo is None:
            raise ValueError("target binding discovery timestamp must be timezone-aware")
        if self.chat_username.casefold() != self.channel_username.removeprefix("@").casefold():
            raise ValueError("target binding numeric chat and public username disagree")
        return self

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _binding(
    profile: TelegramChannelProfile,
    *,
    chat_id: int,
    chat_username: str,
    bot_id: int,
    bot_username: str,
    checked_at_utc: datetime,
    discovery_method: DiscoveryMethod,
) -> TelegramTargetBinding:
    if chat_username.casefold() != profile.bare_username.casefold():
        raise ValueError("Telegram target proof differs from selected channel profile")
    return TelegramTargetBinding(
        schema_name="video-channel-manager.telegram-target-binding",
        schema_version=1,
        project_key=profile.project_key,
        channel_username=profile.channel_username,
        profile_sha256=profile.digest,
        chat_id=chat_id,
        chat_username=chat_username,
        bot_id=bot_id,
        bot_username=bot_username,
        can_post_messages=True,
        discovered_at_utc=checked_at_utc,
        discovery_method=discovery_method,
        provider_write_performed=False,
    )


def target_binding_from_proof(
    profile: TelegramChannelProfile,
    proof: GenericTargetProof,
) -> TelegramTargetBinding:
    if (
        proof.project_key != profile.project_key
        or proof.channel_username.casefold() != profile.channel_username.casefold()
        or proof.profile_sha256 != profile.digest
        or proof.chat_username.casefold() != profile.bare_username.casefold()
        or proof.chat_type != "channel"
        or proof.can_post_messages is not True
    ):
        raise ValueError("Telegram target proof differs from selected channel profile")
    return _binding(
        profile,
        chat_id=proof.chat_id,
        chat_username=proof.chat_username,
        bot_id=proof.bot_id,
        bot_username=proof.bot_username,
        checked_at_utc=proof.checked_at_utc,
        discovery_method="getMe + getChat(@username) + getChat(numeric id) + getChatAdministrators",
    )


def target_binding_from_legacy_dispatch(
    profile: TelegramChannelProfile,
    dispatch: DispatchEnvelope,
) -> TelegramTargetBinding:
    proof = dispatch.target
    if (
        dispatch.project_key != profile.project_key
        or dispatch.channel_username.casefold() != profile.channel_username.casefold()
        or proof.chat_username.casefold() != profile.bare_username.casefold()
        or proof.chat_type != "channel"
        or proof.can_post_messages is not True
    ):
        raise ValueError("legacy Telegram dispatch proof differs from selected channel profile")
    return _binding(
        profile,
        chat_id=proof.chat_id,
        chat_username=proof.chat_username,
        bot_id=proof.bot_id,
        bot_username=proof.bot_username,
        checked_at_utc=proof.checked_at_utc,
        discovery_method="getMe + getChat(numeric id) + getChat(@username) + getChatAdministrators",
    )


def load_target_binding(path: Path, profile: TelegramChannelProfile) -> TelegramTargetBinding:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        binding = TelegramTargetBinding.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram target binding {path}: {exc}") from exc

    if (
        binding.project_key != profile.project_key
        or binding.channel_username.casefold() != profile.channel_username.casefold()
        or binding.profile_sha256 != profile.digest
        or binding.chat_username.casefold() != profile.bare_username.casefold()
    ):
        raise ValueError("Telegram target binding differs from selected channel profile")
    return binding
