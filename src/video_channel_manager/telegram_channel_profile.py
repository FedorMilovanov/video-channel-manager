from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class TelegramChannelProfile(BaseModel):
    """Channel-specific identity and safety configuration for generic Telegram tooling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-channel-profile"]
    schema_version: Literal[1]
    project_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    channel_username: str = Field(pattern=r"^@[A-Za-z0-9_]{5,32}$")
    channel_title: str = Field(min_length=1, max_length=255)
    publication_id_prefix: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}-$")
    timezone: str = Field(min_length=3, max_length=80)
    daily_verified_limit: int = Field(ge=1, le=20)
    state_branch: str = Field(pattern=r"^state/[A-Za-z0-9._/-]+$")
    concurrency_group: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    bot_token_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    target_chat_id_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    target_bot_id_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    target_bot_username_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    provider_writes_authorized: bool = False

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    @property
    def bare_username(self) -> str:
        return self.channel_username.removeprefix("@")

    @property
    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_channel_profile(path: Path) -> TelegramChannelProfile:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return TelegramChannelProfile.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Telegram channel profile {path}: {exc}") from exc
