from __future__ import annotations

import io
import zipfile

import pytest
from pydantic import ValidationError

from video_channel_manager.telegram_historical_media_v2 import (
    HistoricalMediaAcquisitionAssetV2,
    HistoricalMediaAcquisitionManifestV2,
    _download_host_allowed_v2,
    _epub_probe,
    _json_probe,
)


def _epub(*, mimetype: bytes = b"application/epub+zip", compress_mimetype: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "mimetype",
            mimetype,
            compress_type=zipfile.ZIP_DEFLATED if compress_mimetype else zipfile.ZIP_STORED,
        )
        archive.writestr(
            "META-INF/container.xml",
            "<?xml version='1.0'?><container><rootfiles/></container>",
            compress_type=zipfile.ZIP_DEFLATED,
        )
        archive.writestr("OEBPS/document.xhtml", "<html><body>Stam</body></html>")
    return buffer.getvalue()


def _asset(publication_index: int, slot: str) -> dict[str, object]:
    suffix = "hero" if slot == "hero" else "document"
    return {
        "asset_id": f"img-complete-{publication_index}-{suffix}",
        "publication_id": f"lordchrist-history-complete-topic-{publication_index}-v3",
        "slot": slot,
        "source_id": f"src-complete-{publication_index}-{suffix}",
        "source_page_url": "https://history.state.gov/historicaldocuments/frus1934v03/ch8",
        "acquisition_page_url": "https://history.state.gov/historicaldocuments/frus1934v03/d381",
        "download_url": "https://static.history.state.gov/frus/frus1934v03/ebook/frus1934v03.epub",
        "expected_upstream_sha1": "a" * 40,
        "expected_source_mime": "application/epub+zip",
        "output_file_name": f"complete-{publication_index}-{suffix}.epub",
        "rights_basis": "Official United States Department of State historical publication used as archival evidence.",
        "attribution_text": "U.S. Department of State, Office of the Historian.",
        "acquisition_kind": "direct_epub",
        "provider_write_performed": False,
    }


def test_epub_probe_accepts_well_formed_epub_container() -> None:
    assert _epub_probe(_epub()) == ("application/epub+zip", None, None)


def test_epub_probe_rejects_compressed_or_wrong_mimetype_entry() -> None:
    with pytest.raises(ValueError, match="uncompressed"):
        _epub_probe(_epub(compress_mimetype=True))
    with pytest.raises(ValueError, match="invalid mimetype"):
        _epub_probe(_epub(mimetype=b"application/zip"))


def test_json_probe_requires_utf8_json_object() -> None:
    assert _json_probe(b'{"id":"d2cy4t36"}') == ("application/json", None, None)
    with pytest.raises(ValueError, match="object"):
        _json_probe(b"[]")
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        _json_probe(b"{broken")


def test_v2_extra_archive_hosts_are_narrowly_allowlisted() -> None:
    assert _download_host_allowed_v2("bedsarchives.bedford.gov.uk")
    assert _download_host_allowed_v2("api.wellcomecollection.org")
    assert not _download_host_allowed_v2("example.invalid")


def test_epub_asset_requires_epub_kind_and_extension() -> None:
    payload = _asset(1, "document")
    assert HistoricalMediaAcquisitionAssetV2.model_validate(payload)

    payload["acquisition_kind"] = "direct_pdf"
    with pytest.raises(ValidationError, match="kind differs"):
        HistoricalMediaAcquisitionAssetV2.model_validate(payload)

    payload = _asset(1, "document")
    payload["output_file_name"] = "wrong.pdf"
    with pytest.raises(ValidationError, match="suffix"):
        HistoricalMediaAcquisitionAssetV2.model_validate(payload)


def test_json_asset_requires_json_kind_and_extension() -> None:
    payload = _asset(1, "document")
    payload.update(
        {
            "source_page_url": "https://wellcomecollection.org/works/d2cy4t36",
            "acquisition_page_url": "https://api.wellcomecollection.org/catalogue/v2/works/d2cy4t36",
            "download_url": "https://api.wellcomecollection.org/catalogue/v2/works/d2cy4t36",
            "expected_source_mime": "application/json",
            "output_file_name": "taylor-1786.json",
            "acquisition_kind": "direct_json",
        }
    )
    assert HistoricalMediaAcquisitionAssetV2.model_validate(payload)
    payload["acquisition_kind"] = "direct_epub"
    with pytest.raises(ValidationError, match="kind differs"):
        HistoricalMediaAcquisitionAssetV2.model_validate(payload)


def test_complete_manifest_requires_exactly_sixteen_assets_two_per_eight_publications() -> None:
    assets = []
    for index in range(1, 9):
        assets.extend((_asset(index, "hero"), _asset(index, "document")))
    manifest = HistoricalMediaAcquisitionManifestV2.model_validate(
        {
            "schema_name": "video-channel-manager.telegram-historical-media-acquisition-manifest",
            "schema_version": 2,
            "manifest_id": "historical-media-acquisition-complete-example-v2",
            "owning_issue": 561,
            "project_key": "lord-god-strength",
            "channel_username": "@lordchrist",
            "state": "provider_inert",
            "provider_writes_authorized": False,
            "live_eligible": False,
            "batch_manifest": {"path": "content/batch.json", "git_blob_sha": "b" * 40},
            "assets": assets,
        }
    )
    assert len(manifest.assets) == 16
    assert len({asset.publication_id for asset in manifest.assets}) == 8

    with pytest.raises(ValidationError):
        HistoricalMediaAcquisitionManifestV2.model_validate(
            {
                **manifest.model_dump(mode="json"),
                "assets": manifest.model_dump(mode="json")["assets"][:-1],
            }
        )
