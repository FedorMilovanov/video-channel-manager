"""Verified local Meta proxy must not allow external OAuth tunneling."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from pydantic import ValidationError

from video_channel_manager.config.settings import AppSettings
from video_channel_manager.instagram import production
from video_channel_manager.instagram.production import (
    InstagramConfigurationError,
    InstagramProviderClient,
    InstagramRuntimeConfig,
)

PROXY = "http://127.0.0.1:10808"


def _config(*, proxy: str | None = None) -> InstagramRuntimeConfig:
    return InstagramRuntimeConfig(
        login_mode="facebook",
        graph_host="https://graph.facebook.com",
        api_version="v26.0",
        account_id="17841400000000000",
        expected_username="example_creator",
        access_token="test-token",
        writes_enabled=False,
        media_allowed_hosts=(),
        timeout_seconds=10.0,
        poll_interval_seconds=0.0,
        poll_attempts=5,
        meta_proxy_url=proxy,
    )


def test_local_proxy_config_roundtrips_without_enabling_provider_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VCM_INSTAGRAM_META_PROXY_URL", PROXY)
    settings = AppSettings(
        _env_file=None,
        instagram_login_mode="facebook",
        instagram_graph_host="https://graph.facebook.com",
        instagram_graph_api_version="v26.0",
        instagram_account_id="17841400000000000",
        instagram_access_token="test-token",
    )
    config = InstagramRuntimeConfig.from_settings(settings)
    assert config.meta_proxy_url == PROXY
    assert config.writes_enabled is False


@pytest.mark.parametrize(
    "unsafe",
    [
        "https://127.0.0.1:10808",
        "http://example.com:10808",
        "http://192.168.31.1:10808",
        "http://localhost:10808",
        "http://127.0.0.1",
        "http://admin:password@127.0.0.1:10808",
        "http://127.0.0.1:10808/evil",
        "http://127.0.0.1:10808?token=secret",
        "http://127.0.0.1:65536",
        "socks5://127.0.0.1:10808",
    ],
)
def test_untrusted_proxy_settings_are_blocked_before_credentials(monkeypatch: pytest.MonkeyPatch, unsafe: str) -> None:
    monkeypatch.setenv("VCM_INSTAGRAM_META_PROXY_URL", unsafe)
    with pytest.raises(ValidationError, match="Instagram Meta proxy"):
        AppSettings(_env_file=None)
    with pytest.raises(InstagramConfigurationError, match="loopback HTTP"):
        _config(proxy=unsafe)


def test_empty_proxy_setting_keeps_existing_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VCM_INSTAGRAM_META_PROXY_URL", " ")
    assert AppSettings(_env_file=None).instagram_meta_proxy_url is None
    assert replace(_config(), meta_proxy_url=None).meta_proxy_url is None


def test_explicit_proxy_routes_graph_and_media_clients_without_ambient_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctor_args: list[dict[str, Any]] = []

    class RecordingHttpxClient:
        def __init__(self, **kwargs: Any) -> None:
            ctor_args.append(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(production.httpx, "Client", RecordingHttpxClient)
    client = InstagramProviderClient(_config(proxy=PROXY))
    try:
        assert ctor_args == [
            {"timeout": 10.0, "proxy": PROXY, "trust_env": False},
            {"timeout": 10.0, "proxy": PROXY, "trust_env": False},
        ]
    finally:
        client.close()


def test_unset_proxy_retains_legacy_network_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    ctor_args: list[dict[str, Any]] = []

    class RecordingHttpxClient:
        def __init__(self, **kwargs: Any) -> None:
            ctor_args.append(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(production.httpx, "Client", RecordingHttpxClient)
    client = InstagramProviderClient(_config())
    try:
        assert ctor_args == [{"timeout": 10.0}, {"timeout": 10.0}]
    finally:
        client.close()
