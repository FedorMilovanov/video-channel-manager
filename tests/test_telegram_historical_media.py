from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_historical_media import (
    HistoricalMediaAcquisitionAsset,
    _build_acquisition_client,
    _image_probe,
    acquire_historical_media,
)


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _write_json(path: Path, value: object) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _git_blob(data)


def _jpeg(width: int = 3, height: int = 2) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x02"
        + b"\xff\xc0\x00\x07\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\xff\xd9"
    )


def test_image_probe_accepts_bound_jpeg_and_png_dimensions() -> None:
    jpeg = _jpeg(width=321, height=123)
    assert _image_probe(jpeg) == ("image/jpeg", 321, 123)

    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 640, 480)
    assert _image_probe(png) == ("image/png", 640, 480)


def test_default_client_identifies_project_to_archive_origin() -> None:
    with _build_acquisition_client() as client:
        assert client.headers["user-agent"].startswith("video-channel-manager-historical-media/1.0")
        assert "github.com/FedorMilovanov/video-channel-manager" in client.headers["user-agent"]
        assert client.headers["accept"].startswith("image/")


def test_asset_rejects_unallowlisted_download_host() -> None:
    with pytest.raises(ValidationError, match="not allowlisted"):
        HistoricalMediaAcquisitionAsset.model_validate(
            {
                "asset_id": "img-example-hero",
                "publication_id": "lordchrist-history-example-topic-v3",
                "slot": "hero",
                "source_id": "src-example",
                "source_page_url": "https://example.org/source",
                "acquisition_page_url": "https://example.org/acquisition",
                "download_url": "https://example.org/file.jpg",
                "expected_upstream_sha1": "a" * 40,
                "expected_source_mime": "image/jpeg",
                "output_file_name": "example.jpg",
                "rights_basis": "Public-domain archival image with source record.",
                "attribution_text": "Example archive.",
                "acquisition_kind": "direct_image",
                "provider_write_performed": False,
            }
        )


def test_acquire_is_exact_byte_bound_and_provider_inert(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_url = "https://commons.wikimedia.org/wiki/File:Example.jpg"
    download_url = "https://upload.wikimedia.org/wikipedia/commons/a/aa/Example.jpg"
    source_path = repo / "content/source.json"
    source_blob = _write_json(
        source_path,
        {
            "schema_name": "video-channel-manager.telegram-historical-source-shard",
            "schema_version": 1,
            "shard_id": "history-sources-example",
            "checked_on": "2026-09-09",
            "sources": [
                {
                    "source_id": "src-example-archive",
                    "title": "Example archival portrait",
                    "publisher": "Example Archive",
                    "url": source_url,
                    "evidence_type": "primary",
                    "grade": "A",
                    "evidence_role": "institutional_collection",
                    "checked_on": "2026-09-09",
                    "topic_tags": ["example", "portrait"],
                    "independence_group": "example-archive",
                }
            ],
        },
    )
    verification_path = repo / "content/verification.json"
    verification_blob = _write_json(
        verification_path,
        {
            "visual_plan": [
                {
                    "slot": "hero",
                    "source_id": "src-example-archive",
                    "concept": "archival portrait",
                    "state": "planned_unmaterialized",
                    "production_ready": False,
                }
            ]
        },
    )
    batch_path = repo / "content/batch.json"
    batch_blob = _write_json(
        batch_path,
        {
            "schema_name": "video-channel-manager.telegram-historical-v3-batch-manifest",
            "schema_version": 1,
            "owning_issue": 561,
            "provider_writes_authorized": False,
            "live_eligible": False,
            "topics": [
                {
                    "publication_id": "lordchrist-history-example-topic-v3",
                    "source_shards": [{"path": "content/source.json", "git_blob_sha": source_blob}],
                    "verification": {"path": "content/verification.json", "git_blob_sha": verification_blob},
                }
            ],
        },
    )
    media = _jpeg(width=1200, height=800)
    manifest_path = repo / "content/acquisition.json"
    _write_json(
        manifest_path,
        {
            "schema_name": "video-channel-manager.telegram-historical-media-acquisition-manifest",
            "schema_version": 1,
            "manifest_id": "historical-media-acquisition-example-v1",
            "owning_issue": 561,
            "project_key": "lord-god-strength",
            "channel_username": "@lordchrist",
            "state": "provider_inert",
            "provider_writes_authorized": False,
            "live_eligible": False,
            "batch_manifest": {"path": "content/batch.json", "git_blob_sha": batch_blob},
            "assets": [
                {
                    "asset_id": "img-example-hero",
                    "publication_id": "lordchrist-history-example-topic-v3",
                    "slot": "hero",
                    "source_id": "src-example-archive",
                    "source_page_url": source_url,
                    "acquisition_page_url": source_url,
                    "download_url": download_url,
                    "expected_upstream_sha1": hashlib.sha1(media).hexdigest(),  # noqa: S324
                    "expected_source_mime": "image/jpeg",
                    "output_file_name": "example-hero.jpg",
                    "rights_basis": "Public-domain archival image with source record.",
                    "attribution_text": "Example Archive.",
                    "acquisition_kind": "direct_image",
                    "provider_write_performed": False,
                }
            ],
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == download_url
        return httpx.Response(
            200,
            headers={"content-type": "image/jpeg", "content-length": str(len(media)), "etag": '"fixture"'},
            content=media,
            request=request,
        )

    output_dir = tmp_path / "out"
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        receipt = acquire_historical_media(
            Path("content/acquisition.json"),
            output_dir=output_dir,
            repo_root=repo,
            client=client,
        )

    assert receipt.status == "PASS"
    assert receipt.asset_count == 1
    assert receipt.provider_writes_authorized is False
    assert receipt.provider_write_performed is False
    assert receipt.results[0].source_sha256 == "sha256:" + hashlib.sha256(media).hexdigest()
    assert receipt.results[0].width == 1200
    assert receipt.results[0].height == 800
    assert (output_dir / "example-hero.jpg").read_bytes() == media
    saved = json.loads((output_dir / "acquisition-receipt.json").read_text(encoding="utf-8"))
    assert saved["live_eligible"] is False
    assert saved["provider_write_performed"] is False
