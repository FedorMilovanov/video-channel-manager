from __future__ import annotations

import httpx

from video_channel_manager.instagram.production import InstagramProviderClient, InstagramRuntimeConfig


ACCOUNT_ID = "17841435926122104"
USERNAME = "the.legendary.poet"


def _facebook_config() -> InstagramRuntimeConfig:
    return InstagramRuntimeConfig(
        login_mode="facebook",
        graph_host="https://graph.facebook.com",
        api_version="v26.0",
        account_id=ACCOUNT_ID,
        expected_username=USERNAME,
        access_token="test-page-token",
        writes_enabled=False,
        media_allowed_hosts=(),
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        poll_attempts=1,
    )


def test_facebook_identity_probe_requests_only_required_supported_fields() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path == f"/v26.0/{ACCOUNT_ID}"
        assert request.url.params.get("fields") == "id,username"
        return httpx.Response(
            200,
            request=request,
            json={"id": ACCOUNT_ID, "username": USERNAME},
        )

    config = _facebook_config()
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as graph_client, httpx.Client(transport=transport) as media_client:
        client = InstagramProviderClient(config, client=graph_client, media_client=media_client)
        identity = client.get_account_identity()

    assert identity == {"id": ACCOUNT_ID, "username": USERNAME}
    assert len(requests) == 1
