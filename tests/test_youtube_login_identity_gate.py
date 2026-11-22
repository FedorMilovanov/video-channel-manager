"""Reauthorization must not overwrite a trusted YouTube alias before owner GET."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import video_channel_manager.cli.youtube as youtube_cli
from video_channel_manager.cli.app import app
from video_channel_manager.platforms.youtube import (
    ChannelIdentity,
    OAuthToken,
    TokenStore,
    YouTubeAccount,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
)

RUNNER = CliRunner()
POET = "UC-78ys2S3cQ3lpqgXfo-SvQ"
LORD_GOD = "UCeSJsC6go2c9pdJCuUI1BYA"


def _token(value: str, scopes: list[str]) -> OAuthToken:
    return OAuthToken(
        access_token=value,
        refresh_token="refresh-placeholder",
        scopes=scopes,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _setup(monkeypatch, tmp_path: Path, *, claimed_id: str, grant_scopes: list[str]):
    store = TokenStore(tmp_path)
    store.save_token("legendary-poet", _token("original", [YOUTUBE_READONLY_SCOPE]))
    store.save_account(
        YouTubeAccount(
            alias="legendary-poet",
            token_file=str(store.token_path("legendary-poet")),
            channels=[ChannelIdentity(channel_id=POET, title="The Legendary Poet", url="https://example.test")],
        )
    )
    original = store.token_path("legendary-poet").read_bytes()
    registry = store.registry_path.read_bytes()
    observed: list[str] = []
    monkeypatch.setattr(
        youtube_cli,
        "get_settings",
        lambda: SimpleNamespace(
            data_dir=tmp_path,
            youtube_client_secret_file=tmp_path / "client_secret.json",
            youtube_oauth_timeout_seconds=300,
        ),
    )
    monkeypatch.setattr(
        youtube_cli.InstalledClientConfig,
        "from_file",
        lambda path: SimpleNamespace(client_id="fake-only"),
    )

    class Flow:
        def __init__(self, config, *, scopes):
            observed.append("request:" + ",".join(scopes))

        def authorize(self, **kwargs):
            observed.append("oauth")
            return _token("candidate", grant_scopes)

    class Client:
        def __init__(self, *, client_config, token_store, account_alias):
            self.token_store = token_store
            self.account_alias = account_alias

        def list_my_channels(self):
            assert self.token_store.load_token(self.account_alias).access_token == "candidate"
            observed.append("google-get")
            return [
                SimpleNamespace(
                    ref=SimpleNamespace(remote_id=claimed_id),
                    title="Google channel",
                    url="https://example.test",
                )
            ]

        def close(self):
            observed.append("client-close")

    monkeypatch.setattr(youtube_cli, "InstalledOAuthFlow", Flow)
    monkeypatch.setattr(youtube_cli, "YouTubeApiClient", Client)
    return store, original, registry, observed


def test_wrong_google_identity_preserves_existing_poet_token_and_registry(monkeypatch, tmp_path: Path):
    store, original, registry, steps = _setup(
        monkeypatch, tmp_path, claimed_id=LORD_GOD, grant_scopes=[YOUTUBE_FORCE_SSL_SCOPE]
    )
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "legendary-poet", "--force", "--write"])
    assert result.exit_code == 2
    assert "different YouTube channel" in result.stdout
    assert "Neither the original token" in result.stdout
    assert store.token_path("legendary-poet").read_bytes() == original
    assert store.registry_path.read_bytes() == registry
    assert steps == ["request:" + YOUTUBE_FORCE_SSL_SCOPE, "oauth", "google-get", "client-close"]


def test_exact_channel_and_full_write_scope_replace_only_selected_alias(monkeypatch, tmp_path: Path):
    store, original, registry, steps = _setup(
        monkeypatch, tmp_path, claimed_id=POET, grant_scopes=[YOUTUBE_FORCE_SSL_SCOPE]
    )
    other_alias = "fedor-milovanov"
    store.save_token(other_alias, _token("other-original", [YOUTUBE_FORCE_SSL_SCOPE]))
    other_bytes = store.token_path(other_alias).read_bytes()
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "legendary-poet", "--force", "--write"])
    assert result.exit_code == 0, (result.stdout, result.exception)
    assert store.token_path("legendary-poet").read_bytes() != original
    assert store.load_token("legendary-poet").access_token == "candidate"
    assert YOUTUBE_FORCE_SSL_SCOPE in store.load_token("legendary-poet").scopes
    assert [ch.channel_id for ch in store.get_account("legendary-poet").channels] == [POET]
    assert store.token_path(other_alias).read_bytes() == other_bytes
    assert "google-get" in steps


def test_google_partial_scope_grant_never_replaces_existing_token(monkeypatch, tmp_path: Path):
    store, original, registry, steps = _setup(
        monkeypatch, tmp_path, claimed_id=POET, grant_scopes=[YOUTUBE_READONLY_SCOPE]
    )
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "legendary-poet", "--force", "--write"])
    assert result.exit_code == 2
    assert "did not grant" in result.stdout
    assert store.token_path("legendary-poet").read_bytes() == original
    assert store.registry_path.read_bytes() == registry
    assert "google-get" not in steps


def test_unregistered_existing_token_refuses_authorization(monkeypatch, tmp_path: Path):
    store, original, registry, steps = _setup(
        monkeypatch, tmp_path, claimed_id=POET, grant_scopes=[YOUTUBE_FORCE_SSL_SCOPE]
    )
    store.registry_path.unlink()
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "legendary-poet", "--force", "--write"])
    assert result.exit_code == 2
    assert "no trusted channel identity" in result.stdout
    assert store.token_path("legendary-poet").read_bytes() == original
    assert "oauth" not in steps


def test_missing_offline_refresh_token_refuses_persist(monkeypatch, tmp_path: Path):
    store, original, registry, steps = _setup(
        monkeypatch, tmp_path, claimed_id=POET, grant_scopes=[YOUTUBE_FORCE_SSL_SCOPE]
    )

    class FlowWithoutRefresh:
        def __init__(self, config, *, scopes):
            pass

        def authorize(self, **kwargs):
            token = _token("candidate", [YOUTUBE_FORCE_SSL_SCOPE])
            token.refresh_token = None
            return token

    monkeypatch.setattr(youtube_cli, "InstalledOAuthFlow", FlowWithoutRefresh)
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "legendary-poet", "--force", "--write"])
    assert result.exit_code == 2
    assert "did not issue an offline refresh token" in result.stdout
    assert store.token_path("legendary-poet").read_bytes() == original
    assert store.registry_path.read_bytes() == registry
    assert "google-get" not in steps
