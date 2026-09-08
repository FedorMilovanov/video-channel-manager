from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest
from pydantic import ValidationError

from video_channel_manager.config.settings import AppSettings
from video_channel_manager.instagram.production import (
    InstagramConfigurationError,
    InstagramIdentityMismatchError,
    InstagramMediaVerificationError,
    InstagramProductionError,
    InstagramProductionService,
    InstagramProviderClient,
    InstagramPublicationLedger,
    InstagramPublishManifest,
    InstagramReconciliationRequired,
    InstagramRuntimeConfig,
    InstagramWriteGateError,
    PublicationStatus,
)
from video_channel_manager.persistence import Database


ACCOUNT_ID = "17841400000000000"
USERNAME = "example_creator"
API_VERSION = "v25.0"
MEDIA_BYTES = b"verified reel bytes"
MEDIA_SHA256 = f"sha256:{hashlib.sha256(MEDIA_BYTES).hexdigest()}"
MEDIA_URL = "https://cdn.example.com/reel.mp4"


def _config(*, writes_enabled: bool = True, media_allowed_hosts: tuple[str, ...] = ("cdn.example.com",)) -> InstagramRuntimeConfig:
    return InstagramRuntimeConfig(
        login_mode="instagram",
        graph_host="https://graph.instagram.com",
        api_version=API_VERSION,
        account_id=ACCOUNT_ID,
        expected_username=USERNAME,
        access_token="test-token",
        writes_enabled=writes_enabled,
        media_allowed_hosts=media_allowed_hosts,
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        poll_attempts=2,
    )


def _manifest(*, key: str = "test.reel.001", caption: str = "Caption") -> InstagramPublishManifest:
    return InstagramPublishManifest(
        publication_key=key,
        account_id=ACCOUNT_ID,
        video_url=MEDIA_URL,
        media_sha256=MEDIA_SHA256,
        media_size_bytes=len(MEDIA_BYTES),
        media_content_type="video/mp4",
        caption=caption,
    )


@contextmanager
def _ledger() -> Iterator[InstagramPublicationLedger]:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    try:
        yield InstagramPublicationLedger(database)
    finally:
        database.close()


def _response(request: httpx.Request, status_code: int, payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(status_code, request=request, json=payload)


def _media_response(request: httpx.Request, content: bytes = MEDIA_BYTES) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        content=content,
        headers={"Content-Type": "video/mp4", "Content-Length": str(len(content))},
    )


def _provider_client(config: InstagramRuntimeConfig, handler: httpx.MockTransport) -> Iterator[InstagramProviderClient]:
    with httpx.Client(transport=handler) as graph_client, httpx.Client(transport=handler) as media_client:
        yield InstagramProviderClient(config, client=graph_client, media_client=media_client)


def test_manifest_requires_public_https_media() -> None:
    with pytest.raises(ValidationError):
        InstagramPublishManifest(
            publication_key="bad-http",
            account_id=ACCOUNT_ID,
            video_url="http://cdn.example.com/reel.mp4",
            media_sha256=MEDIA_SHA256,
            media_size_bytes=len(MEDIA_BYTES),
        )
    with pytest.raises(ValidationError):
        InstagramPublishManifest(
            publication_key="bad-local",
            account_id=ACCOUNT_ID,
            video_url="https://127.0.0.1/reel.mp4",
            media_sha256=MEDIA_SHA256,
            media_size_bytes=len(MEDIA_BYTES),
        )


def test_manifest_cover_requires_complete_integrity_contract() -> None:
    with pytest.raises(ValidationError, match="cover_url requires"):
        InstagramPublishManifest(
            publication_key="bad-cover",
            account_id=ACCOUNT_ID,
            video_url=MEDIA_URL,
            media_sha256=MEDIA_SHA256,
            media_size_bytes=len(MEDIA_BYTES),
            cover_url="https://cdn.example.com/cover.jpg",
        )


def test_runtime_config_refuses_missing_identity_token_and_version() -> None:
    settings = AppSettings(_env_file=None)
    with pytest.raises(InstagramConfigurationError, match="VCM_INSTAGRAM_GRAPH_API_VERSION"):
        InstagramRuntimeConfig.from_settings(settings)


def test_write_gate_blocks_before_any_provider_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(request, 500, {})

    config = _config(writes_enabled=False)
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        with pytest.raises(InstagramWriteGateError):
            service.publish(_manifest(), execute=True)
        assert requests == []


def test_preflight_requires_exact_provider_identity() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(request, 200, {"id": "different", "username": USERNAME})

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        with pytest.raises(InstagramIdentityMismatchError):
            service.preflight()


def test_successful_reel_publish_is_durable_and_idempotent() -> None:
    writes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cdn.example.com":
            assert "authorization" not in request.headers
            return _media_response(request)
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME, "account_type": "CREATOR"})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": [{"quota_usage": 1, "config": {"quota_total": 100}}]})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media"):
            writes.append("container")
            return _response(request, 200, {"id": "container-1"})
        if request.method == "GET" and path.endswith("/container-1"):
            return _response(request, 200, {"status_code": "FINISHED", "status": "ready"})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media_publish"):
            writes.append("publish")
            return _response(request, 200, {"id": "media-1"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        first = service.publish(_manifest(), execute=True)
        second = service.publish(_manifest(), execute=True)

        assert first.status == PublicationStatus.PUBLISHED
        assert first.provider_media_id == "media-1"
        assert second.status == PublicationStatus.PUBLISHED
        assert writes == ["container", "publish"]
        durable = ledger.get("test.reel.001")
        assert durable is not None
        assert durable.provider_container_id == "container-1"
        assert durable.provider_media_id == "media-1"
        assert durable.publish_requested_at is not None
        assert durable.published_at is not None


def test_media_sha_mismatch_is_terminal_and_causes_zero_provider_posts() -> None:
    graph_posts: list[str] = []
    wrong_bytes = b"x" * len(MEDIA_BYTES)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cdn.example.com":
            return _media_response(request, wrong_bytes)
        if request.method == "POST":
            graph_posts.append(request.url.path)
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        with pytest.raises(InstagramMediaVerificationError) as error:
            service.publish(_manifest(key="bad-sha"), execute=True)
        assert error.value.error_code == "video_sha256_mismatch"
        assert graph_posts == []
        durable = ledger.get("bad-sha")
        assert durable is not None
        assert durable.status == PublicationStatus.TERMINAL_FAILURE


def test_media_size_mismatch_is_terminal_and_causes_zero_provider_posts() -> None:
    graph_posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cdn.example.com":
            return httpx.Response(
                200,
                request=request,
                content=MEDIA_BYTES,
                headers={"Content-Type": "video/mp4", "Content-Length": str(len(MEDIA_BYTES) + 1)},
            )
        if request.method == "POST":
            graph_posts.append(request.url.path)
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        with pytest.raises(InstagramMediaVerificationError) as error:
            service.publish(_manifest(key="bad-size"), execute=True)
        assert error.value.error_code == "video_size_mismatch"
        assert graph_posts == []


def test_media_redirect_is_refused_before_provider_post() -> None:
    graph_posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cdn.example.com":
            return httpx.Response(302, request=request, headers={"Location": "https://other.example/reel.mp4"})
        if request.method == "POST":
            graph_posts.append(request.url.path)
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        with pytest.raises(InstagramMediaVerificationError) as error:
            service.publish(_manifest(key="redirect"), execute=True)
        assert error.value.error_code == "video_redirect_refused"
        assert graph_posts == []


def test_untrusted_media_host_is_refused_before_media_fetch_or_provider_post() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config(media_allowed_hosts=())
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        with pytest.raises(InstagramConfigurationError, match="VCM_INSTAGRAM_MEDIA_ALLOWED_HOSTS"):
            service.publish(_manifest(key="untrusted-host"), execute=True)
        assert all(request.method == "GET" for request in requests)
        assert all(request.url.host == "graph.instagram.com" for request in requests)


def test_unknown_publish_result_blocks_blind_retry_until_reconciliation() -> None:
    publish_calls = 0
    container_status = "FINISHED"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal publish_calls
        if request.url.host == "cdn.example.com":
            return _media_response(request)
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media"):
            return _response(request, 200, {"id": "container-ambiguous"})
        if request.method == "GET" and path.endswith("/container-ambiguous"):
            return _response(request, 200, {"status_code": container_status})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media_publish"):
            publish_calls += 1
            raise httpx.ReadTimeout("provider response lost", request=request)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)
        with pytest.raises(InstagramReconciliationRequired):
            service.publish(_manifest(key="ambiguous"), execute=True)
        unknown = ledger.get("ambiguous")
        assert unknown is not None
        assert unknown.status == PublicationStatus.PUBLISH_UNKNOWN
        assert publish_calls == 1

        with pytest.raises(InstagramReconciliationRequired):
            service.publish(_manifest(key="ambiguous"), execute=True)
        assert publish_calls == 1

        reconciled = service.reconcile("ambiguous")
        assert reconciled.status == PublicationStatus.READY
        assert publish_calls == 1


def test_reconcile_published_container_never_republishes_without_exact_media_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        if request.method == "GET" and path.endswith("/container-published"):
            return _response(request, 200, {"status_code": "PUBLISHED"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledger() as ledger, contextmanager(_provider_client)(config, transport) as client:
        manifest = _manifest(key="published-unknown")
        ledger.ensure_planned(manifest)
        ledger.transition(
            manifest.publication_key,
            PublicationStatus.PUBLISH_UNKNOWN,
            container_id="container-published",
        )
        service = InstagramProductionService(config, ledger, client=client, sleep=lambda _: None)

        unresolved = service.reconcile(manifest.publication_key)
        assert unresolved.status == PublicationStatus.PUBLISHED_UNRESOLVED
        with pytest.raises(InstagramReconciliationRequired):
            service.publish(manifest, execute=True)

        resolved = service.reconcile(manifest.publication_key, published_media_id="media-exact-evidence")
        assert resolved.status == PublicationStatus.PUBLISHED
        assert resolved.provider_media_id == "media-exact-evidence"


def test_publication_key_cannot_be_rebound_to_different_content() -> None:
    with _ledger() as ledger:
        ledger.ensure_planned(_manifest(key="stable", caption="one"))
        with pytest.raises(InstagramProductionError, match="different canonical content"):
            ledger.ensure_planned(_manifest(key="stable", caption="two"))
