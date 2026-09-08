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
    _source_probe,
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


def test_source_probe_accepts_complete_pdf_without_inventing_dimensions() -> None:
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nstartxref\n0\n%%EOF\n"
    assert _source_probe(pdf) == ("application/pdf", None, None)

    with pytest.raises(ValueError, match="truncated"):
        _source_probe(b"%PDF-1.4\nmissing eof")


def test_default_client_identifies_project_to_archive_origin() -> None:
    with _build_acquisition_client() as client:
        assert client.headers["user-agent"].startswith("video-channel-manager-historical-media/1.0")
        assert "github.com/FedorMilovanov/video-channel-manager" in client.headers["user-agent"]
        assert client.headers["accept"].startswith("image/")
        assert "application/pdf" in client.headers["accept"]


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


def test_asset_requires_pdf_kind_and_extension_to_match_mime() -> None:
    base = {
        "asset_id": "img-example-document",
        "publication_id": "lordchrist-history-example-topic-v3",
        "slot": "document",
        "source_id": "src-example",
        "source_page_url": "https://example.org/source",
        "acquisition_page_url": "https://example.org/acquisition",
        "download_url": "https://careycenter.wmcarey.edu/example.pdf",
        "expected_upstream_sha1": "a" * 40,
        "expected_source_mime": "application/pdf",
        "output_file_name": "example.pdf",
        "rights_basis": "Public-domain historical document with source record.",
        "attribution_text": "Example archive.",
        "provider_write_performed": False,
    }
    assert HistoricalMediaAcquisitionAsset.model_validate({**base, "acquisition_kind": "direct_pdf"})
    with pytest.raises(ValidationError, match="direct_image"):
        HistoricalMediaAcquisitionAsset.model_validate({**base, "acquisition_kind": "direct_image"})
    with pytest.raises(ValidationError, match="suffix"):
        HistoricalMediaAcquisitionAsset.model_validate(
            {**base, "acquisition_kind": "direct_pdf", "output_file_name": "example.jpg"}
        )


def _fixture_repository(
    repo: Path,
    *,
    slot: str,
    source_id: str,
    source_url: str,
) -> str:
    source_blob = _write_json(
        repo / "content/source.json",
        {
            "schema_name": "video-channel-manager.telegram-historical-source-shard",
            "schema_version": 1,
            "shard_id": "history-sources-example",
            "checked_on": "2026-09-09",
            "sources": [
                {
                    "source_id": source_id,
                    "title": "Example archival source",
                    "publisher": "Example Archive",
                    "url": source_url,
                    "evidence_type": "primary",
                    "grade": "A",
                    "evidence_role": "institutional_collection",
                    "checked_on": "2026-09-09",
                    "topic_tags": ["example", "archive"],
                    "independence_group": "example-archive",
                }
            ],
        },
    )
    verification_blob = _write_json(
        repo / "content/verification.json",
        {
            "visual_plan": [
                {
                    "slot": slot,
                    "source_id": source_id,
                    "concept": "archival source",
                    "state": "planned_unmaterialized",
                    "production_ready": False,
                }
            ]
        },
    )
    return _write_json(
        repo / "content/batch.json",
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


def test_acquire_is_exact_byte_bound_and_provider_inert(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_url = "https://commons.wikimedia.org/wiki/File:Example.jpg"
    download_url = "https://upload.wikimedia.org/wikipedia/commons/a/aa/Example.jpg"
    batch_blob = _fixture_repository(repo, slot="hero", source_id="src-example-archive", source_url=source_url)
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


def test_acquire_pdf_preserves_exact_source_bytes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_url = "https://careycenter.wmcarey.edu/enquiry/enquiry.html"
    download_url = "https://careycenter.wmcarey.edu/enquiry/anenquiry.pdf"
    batch_blob = _fixture_repository(repo, slot="hero", source_id="src-example-pdf", source_url=source_url)
    pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nstartxref\n0\n%%EOF\n"
    _write_json(
        repo / "content/acquisition.json",
        {
            "schema_name": "video-channel-manager.telegram-historical-media-acquisition-manifest",
            "schema_version": 1,
            "manifest_id": "historical-media-acquisition-example-pdf-v1",
            "owning_issue": 561,
            "project_key": "lord-god-strength",
            "channel_username": "@lordchrist",
            "state": "provider_inert",
            "provider_writes_authorized": False,
            "live_eligible": False,
            "batch_manifest": {"path": "content/batch.json", "git_blob_sha": batch_blob},
            "assets": [
                {
                    "asset_id": "img-example-pdf",
                    "publication_id": "lordchrist-history-example-topic-v3",
                    "slot": "hero",
                    "source_id": "src-example-pdf",
                    "source_page_url": source_url,
                    "acquisition_page_url": source_url,
                    "download_url": download_url,
                    "expected_upstream_sha1": hashlib.sha1(pdf).hexdigest(),  # noqa: S324
                    "expected_source_mime": "application/pdf",
                    "output_file_name": "example-source.pdf",
                    "rights_basis": "Public-domain historical document with source record.",
                    "attribution_text": "Example Archive.",
                    "acquisition_kind": "direct_pdf",
                    "provider_write_performed": False,
                }
            ],
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf", "content-length": str(len(pdf))},
            content=pdf,
            request=request,
        )

    output_dir = tmp_path / "out-pdf"
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        receipt = acquire_historical_media(
            Path("content/acquisition.json"), output_dir=output_dir, repo_root=repo, client=client
        )

    result = receipt.results[0]
    assert result.mime == "application/pdf"
    assert result.width is None
    assert result.height is None
    assert result.source_sha256 == "sha256:" + hashlib.sha256(pdf).hexdigest()
    assert (output_dir / "example-source.pdf").read_bytes() == pdf
