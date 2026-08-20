from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from video_channel_manager.platforms.instagram import InstagramFacebookIdentityClient, InstagramIdentityReadError
from video_channel_manager.platforms.http import RetryPolicy


USER_TOKEN = "USER_TOKEN_SECRET"
DEBUG_TOKEN = "DEBUG_AUTH_SECRET"
NOW = datetime(2026, 8, 20, 1, 0, tzinfo=UTC)


def _client(handler: httpx.MockTransport) -> InstagramFacebookIdentityClient:
    return InstagramFacebookIdentityClient(
        user_access_token=USER_TOKEN,
        debug_authorization_token=DEBUG_TOKEN,
        api_version="v23.0",
        http_client=httpx.Client(transport=handler),
        retry_policy=RetryPolicy(max_attempts=1),
        now=lambda: NOW,
    )


def test_facebook_identity_discovery_uses_provider_scopes_and_all_page_cursors() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/debug_token"):
            assert request.headers["Authorization"] == f"Bearer {DEBUG_TOKEN}"
            assert request.url.params["input_token"] == USER_TOKEN
            return httpx.Response(
                200,
                json={
                    "data": {
                        "is_valid": True,
                        "scopes": ["pages_show_list", "instagram_basic"],
                    }
                },
            )

        assert request.url.path.endswith("/me/accounts")
        assert request.headers["Authorization"] == f"Bearer {USER_TOKEN}"
        assert request.url.params["fields"] == "id,name,tasks,instagram_business_account"
        assert "access_token" not in request.url.params
        if "after" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "2002",
                            "name": "Lord God Page",
                            "tasks": ["CREATE_CONTENT"],
                            "instagram_business_account": {"id": "9002"},
                        },
                        {"id": "2999", "name": "Facebook-only Page"},
                    ],
                    "paging": {"cursors": {"after": "NEXT_CURSOR"}},
                },
            )
        assert request.url.params["after"] == "NEXT_CURSOR"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1001",
                        "name": "Poet Page",
                        "instagram_business_account": {"id": "9001"},
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    with _client(transport) as client:
        observations = client.discover()

    assert [item.instagram_professional_account_id for item in observations] == ["9001", "9002"]
    assert [item.facebook_page_id for item in observations] == ["1001", "2002"]
    assert all(item.granted_scopes == ("instagram_basic", "pages_show_list") for item in observations)
    assert all(item.observed_at == NOW for item in observations)
    assert all(item.provider_writes_authorized is False for item in observations)
    assert observations[0].account_evidence_sha256 == observations[1].account_evidence_sha256
    assert observations[0].scope_evidence_sha256 == observations[1].scope_evidence_sha256
    assert observations[0].account_evidence_sha256 != observations[0].scope_evidence_sha256
    assert len(calls) == 3


def test_facebook_identity_discovery_rejects_provider_scope_gap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/debug_token")
        return httpx.Response(200, json={"data": {"is_valid": True, "scopes": ["instagram_basic"]}})

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(InstagramIdentityReadError, match="pages_show_list"):
            client.discover()


def test_facebook_identity_discovery_rejects_duplicate_professional_account_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/debug_token"):
            return httpx.Response(
                200,
                json={"data": {"is_valid": True, "scopes": ["instagram_basic", "pages_show_list"]}},
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "1001", "instagram_business_account": {"id": "9001"}},
                    {"id": "1002", "instagram_business_account": {"id": "9001"}},
                ]
            },
        )

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(InstagramIdentityReadError, match="duplicate Professional account ID"):
            client.discover()


def test_facebook_identity_discovery_rejects_repeated_pagination_cursor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/debug_token"):
            return httpx.Response(
                200,
                json={"data": {"is_valid": True, "scopes": ["instagram_basic", "pages_show_list"]}},
            )
        return httpx.Response(
            200,
            json={
                "data": [],
                "paging": {"cursors": {"after": "SAME_CURSOR"}},
            },
        )

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(InstagramIdentityReadError, match="repeated a pagination cursor"):
            client.discover()


def test_facebook_identity_errors_and_shared_redaction_do_not_echo_tokens() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": f"bad {USER_TOKEN} {DEBUG_TOKEN}"}})

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(InstagramIdentityReadError) as exc_info:
            client.discover()
        message = str(exc_info.value)
        assert USER_TOKEN not in message
        assert DEBUG_TOKEN not in message

        redacted = client.redacted_error_context(f"Authorization: Bearer {USER_TOKEN} access_token={DEBUG_TOKEN}")
        assert USER_TOKEN not in redacted
        assert DEBUG_TOKEN not in redacted
        assert "<redacted>" in redacted
