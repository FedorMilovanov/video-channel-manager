from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Typed application configuration loaded from VCM_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="VCM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    log_level: str = "INFO"
    data_dir: Path = Path("./data")
    database_url: str = "sqlite:///./data/video_manager.db"

    safe_mode: bool = True
    allow_destructive_operations: bool = False
    max_operations_per_plan: int = Field(default=1000, ge=1, le=100_000)
    require_expected_revision: bool = True

    youtube_client_secret_file: Path = Path("./secrets/client_secret.json")
    youtube_oauth_timeout_seconds: int = Field(default=300, ge=30, le=1800)
    youtube_client_id: str | None = None
    youtube_client_secret: SecretStr | None = None
    youtube_token_file: Path = Path("./data/secrets/youtube-token.json")

    vk_app_id: str | None = None
    vk_access_token: SecretStr | None = None
    vk_shared_env_file: Path = Field(default_factory=lambda: Path.home() / "Projects" / "mp3telegrambot" / ".env")
    vk_api_version: str = "5.199"

    # Instagram production publishing is intentionally disabled by default.
    # Credentials are secrets and must only arrive through VCM_* environment
    # configuration or an external secret store that populates the environment.
    instagram_login_mode: Literal["instagram", "facebook"] = "instagram"
    instagram_graph_host: str = "https://graph.instagram.com"
    instagram_graph_api_version: str | None = None
    instagram_account_id: str | None = None
    instagram_account_username: str | None = None
    instagram_access_token: SecretStr | None = None
    instagram_writes_enabled: bool = False
    instagram_media_allowed_hosts: tuple[str, ...] = ()
    instagram_request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    instagram_poll_interval_seconds: float = Field(default=5.0, ge=0, le=60)
    instagram_poll_attempts: int = Field(default=24, ge=1, le=120)

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("instagram_graph_host")
    @classmethod
    def validate_instagram_graph_host(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        allowed = {"https://graph.instagram.com", "https://graph.facebook.com"}
        if normalized not in allowed:
            raise ValueError(f"Instagram Graph host must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("instagram_graph_api_version", "instagram_account_id", "instagram_account_username")
    @classmethod
    def normalize_optional_instagram_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("instagram_media_allowed_hosts")
    @classmethod
    def normalize_instagram_media_allowed_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(host.strip().lower().rstrip(".") for host in value if host.strip())
        if len(set(normalized)) != len(normalized):
            raise ValueError("Instagram media allowed hosts must not contain duplicates")
        for host in normalized:
            if "://" in host or "/" in host or host == "localhost":
                raise ValueError("Instagram media allowed hosts must be bare public hostnames")
            try:
                address = __import__("ipaddress").ip_address(host)
            except ValueError:
                continue
            if not address.is_global:
                raise ValueError("Instagram media allowed hosts must not contain private or local IP addresses")
        return normalized

    def ensure_runtime_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "exports").mkdir(exist_ok=True)
        (self.data_dir / "imports").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        (self.data_dir / "secrets").mkdir(exist_ok=True)
        (self.data_dir / "youtube").mkdir(exist_ok=True)
        (self.data_dir / "vk").mkdir(exist_ok=True)
        (self.data_dir / "instagram").mkdir(exist_ok=True)


def _read_shared_vk_access_token(path: Path) -> SecretStr | None:
    """Read VK_API_TOKEN from an external .env without logging secret material."""

    try:
        values = dotenv_values(path, encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    raw_value = values.get("VK_API_TOKEN")
    if not isinstance(raw_value, str):
        return None
    value = raw_value.strip()
    return SecretStr(value) if value else None


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    settings = AppSettings()
    if settings.vk_access_token is not None:
        return settings
    shared_token = _read_shared_vk_access_token(settings.vk_shared_env_file)
    if shared_token is None:
        return settings
    return settings.model_copy(update={"vk_access_token": shared_token})
