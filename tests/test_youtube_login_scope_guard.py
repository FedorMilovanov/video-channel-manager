"""The YouTube OAuth CLI must fail closed on a partially granted Google consent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import video_channel_manager.cli.youtube as youtube_cli
from video_channel_manager.cli.app import app
from video_channel_manager.platforms.youtube.models import OAuthToken
from video_channel_manager.platforms.youtube.oauth import YOUTUBE_FORCE_SSL_SCOPE, YOUTUBE_READONLY_SCOPE
from video_channel_manager.platforms.youtube.store import TokenStore

RUNNER = CliRunner()
MILOVI_CHANNEL = "UCMDnxfGZiBqcDzgUV1zjFpw"


def _token(access_token: str, scopes: list[str]) -> OAuthToken:
    return OAuthToken(
        access_token=access_token,
        refresh_token="dummy-refresh",
        scopes=scopes,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, received_token: OAuthToken) -> tuple[TokenStore, dict]:
    store = TokenStore(tmp_path)
    store.save_token("milovi-cake", _token("existing-readonly", [YOUTUBE_READONLY_SCOPE]))
    calls: dict[str, object] = {"clients": 0, "requested_scopes": ()}
    monkeypatch.setattr(
        youtube_cli,
        "get_settings",
        lambda: SimpleNamespace(
            data_dir=tmp_path,
            youtube_client_secret_file=tmp_path / "fake-desktop-client.json",
            youtube_oauth_timeout_seconds=10,
        ),
    )
    monkeypatch.setattr(
        youtube_cli,
        "InstalledClientConfig",
        SimpleNamespace(from_file=lambda _path: object()),
    )

    class FakeFlow:
        def __init__(self, _config: object, *, scopes: tuple[str, ...]) -> None:
            calls["requested_scopes"] = scopes

        def authorize(self, **_kwargs: object) -> OAuthToken:
            return received_token

    class FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            calls["clients"] = int(calls["clients"]) + 1

        def list_my_channels(self) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    ref=SimpleNamespace(remote_id=MILOVI_CHANNEL),
                    title="Milovi Cake",
                    url=f"https://www.youtube.com/channel/{MILOVI_CHANNEL}",
                )
            ]

    monkeypatch.setattr(youtube_cli, "InstalledOAuthFlow", FakeFlow)
    monkeypatch.setattr(youtube_cli, "YouTubeApiClient", FakeClient)
    return store, calls


def test_denied_write_scope_fails_without_replacing_existing_token_or_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, calls = _install(monkeypatch, tmp_path, _token("unapproved-grant", [YOUTUBE_READONLY_SCOPE]))
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "milovi-cake", "--write", "--force"])

    assert result.exit_code == 2, (result.stdout, result.exception)
    assert "did not grant the requested YouTube write access" in result.stdout
    assert "No account token was saved or replaced" in result.stdout
    assert "Authorized YouTube account alias" not in result.stdout
    assert store.load_token("milovi-cake").access_token == "existing-readonly"
    assert not store.registry_path.exists()
    assert calls["requested_scopes"] == (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE)
    assert calls["clients"] == 0


def test_full_write_consent_persists_and_confirms_expected_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    granted = _token("new-write", [YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE])
    store, calls = _install(monkeypatch, tmp_path, granted)
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "milovi-cake", "--write", "--force"])

    assert result.exit_code == 0, (result.stdout, result.exception)
    assert "guarded write" in result.stdout
    assert MILOVI_CHANNEL in result.stdout
    assert store.load_token("milovi-cake").scopes == [YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE]
    assert store.get_account("milovi-cake").channels[0].channel_id == MILOVI_CHANNEL
    assert calls["clients"] == 1


def test_read_only_consent_remains_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, calls = _install(monkeypatch, tmp_path, _token("new-readonly", [YOUTUBE_READONLY_SCOPE]))
    result = RUNNER.invoke(app, ["youtube", "login", "--account", "milovi-cake", "--force"])

    assert result.exit_code == 0, (result.stdout, result.exception)
    assert "read-only" in result.stdout
    assert store.load_token("milovi-cake").access_token == "new-readonly"
    assert calls["requested_scopes"] == (YOUTUBE_READONLY_SCOPE,)
