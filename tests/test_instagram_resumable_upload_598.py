from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
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
    InstagramProviderError,
    InstagramPublicationLedger,
    InstagramReconciliationRequired,
    InstagramRuntimeConfig,
    PublicationStatus,
)
from video_channel_manager.local_media.quality import MediaQualityReport
from video_channel_manager.persistence import Database


ACCOUNT_ID = "17841400000000000"
USERNAME = "example_creator"
TOKEN = "issue-598-secret-token"
VIDEO_BYTES = b"issue 598 exact reel bytes"
UPLOAD_URI = "https://rupload.facebook.com/ig-api-upload/v26.0/container-598"


def _config() -> InstagramRuntimeConfig:
    return InstagramRuntimeConfig(
        login_mode="facebook",
        graph_host="https://graph.facebook.com",
        api_version="v26.0",
        account_id=ACCOUNT_ID,
        expected_username=USERNAME,
        access_token=TOKEN,
        writes_enabled=True,
        media_allowed_hosts=(),
        timeout_seconds=300.0,
        poll_interval_seconds=0.0,
        poll_attempts=2,
    )


@contextmanager
def _client(
    config: InstagramRuntimeConfig,
    transport: httpx.MockTransport,
) -> Iterator[InstagramResumableProviderClient]:
    with httpx.Client(transport=transport) as graph_client, httpx.Client(transport=transport) as media_client:
        yield InstagramResumableProviderClient(config, client=graph_client, media_client=media_client)


def _response(request: httpx.Request, status_code: int, payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(status_code, request=request, json=payload)


def _compatible_probe(path: Path) -> MediaQualityReport:
    content = path.read_bytes()
    return MediaQualityReport(
        path=str(path.resolve()),
        size_bytes=len(content),
        sha256=f"sha256:{hashlib.sha256(content).hexdigest()}",
        duration_seconds=12.0,
        format_names=("mov", "mp4", "m4a", "3gp", "3g2", "mj2"),
        video_stream_count=1,
        audio_stream_count=1,
        video_codec="h264",
        audio_codec="aac",
        width=1080,
        height=1920,
        sample_rate_hz=48_000,
        audio_channels=2,
        video_frame_rate_fps=30.0,
        video_bitrate_bps=5_000_000,
        audio_bitrate_bps=128_000,
    )


def test_binary_upload_passes_complete_bytes_and_only_meta_sample_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    unused_transport = httpx.MockTransport(lambda request: _response(request, 500, {}))
    observed: dict[str, Any] = {}

    with _client(config, unused_transport) as client:
        def fake_post(url: str, *, headers: dict[str, str], content: bytes) -> httpx.Response:
            observed["url"] = url
            observed["headers"] = dict(headers)
            observed["content"] = content
            request = httpx.Request("POST", url, headers=headers, content=content)
            return httpx.Response(200, request=request, json={"success": True})

        monkeypatch.setattr(client._client, "post", fake_post)
        client.upload_local_video(UPLOAD_URI, io.BytesIO(VIDEO_BYTES), file_size=len(VIDEO_BYTES))

    assert observed["url"] == UPLOAD_URI
    assert observed["content"] == VIDEO_BYTES
    assert type(observed["content"]) is bytes
    assert observed["headers"] == {
        "Authorization": f"OAuth {TOKEN}",
        "offset": "0",
        "file_size": str(len(VIDEO_BYTES)),
    }
    assert "Content-Length" not in observed["headers"]


def test_plain_text_http_400_detail_is_bounded_and_redacted() -> None:
    raw_detail = f"Upload rejected for OAuth {TOKEN} at {UPLOAD_URI} " + ("provider-detail " * 100)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, request=request, text=raw_detail)

    config = _config()
    with _client(config, httpx.MockTransport(handler)) as client:
        with pytest.raises(InstagramProviderError) as caught:
            client.upload_local_video(UPLOAD_URI, io.BytesIO(VIDEO_BYTES), file_size=len(VIDEO_BYTES))

    error = caught.value
    message = str(error)
    assert error.status_code == 400
    assert "Instagram resumable upload returned HTTP 400" in message
    assert "Upload rejected" in message
    assert TOKEN not in message
    assert UPLOAD_URI not in message
    assert "[REDACTED" in message
    assert len(message) < 600


def test_http_400_diagnostic_is_durable_and_does_not_reopen_binary_upload(tmp_path: Path) -> None:
    video = tmp_path / "reel.mp4"
    video.write_bytes(VIDEO_BYTES)
    manifest = build_local_publish_manifest(
        video,
        publication_key="issue598.http400",
        account_id=ACCOUNT_ID,
    )
    container_calls = 0
    upload_calls = 0
    publish_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal container_calls, upload_calls, publish_calls
        path = request.url.path
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}"):
            return _response(request, 200, {"id": ACCOUNT_ID, "username": USERNAME})
        if request.method == "GET" and path.endswith(f"/{ACCOUNT_ID}/content_publishing_limit"):
            return _response(request, 200, {"data": [{"quota_usage": 0}]})
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media"):
            container_calls += 1
            body = parse_qs(request.content.decode("utf-8"))
            assert body["upload_type"] == ["resumable"]
            return _response(request, 200, {"id": "container-598", "uri": UPLOAD_URI})
        if request.method == "POST" and request.url.host == "rupload.facebook.com":
            upload_calls += 1
            return _response(
                request,
                400,
                {
                    "error": {
                        "code": 36003,
                        "type": "OAuthException",
                        "error_user_msg": f"Video rejected; do not echo {TOKEN} or {UPLOAD_URI}",
                    }
                },
            )
        if request.method == "POST" and path.endswith(f"/{ACCOUNT_ID}/media_publish"):
            publish_calls += 1
            return _response(request, 200, {"id": "must-not-publish"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    database = Database("sqlite:///:memory:")
    database.create_schema()
    ledger = InstagramPublicationLedger(database)
    upload_ledger = InstagramResumableUploadLedger(database)
    config = _config()
    try:
        with _client(config, httpx.MockTransport(handler)) as client:
            service = InstagramLocalResumableService(
                config,
                ledger,
                upload_ledger,
                client=client,
                media_probe=_compatible_probe,
            )
            with pytest.raises(InstagramReconciliationRequired) as first_error:
                service.publish_local(manifest, video, execute=True)

            first_message = str(first_error.value)
            assert "Provider detail:" in first_message
            assert "Video rejected" in first_message
            assert TOKEN not in first_message
            assert UPLOAD_URI not in first_message

            child = upload_ledger.get(manifest.publication_key)
            assert child is not None
            assert child.state == ResumableUploadState.UPLOAD_UNKNOWN
            assert child.attempt_count == 1
            assert child.last_error_code == "36003"
            assert child.last_error_message is not None
            assert "Video rejected" in child.last_error_message
            assert TOKEN not in child.last_error_message
            assert UPLOAD_URI not in child.last_error_message

            publication = ledger.get(manifest.publication_key)
            assert publication is not None
            assert publication.status == PublicationStatus.CONTAINER_CREATED

            with pytest.raises(InstagramReconciliationRequired, match="ambiguous"):
                service.publish_local(manifest, video, execute=True)
    finally:
        database.close()

    assert container_calls == 1
    assert upload_calls == 1
    assert publish_calls == 0
