from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from video_channel_manager.platforms.http import HttpClientOwner
from video_channel_manager.platforms.youtube.models import InstalledClientConfig, OAuthToken

YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_FORCE_SSL_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


class OAuthFlowError(RuntimeError):
    pass


@dataclass(slots=True)
class CallbackResult:
    code: str | None = None
    error: str | None = None
    state: str | None = None


class InstalledOAuthFlow(HttpClientOwner):
    """OAuth 2.0 Desktop flow using PKCE and a loopback callback server."""

    def __init__(
        self,
        config: InstalledClientConfig,
        *,
        scopes: tuple[str, ...] = (YOUTUBE_READONLY_SCOPE,),
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.scopes = scopes
        self._initialize_http_client(
            http_client,
            timeout=30.0,
            follow_redirects=True,
        )

    def build_authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        code_verifier: str,
        force_consent: bool,
    ) -> str:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest()).rstrip(b"=")
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "state": state,
            "code_challenge": challenge.decode("ascii"),
            "code_challenge_method": "S256",
        }
        if force_consent:
            params["prompt"] = "consent"
        return f"{self.config.auth_uri}?{urlencode(params)}"

    def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str) -> OAuthToken:
        try:
            response = self._http_client.post(
                self.config.token_uri,
                data={
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "code": code,
                    "code_verifier": code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise OAuthFlowError(f"Google token exchange failed: {exc}") from exc
        try:
            return OAuthToken.from_token_response(payload, previous_scopes=list(self.scopes))
        except (KeyError, TypeError, ValueError) as exc:
            raise OAuthFlowError("Google token response did not contain a usable access token.") from exc

    def refresh(self, token: OAuthToken) -> OAuthToken:
        if not token.refresh_token:
            raise OAuthFlowError("Stored credentials do not contain a refresh token; run youtube login again.")
        try:
            response = self._http_client.post(
                self.config.token_uri,
                data={
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "refresh_token": token.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            payload = response.json()
            return OAuthToken.from_token_response(
                payload,
                previous_refresh_token=token.refresh_token,
                previous_scopes=token.scopes,
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise OAuthFlowError(f"Google access-token refresh failed: {exc}") from exc

    def authorize(
        self,
        *,
        timeout_seconds: int = 300,
        force_consent: bool = True,
        open_browser: Callable[[str], bool] = webbrowser.open,
        on_authorization_url: Callable[[str], None] | None = None,
    ) -> OAuthToken:
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        result = CallbackResult()
        result_event = threading.Event()

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path != "/oauth2/callback":
                    self.send_error(404)
                    return
                query = parse_qs(parsed.query)
                result.code = query.get("code", [None])[0]
                result.error = query.get("error", [None])[0]
                result.state = query.get("state", [None])[0]
                message = (
                    "Authorization received. You can close this window and return to Video Channel Manager."
                    if result.code
                    else "Authorization failed. Return to Video Channel Manager for details."
                )
                body = f"<html><body><h2>{message}</h2></body></html>".encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                result_event.set()

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
        server.timeout = 0.5
        port = int(server.server_address[1])
        redirect_uri = f"http://127.0.0.1:{port}/oauth2/callback"
        authorization_url = self.build_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=code_verifier,
            force_consent=force_consent,
        )
        if on_authorization_url is not None:
            on_authorization_url(authorization_url)
        open_browser(authorization_url)

        deadline = time.monotonic() + timeout_seconds
        try:
            while not result_event.is_set() and time.monotonic() < deadline:
                server.handle_request()
        finally:
            server.server_close()

        if not result_event.is_set():
            raise OAuthFlowError(f"OAuth authorization timed out after {timeout_seconds} seconds.")
        if result.state != state:
            raise OAuthFlowError("OAuth state mismatch; authorization was rejected for safety.")
        if result.error:
            raise OAuthFlowError(f"Google authorization failed: {result.error}")
        if not result.code:
            raise OAuthFlowError("Google authorization callback did not include an authorization code.")
        return self.exchange_code(code=result.code, redirect_uri=redirect_uri, code_verifier=code_verifier)
