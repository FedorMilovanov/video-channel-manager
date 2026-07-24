from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pydantic import Field

from video_channel_manager.domain.models import StrictModel


class VkConfigurationError(ValueError):
    """Raised when a VK token input cannot be parsed safely."""


class VkAccessToken(StrictModel):
    access_token: str = Field(min_length=1, repr=False)
    user_id: int | None = Field(default=None, ge=1)
    token_type: str = "user"
    scopes: list[str] = Field(default_factory=lambda: ["video", "groups"])
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    @classmethod
    def from_text(cls, raw: str) -> "VkAccessToken":
        value = raw.strip()
        if not value:
            raise VkConfigurationError("VK access token is blank.")

        if value.startswith("{"):
            try:
                payload = json.loads(value)
            except json.JSONDecodeError as exc:
                raise VkConfigurationError("VK token JSON is invalid.") from exc
            if not isinstance(payload, dict):
                raise VkConfigurationError("VK token JSON must be an object.")
            return cls.model_validate(payload)

        if "access_token=" in value:
            parsed = urlparse(value)
            parameters = parse_qs(parsed.fragment or parsed.query)
            token_values = parameters.get("access_token")
            if not token_values:
                raise VkConfigurationError("The pasted VK redirect URL does not contain access_token.")
            expires_at: datetime | None = None
            expires_values = parameters.get("expires_in")
            if expires_values:
                try:
                    expires_in = int(expires_values[0])
                except ValueError as exc:
                    raise VkConfigurationError("VK expires_in is not an integer.") from exc
                if expires_in > 0:
                    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
            user_id: int | None = None
            user_values = parameters.get("user_id")
            if user_values:
                try:
                    user_id = int(user_values[0])
                except ValueError as exc:
                    raise VkConfigurationError("VK user_id is not an integer.") from exc
            return cls(access_token=token_values[0], user_id=user_id, expires_at=expires_at)

        return cls(access_token=value)

    @classmethod
    def from_file(cls, path: Path) -> "VkAccessToken":
        try:
            return cls.from_text(path.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            raise VkConfigurationError(f"Cannot read VK token file: {path}") from exc

    def is_expired(self, *, leeway_seconds: int = 60) -> bool:
        if self.expires_at is None:
            return False
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return datetime.now(UTC) + timedelta(seconds=leeway_seconds) >= expires_at


class VkUserIdentity(StrictModel):
    user_id: int = Field(ge=1)
    display_name: str = Field(min_length=1)
    screen_name: str | None = None


class VkCommunityIdentity(StrictModel):
    community_id: int = Field(ge=1)
    title: str = Field(min_length=1)
    screen_name: str | None = None
    url: str = Field(min_length=1)


class VkAccount(StrictModel):
    alias: str = Field(min_length=1, max_length=64)
    token_file: str = Field(min_length=1)
    user: VkUserIdentity
    communities: list[VkCommunityIdentity] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
