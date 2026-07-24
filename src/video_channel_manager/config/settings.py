from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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
    vk_api_version: str = "5.199"

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    def ensure_runtime_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "exports").mkdir(exist_ok=True)
        (self.data_dir / "imports").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        (self.data_dir / "secrets").mkdir(exist_ok=True)
        (self.data_dir / "youtube").mkdir(exist_ok=True)
        (self.data_dir / "vk").mkdir(exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
