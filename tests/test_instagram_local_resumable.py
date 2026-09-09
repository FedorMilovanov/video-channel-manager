from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from video_channel_manager.instagram.local_resumable import (
    InstagramLocalResumableService,
    InstagramResumableProviderClient,
    InstagramResumableUploadLedger,
    ResumableUploadState,
    build_local_publish_manifest,
)
from video_channel_manager.instagram.production import (
    InstagramProductionError,
    InstagramProviderError,
    InstagramPublicationLedger,
    InstagramReconciliationRequired,
    InstagramRuntimeConfig,
    InstagramWriteGateError,
    PublicationStatus,
)
from video_channel_manager.persistence import Database


ACCOUNT_ID = "17841400000000000"
USERNAME = "example_creator"
API_VERSION = "v25.0"
TOKEN = "test-token"
VIDEO_BYTES = b"local resumable reel bytes"
UPLOAD_URI = "https://rupload.facebook.com/ig-api-upload/v25.0/container-local-1"


def _config(*, writes_enabled: bool = True) -> InstagramRuntimeConfig:
    return InstagramRuntimeConfig(
        login_mode="facebook",
        graph_host="https://graph.facebook.com",
        api_version=API_VERSION,
        account_id=ACCOUNT_ID,
        expected_username=USERNAME,
        access_token=TOKEN,
        writes_enabled=writes_enabled,
        media_allowed_hosts=(),
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        poll_attempts=2,
    )


@contextmanager
def _ledgers() -> Iterator[tuple[InstagramPublicationLedger, InstagramResumableUploadLedger, Database]]:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    try:
        yield InstagramPublicationLedger(database), InstagramResumableUploadLedger(database), database
    finally:
        database.close()


@contextmanager
def _client(
    config: InstagramRuntimeConfig,
    transport: httpx.MockTransport,
) -> Iterator[InstagramResumableProviderClient]:
    with httpx.Client(transport=transport) as graph_client, httpx.Client(transport=transport) as media_client:
        yield InstagramResumableProviderClient(config, client=graph_client, media_client=media_client)


def _write_video(path: Path, content: bytes = VIDEO_BYTES) -> None:
    path.write_bytes(content)


def _response(request: httpx.Request, status_code: int, payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(status_code, request=request, json=payload)


def test_local_manifest_binds_bytes_but_not_filesystem_path(tmp_path: Path) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    _write_video(first)
    _write_video(second)

    first_manifest = build_local_publish_manifest(
        first,
        publication_key="local.identity.001",
        account_id=ACCOUNT_ID,
        caption="Caption",
    )
    second_manifest = build_local_publish_manifest(
        second,
        publication_key="local.identity.001",
        account_id=ACCOUNT_ID,
        caption="Caption",
    )

    assert first_manifest.content_hash() == second_manifest.content_hash()
    assert first_manifest.media_sha256 == second_manifest.media_sha256
    assert "first.mp4" not in first_manifest.model_dump_json()
    assert "second.mp4" not in second_manifest.model_dump_json()


def test_same_publication_key_rejects_changed_local_bytes(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    _write_video(video, b"first bytes")
    first = build_local_publish_manifest(video, publication_key="local.binding.001", account_id=ACCOUNT_ID)

    with _ledgers() as (ledger, _upload_ledger, _database):
        ledger.ensure_planned(first)  # type: ignore[arg-type]
        _write_video(video, b"different bytes")
        second = build_local_publish_manifest(video, publication_key="local.binding.001", account_id=ACCOUNT_ID)
        with pytest.raises(InstagramProductionError, match="already bound"):
            ledger.ensure_planned(second)  # type: ignore[arg-type]


def test_kill_switch_blocks_before_any_provider_request(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    _write_video(video)
    manifest = build_local_publish_manifest(video, publication_key="local.kill-switch", account_id=ACCOUNT_ID)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(request, 500, {})

    config = _config(writes_enabled=False)
    transport = httpx.MockTransport(handler)
    with _ledgers() as (ledger, upload_ledger, _database), _client(config, transport) as client:
        service = InstagramLocalResumableService(config, ledger, upload_ledger, client=client)
        with pytest.raises(InstagramWriteGateError):
            service.publish_local(manifest, video, execute=True)
    assert requests == []


def test_successful_local_resumable_publish_sends_exact_protocol_and_is_idempotent(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    _write_video(video)
    manifest = build_local_publish_manifest(
        video,
        publication_key="local.success.001",
        account_id=ACCOUNT_ID,
        caption="Exact caption",
    )
    writes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": [{"quota_usage": 1}]})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media"):
            writes.append("container")
            body = parse_qs(request.content.decode("utf-8"))
            assert body["media_type"] == ["REELS"]
            assert body["upload_type"] == ["resumable"]
            assert body["caption"] == ["Exact caption"]
            assert "video_url" not in body
            return _response(request, 200, {"id": "container-local-1", "uri": UPLOAD_URI})
        if request.method == "POST" and request.url.host == "rupload.facebook.com":
            writes.append("upload")
            assert request.headers["authorization"] == f"OAuth {TOKEN}"
            assert request.headers["offset"] == "0"
            assert request.headers["file_size"] == str(len(VIDEO_BYTES))
            assert request.headers["content-length"] == str(len(VIDEO_BYTES))
            assert request.content == VIDEO_BYTES
            return _response(request, 200, {"success": True})
        if request.method == "GET" and path.endswith("/container-local-1"):
            return _response(request, 200, {"status_code": "FINISHED", "status": "ready"})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media_publish"):
            writes.append("publish")
            return _response(request, 200, {"id": "media-local-1"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledgers() as (ledger, upload_ledger, _database), _client(config, transport) as client:
        service = InstagramLocalResumableService(config, ledger, upload_ledger, client=client)
        first = service.publish_local(manifest, video, execute=True)
        second = service.publish_local(manifest, video, execute=True)

        assert first.status == PublicationStatus.PUBLISHED
        assert first.provider_container_id == "container-local-1"
        assert first.provider_media_id == "media-local-1"
        assert second.status == PublicationStatus.PUBLISHED
        assert writes == ["container", "upload", "publish"]

        child = upload_ledger.get(manifest.publication_key)
        assert child is not None
        assert child.provider_container_id == "container-local-1"
        assert child.state == ResumableUploadState.UPLOADED
        assert child.attempt_count == 1
        assert child.upload_requested_at is not None
        assert child.uploaded_at is not None


def test_upload_transport_ambiguity_blocks_blind_binary_replay(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    _write_video(video)
    manifest = build_local_publish_manifest(video, publication_key="local.upload-unknown", account_id=ACCOUNT_ID)
    container_calls = 0
    upload_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal container_calls, upload_calls
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media"):
            container_calls += 1
            return _response(request, 200, {"id": "container-local-1", "uri": UPLOAD_URI})
        if request.method == "POST" and request.url.host == "rupload.facebook.com":
            upload_calls += 1
            raise httpx.ReadTimeout("upload response lost", request=request)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledgers() as (ledger, upload_ledger, _database), _client(config, transport) as client:
        service = InstagramLocalResumableService(config, ledger, upload_ledger, client=client)

        with pytest.raises(InstagramReconciliationRequired, match="Binary upload result"):
            service.publish_local(manifest, video, execute=True)
        child = upload_ledger.get(manifest.publication_key)
        assert child is not None
        assert child.state == ResumableUploadState.UPLOAD_UNKNOWN
        assert container_calls == 1
        assert upload_calls == 1

        with pytest.raises(InstagramReconciliationRequired, match="ambiguous"):
            service.publish_local(manifest, video, execute=True)
        assert container_calls == 1
        assert upload_calls == 1


def test_persisted_container_response_recovers_without_duplicate_container_write(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    _write_video(video)
    manifest = build_local_publish_manifest(video, publication_key="local.container-recover", account_id=ACCOUNT_ID)

    with _ledgers() as (ledger, upload_ledger, _database):
        ledger.ensure_planned(manifest)  # type: ignore[arg-type]
        ledger.claim_container_request(manifest.publication_key)
        upload_ledger.bind_container_response(
            manifest.publication_key,
            provider_container_id="container-local-1",
            upload_uri=UPLOAD_URI,
        )

        writes: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
                return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
            if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
                return _response(request, 200, {"data": []})
            if request.method == "POST" and request.url.host == "rupload.facebook.com":
                writes.append("upload")
                return _response(request, 200, {"success": True})
            if request.method == "GET" and path.endswith("/container-local-1"):
                return _response(request, 200, {"status_code": "FINISHED"})
            if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media_publish"):
                writes.append("publish")
                return _response(request, 200, {"id": "media-local-1"})
            if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media"):
                raise AssertionError("container creation must not be replayed")
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        config = _config()
        transport = httpx.MockTransport(handler)
        with _client(config, transport) as client:
            service = InstagramLocalResumableService(config, ledger, upload_ledger, client=client)
            result = service.publish_local(manifest, video, execute=True)

        assert result.status == PublicationStatus.PUBLISHED
        assert result.provider_container_id == "container-local-1"
        assert writes == ["upload", "publish"]


def test_resumable_container_rejects_non_meta_upload_uri_fail_closed(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    _write_video(video)
    manifest = build_local_publish_manifest(video, publication_key="local.bad-uri", account_id=ACCOUNT_ID)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": []})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media"):
            return _response(
                request,
                200,
                {"id": "container-local-1", "uri": "https://attacker.example/upload"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = _config()
    transport = httpx.MockTransport(handler)
    with _ledgers() as (ledger, upload_ledger, _database), _client(config, transport) as client:
        service = InstagramLocalResumableService(config, ledger, upload_ledger, client=client)
        with pytest.raises(InstagramReconciliationRequired):
            service.publish_local(manifest, video, execute=True)
        snapshot = ledger.get(manifest.publication_key)
        assert snapshot is not None
        assert snapshot.status == PublicationStatus.CONTAINER_UNKNOWN
        assert upload_ledger.get(manifest.publication_key) is None


def test_provider_client_rejects_local_resumable_on_instagram_login_mode(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    _write_video(video)
    config = InstagramRuntimeConfig(
        login_mode="instagram",
        graph_host="https://graph.instagram.com",
        api_version=API_VERSION,
        account_id=ACCOUNT_ID,
        expected_username=USERNAME,
        access_token=TOKEN,
        writes_enabled=True,
        media_allowed_hosts=(),
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
        poll_attempts=1,
    )
    manifest = build_local_publish_manifest(video, publication_key="local.mode", account_id=ACCOUNT_ID)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"No provider request expected: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    with _ledgers() as (ledger, upload_ledger, _database), _client(config, transport) as client:
        service = InstagramLocalResumableService(config, ledger, upload_ledger, client=client)
        with pytest.raises(InstagramProductionError, match="Facebook Login"):
            service.publish_local(manifest, video, execute=True)


def test_resumable_client_surfaces_provider_http_error_without_token_leak() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(request, 500, {"error": {"message": "provider failed", "code": 2}})

    config = _config()
    transport = httpx.MockTransport(handler)
    with _client(config, transport) as client:
        with pytest.raises(InstagramProviderError) as error:
            client.upload_local_video(UPLOAD_URI, __import__("io").BytesIO(VIDEO_BYTES), file_size=len(VIDEO_BYTES))
    assert TOKEN not in str(error.value)
