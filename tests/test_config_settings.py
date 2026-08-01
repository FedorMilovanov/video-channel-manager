from __future__ import annotations

from pathlib import Path

from video_channel_manager.config.settings import get_settings


def _reset_settings_cache() -> None:
    get_settings.cache_clear()


def test_external_vk_env_supplies_token_when_primary_setting_is_absent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shared_env = tmp_path / "shared-vk.env"
    shared_env.write_text("VK_API_TOKEN=external-token\n", encoding="utf-8")
    monkeypatch.delenv("VCM_VK_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("VCM_VK_SHARED_ENV_FILE", str(shared_env))
    _reset_settings_cache()

    settings = get_settings()

    assert settings.vk_access_token is not None
    assert settings.vk_access_token.get_secret_value() == "external-token"
    _reset_settings_cache()


def test_primary_vcm_vk_setting_wins_over_external_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shared_env = tmp_path / "shared-vk.env"
    shared_env.write_text("VK_API_TOKEN=external-token\n", encoding="utf-8")
    monkeypatch.setenv("VCM_VK_ACCESS_TOKEN", "primary-token")
    monkeypatch.setenv("VCM_VK_SHARED_ENV_FILE", str(shared_env))
    _reset_settings_cache()

    settings = get_settings()

    assert settings.vk_access_token is not None
    assert settings.vk_access_token.get_secret_value() == "primary-token"
    _reset_settings_cache()


def test_missing_external_vk_env_keeps_token_unset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("VCM_VK_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("VCM_VK_SHARED_ENV_FILE", str(tmp_path / "missing.env"))
    _reset_settings_cache()

    settings = get_settings()

    assert settings.vk_access_token is None
    _reset_settings_cache()
