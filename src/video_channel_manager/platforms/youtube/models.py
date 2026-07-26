from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator

from video_channel_manager.domain.models import StrictModel


class YouTubeConfigurationError(ValueError):
    """Raised when the downloaded Google OAuth client file is invalid."""


class InstalledClientConfig(StrictModel):
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    auth_uri: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    redirect_uris: list[str] = Field(default_factory=lambda: ["http://localhost"])

    @classmethod
    def from_file(cls, path: Path) -> "InstalledClientConfig":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            raise YouTubeConfigurationError(f"Cannot read OAuth client file: {path}") from exc
        except json.JSONDecodeError as exc:
            raise YouTubeConfigurationError(f"OAuth client file is not valid JSON: {path}") from exc

        installed = payload.get("installed") if isinstance(payload, dict) else None
        if not isinstance(installed, dict):
            client_type = "web" if isinstance(payload, dict) and isinstance(payload.get("web"), dict) else "unknown"
            if client_type == "web":
                raise YouTubeConfigurationError(
                    "This is a Google OAuth 'Web application' client. Create/download a client of type 'Desktop app'."
                )
            raise YouTubeConfigurationError(
                "Expected a Google OAuth client of type 'Desktop app' with a top-level 'installed' object."
            )

        required_fields = ("client_id", "client_secret")
        missing_fields = [name for name in required_fields if not str(installed.get(name) or "").strip()]
        if missing_fields:
            names = ", ".join(missing_fields)
            raise YouTubeConfigurationError(f"OAuth Desktop client file is missing required field(s): {names}.")

        # Google includes harmless metadata such as project_id and
        # auth_provider_x509_cert_url. Keep our runtime model strict while
        # explicitly selecting only OAuth fields that the application uses.
        supported_fields = ("client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris")
        normalized = {name: installed[name] for name in supported_fields if name in installed}
        try:
            return cls.model_validate(normalized)
        except Exception as exc:
            raise YouTubeConfigurationError(
                "OAuth Desktop client fields have invalid values; download the JSON again from Google Cloud."
            ) from exc


class OAuthToken(StrictModel):
    access_token: str = Field(min_length=1)
    refresh_token: str | None = None
    token_type: str = "Bearer"
    scopes: list[str] = Field(default_factory=list)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime

    @field_validator("scopes", mode="before")
    @classmethod
    def normalize_scopes(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item for item in value.split() if item]
        if isinstance(value, list):
            return [str(item) for item in value]
        raise ValueError("scopes must be a space-separated string or a list")

    @model_validator(mode="after")
    def normalize_datetimes(self) -> "OAuthToken":
        if self.issued_at.tzinfo is None:
            self.issued_at = self.issued_at.replace(tzinfo=UTC)
        if self.expires_at.tzinfo is None:
            self.expires_at = self.expires_at.replace(tzinfo=UTC)
        return self

    @classmethod
    def from_token_response(
        cls,
        payload: dict[str, Any],
        *,
        previous_refresh_token: str | None = None,
        previous_scopes: list[str] | None = None,
    ) -> "OAuthToken":
        now = datetime.now(UTC)
        expires_in = int(payload.get("expires_in", 3600))
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=payload.get("refresh_token") or previous_refresh_token,
            token_type=str(payload.get("token_type", "Bearer")),
            scopes=payload.get("scope", previous_scopes or []),
            issued_at=now,
            expires_at=now + timedelta(seconds=max(expires_in, 0)),
        )

    def needs_refresh(self, *, leeway_seconds: int = 90) -> bool:
        return datetime.now(UTC) + timedelta(seconds=leeway_seconds) >= self.expires_at


class ChannelIdentity(StrictModel):
    channel_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str


class YouTubeAccount(StrictModel):
    alias: str = Field(min_length=1, max_length=64)
    token_file: str = Field(min_length=1)
    channels: list[ChannelIdentity] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
