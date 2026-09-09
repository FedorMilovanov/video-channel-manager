from __future__ import annotations

import argparse
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Literal, Sequence
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_historical_media import (
    _MAX_SOURCE_BYTES,
    _build_acquisition_client,
    _download_host_allowed,
    _read_json,
    _resolve_repo_path,
    _sha1,
    _sha256,
    _source_probe,
    _validate_manifest_bindings,
)
from video_channel_manager.telegram_historical_revision import HistoricalRevisionGitBlobRef

_SHA1_RE = r"^[0-9a-f]{40}$"
_SHA256_RE = r"^sha256:[0-9a-f]{64}$"
_PUBLICATION_RE = r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$"
_ASSET_RE = r"^img-[a-z0-9][a-z0-9-]{2,100}$"
_SOURCE_MIME = Literal[
    "image/jpeg",
    "image/png",
    "application/pdf",
    "application/epub+zip",
    "application/json",
]
_V2_EXTRA_DOWNLOAD_HOSTS = frozenset({"api.wellcomecollection.org", "bedsarchives.bedford.gov.uk"})


def _download_host_allowed_v2(host: str | None) -> bool:
    if _download_host_allowed(host):
        return True
    if not host:
        return False
    return host.casefold().rstrip(".") in _V2_EXTRA_DOWNLOAD_HOSTS


class HistoricalMediaAcquisitionAssetV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(pattern=_ASSET_RE)
    publication_id: str = Field(pattern=_PUBLICATION_RE)
    slot: Literal["hero", "document", "opposition"]
    source_id: str = Field(min_length=5, max_length=120)
    source_page_url: str = Field(min_length=12, max_length=500)
    acquisition_page_url: str = Field(min_length=12, max_length=500)
    download_url: str = Field(min_length=12, max_length=700)
    expected_upstream_sha1: str = Field(pattern=_SHA1_RE)
    expected_source_mime: _SOURCE_MIME
    output_file_name: str = Field(min_length=5, max_length=180)
    rights_basis: str = Field(min_length=20, max_length=500)
    attribution_text: str = Field(min_length=10, max_length=300)
    acquisition_kind: Literal["direct_image", "direct_pdf", "direct_epub", "direct_json"]
    provider_write_performed: Literal[False]

    @model_validator(mode="after")
    def transport_boundary(self) -> "HistoricalMediaAcquisitionAssetV2":
        for label, value in (
            ("source_page_url", self.source_page_url),
            ("acquisition_page_url", self.acquisition_page_url),
            ("download_url", self.download_url),
        ):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError(f"{label} must be an absolute HTTPS URL")
            if parsed.username or parsed.password:
                raise ValueError(f"{label} must not contain credentials")
        if not _download_host_allowed_v2(urlparse(self.download_url).hostname):
            raise ValueError(
                f"historical media download host is not allowlisted: {urlparse(self.download_url).hostname}"
            )
        if "/" in self.output_file_name or "\\" in self.output_file_name:
            raise ValueError("historical media output filename must be a basename")
        suffix_by_mime = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "application/pdf": ".pdf",
            "application/epub+zip": ".epub",
            "application/json": ".json",
        }
        if not self.output_file_name.casefold().endswith(suffix_by_mime[self.expected_source_mime]):
            raise ValueError("historical media output filename suffix differs from MIME")
        kind_by_mime = {
            "image/jpeg": "direct_image",
            "image/png": "direct_image",
            "application/pdf": "direct_pdf",
            "application/epub+zip": "direct_epub",
            "application/json": "direct_json",
        }
        if self.acquisition_kind != kind_by_mime[self.expected_source_mime]:
            raise ValueError("historical media acquisition kind differs from MIME")
        return self


class HistoricalMediaAcquisitionManifestV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-media-acquisition-manifest"]
    schema_version: Literal[2]
    manifest_id: str = Field(pattern=r"^historical-media-acquisition-[a-z0-9][a-z0-9-]{4,100}$")
    owning_issue: Literal[561]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    state: Literal["provider_inert"]
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    batch_manifest: HistoricalRevisionGitBlobRef
    assets: tuple[HistoricalMediaAcquisitionAssetV2, ...] = Field(min_length=16, max_length=16)

    @model_validator(mode="after")
    def complete_unique_asset_universe(self) -> "HistoricalMediaAcquisitionManifestV2":
        asset_ids = [asset.asset_id for asset in self.assets]
        output_names = [asset.output_file_name for asset in self.assets]
        source_keys = [(asset.publication_id, asset.slot) for asset in self.assets]
        publications = {asset.publication_id for asset in self.assets}
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("historical media acquisition asset ids must be unique")
        if len(output_names) != len(set(output_names)):
            raise ValueError("historical media acquisition output filenames must be unique")
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("historical media acquisition publication/slot pairs must be unique")
        if len(publications) != 8:
            raise ValueError("complete historical media acquisition must cover exactly eight publications")
        counts = {publication_id: 0 for publication_id in publications}
        for publication_id, _slot in source_keys:
            counts[publication_id] += 1
        if set(counts.values()) != {2}:
            raise ValueError("complete historical media acquisition must contain exactly two slots per publication")
        return self


class HistoricalMediaAcquisitionResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    publication_id: str
    slot: str
    source_id: str
    source_page_url: str
    acquisition_page_url: str
    requested_url: str
    effective_url: str
    source_sha1: str = Field(pattern=_SHA1_RE)
    source_sha256: str = Field(pattern=_SHA256_RE)
    source_byte_length: int = Field(gt=0, le=_MAX_SOURCE_BYTES)
    mime: _SOURCE_MIME
    width: int | None = Field(default=None, gt=0, le=20_000)
    height: int | None = Field(default=None, gt=0, le=20_000)
    output_file_name: str
    etag: str | None = None
    last_modified: str | None = None
    rights_basis: str
    attribution_text: str
    provider_write_performed: Literal[False]

    @model_validator(mode="after")
    def dimensions_match_mime(self) -> "HistoricalMediaAcquisitionResultV2":
        if self.mime in {"application/pdf", "application/epub+zip", "application/json"}:
            if self.width is not None or self.height is not None:
                raise ValueError("document acquisition must not invent image dimensions")
        elif self.width is None or self.height is None:
            raise ValueError("source image acquisition requires dimensions")
        return self


class HistoricalMediaAcquisitionReceiptV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-media-acquisition-receipt"]
    schema_version: Literal[2]
    status: Literal["PASS"]
    manifest_id: str
    asset_count: Literal[16]
    results: tuple[HistoricalMediaAcquisitionResultV2, ...] = Field(min_length=16, max_length=16)
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    provider_write_performed: Literal[False]


def _epub_probe(data: bytes) -> tuple[Literal["application/epub+zip"], None, None]:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
            if not names or names[0] != "mimetype":
                raise ValueError("historical media EPUB must begin with the mimetype entry")
            mimetype_info = archive.getinfo("mimetype")
            if mimetype_info.compress_type != zipfile.ZIP_STORED:
                raise ValueError("historical media EPUB mimetype entry must be uncompressed")
            if archive.read("mimetype") != b"application/epub+zip":
                raise ValueError("historical media EPUB has an invalid mimetype payload")
            if "META-INF/container.xml" not in names:
                raise ValueError("historical media EPUB lacks META-INF/container.xml")
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"historical media EPUB has corrupt member: {bad_member}")
    except zipfile.BadZipFile as exc:
        raise ValueError("historical media EPUB is not a valid ZIP container") from exc
    return "application/epub+zip", None, None


def _json_probe(data: bytes) -> tuple[Literal["application/json"], None, None]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("historical media JSON source is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("historical media JSON source must be an object")
    return "application/json", None, None


def _source_probe_v2(data: bytes) -> tuple[_SOURCE_MIME, int | None, int | None]:
    if data.startswith(b"PK\x03\x04"):
        return _epub_probe(data)
    stripped = data.lstrip()
    if stripped.startswith(b"{"):
        return _json_probe(data)
    return _source_probe(data)


def _load_manifest_v2(path: Path, *, repo_root: Path) -> HistoricalMediaAcquisitionManifestV2:
    resolved = path if path.is_absolute() else _resolve_repo_path(repo_root, path)
    manifest = HistoricalMediaAcquisitionManifestV2.model_validate(_read_json(resolved))
    _validate_manifest_bindings(manifest, repo_root=repo_root)  # type: ignore[arg-type]
    return manifest


def _fetch_asset_v2(
    asset: HistoricalMediaAcquisitionAssetV2,
    *,
    client: httpx.Client,
    output_dir: Path,
) -> HistoricalMediaAcquisitionResultV2:
    with client.stream("GET", asset.download_url) as response:
        response.raise_for_status()
        final_url = str(response.url)
        if not _download_host_allowed_v2(urlparse(final_url).hostname):
            raise ValueError(f"historical media redirect escaped allowlist: {urlparse(final_url).hostname}")
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise ValueError("historical media content-length is invalid") from exc
            if declared_length <= 0 or declared_length > _MAX_SOURCE_BYTES:
                raise ValueError("historical media content-length exceeds acquisition boundary")
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > _MAX_SOURCE_BYTES:
                raise ValueError("historical media response exceeds acquisition boundary")
            chunks.append(chunk)
        data = b"".join(chunks)
        etag = response.headers.get("etag")
        last_modified = response.headers.get("last-modified")

    if not data:
        raise ValueError("historical media source is empty")
    actual_sha1 = _sha1(data)
    if actual_sha1 != asset.expected_upstream_sha1:
        raise ValueError(
            f"historical media upstream SHA-1 differs for {asset.asset_id}: "
            f"expected {asset.expected_upstream_sha1}, got {actual_sha1}"
        )
    mime, width, height = _source_probe_v2(data)
    if mime != asset.expected_source_mime:
        raise ValueError(f"historical media MIME differs for {asset.asset_id}: {mime}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / asset.output_file_name
    if output_path.exists():
        raise ValueError(f"historical media output already exists: {output_path}")
    output_path.write_bytes(data)

    return HistoricalMediaAcquisitionResultV2(
        asset_id=asset.asset_id,
        publication_id=asset.publication_id,
        slot=asset.slot,
        source_id=asset.source_id,
        source_page_url=asset.source_page_url,
        acquisition_page_url=asset.acquisition_page_url,
        requested_url=asset.download_url,
        effective_url=final_url,
        source_sha1=actual_sha1,
        source_sha256=_sha256(data),
        source_byte_length=len(data),
        mime=mime,
        width=width,
        height=height,
        output_file_name=asset.output_file_name,
        etag=etag,
        last_modified=last_modified,
        rights_basis=asset.rights_basis,
        attribution_text=asset.attribution_text,
        provider_write_performed=False,
    )


def acquire_historical_media_v2(
    manifest_path: Path,
    *,
    output_dir: Path,
    repo_root: Path = Path("."),
    client: httpx.Client | None = None,
) -> HistoricalMediaAcquisitionReceiptV2:
    manifest = _load_manifest_v2(manifest_path, repo_root=repo_root)
    owns_client = client is None
    active_client = client or _build_acquisition_client()
    try:
        results = tuple(
            _fetch_asset_v2(asset, client=active_client, output_dir=output_dir) for asset in manifest.assets
        )
    finally:
        if owns_client:
            active_client.close()

    receipt = HistoricalMediaAcquisitionReceiptV2(
        schema_name="video-channel-manager.telegram-historical-media-acquisition-receipt",
        schema_version=2,
        status="PASS",
        manifest_id=manifest.manifest_id,
        asset_count=16,
        results=results,
        provider_writes_authorized=False,
        live_eligible=False,
        provider_write_performed=False,
    )
    (output_dir / "acquisition-receipt.json").write_text(
        json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return receipt


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Acquire complete provider-inert LordChrist historical archive media v2")
    root.add_argument("manifest", type=Path)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--repo-root", type=Path, default=Path("."))
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    receipt = acquire_historical_media_v2(args.manifest, output_dir=args.output_dir, repo_root=args.repo_root)
    print(json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
