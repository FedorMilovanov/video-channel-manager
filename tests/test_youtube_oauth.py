from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken
from video_channel_manager.platforms.youtube.oauth import InstalledOAuthFlow, YOUTUBE_READONLY_SCOPE


def _config(tmp_path: Path) -> InstalledClientConfig:
    path = tmp_path / "client_secret.json"
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "desktop.apps.googleusercontent.com",
                    "client_secret": "secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )
    return InstalledClientConfig.from_file(path)


def test_desktop_client_config_and_authorization_url(tmp_path: Path) -> None:
    config = _config(tmp_path)
    flow = InstalledOAuthFlow(config)
    url = flow.build_authorization_url(
        redirect_uri="http://127.0.0.1:4567/oauth2/callback",
        state="state-value",
        code_verifier="verifier-value",
        force_consent=True,
    )
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == [config.client_id]
    assert query["scope"] == [YOUTUBE_READONLY_SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["code_challenge_method"] == ["S256"]
    assert "client_secret" not in query


def test_exchange_and_refresh_preserve_refresh_token(tmp_path: Path) -> None:
    config = _config(tmp_path)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = request.content.decode()
        if "grant_type=authorization_code" in body:
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                    "scope": YOUTUBE_READONLY_SCOPE,
                    "token_type": "Bearer",
                },
            )
        return httpx.Response(
            200,
            json={"access_token": "access-2", "expires_in": 3600, "scope": YOUTUBE_READONLY_SCOPE},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    flow = InstalledOAuthFlow(config, http_client=client)
    token = flow.exchange_code(code="code", redirect_uri="http://127.0.0.1/callback", code_verifier="verifier")
    refreshed = flow.refresh(token)
    assert token.refresh_token == "refresh-1"
    assert refreshed.access_token == "access-2"
    assert refreshed.refresh_token == "refresh-1"
    assert len(requests) == 2


def test_needs_refresh_uses_leeway() -> None:
    token = OAuthToken(
        access_token="a",
        refresh_token="r",
        expires_at=datetime.now(UTC) + timedelta(seconds=30),
    )
    assert token.needs_refresh(leeway_seconds=90)
