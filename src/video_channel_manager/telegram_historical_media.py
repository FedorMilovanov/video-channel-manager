from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Literal, Sequence
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalSource
from video_channel_manager.telegram_historical_revision import (
    HistoricalRevisionGitBlobRef,
    load_historical_revision_git_blob_json,
)

_SHA1_RE = r"^[0-9a-f]{40}$"
_SHA256_RE = r"^sha256:[0-9a-f]{64}$"
_PUBLICATION_RE = r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$"
_ASSET_RE = r"^img-[a-z0-9][a-z0-9-]{2,80}$"
_ALLOWED_DOWNLOAD_HOSTS = frozenset({"upload.wikimedia.org"})
_MAX_SOURCE_BYTES = 10_000_000
_ACQUISITION_USER_AGENT = (
    "video-channel-manager-historical-media/1.0 "
    "(+https://github.com/FedorMilovanov/video-channel-manager; contact via repository issues)"
)
_ACQUISITION_ACCEPT = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"


class HistoricalMediaAcquisitionAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(pattern=_ASSET_RE)
    publication_id: str = Field(pattern=_PUBLICATION_RE)
    slot: Literal["hero", "document", "opposition"]
    source_id: str = Field(min_length=5, max_length=120)
    source_page_url: str = Field(min_length=12, max_length=500)
    acquisition_page_url: str = Field(min_length=12, max_length=500)
    download_url: str = Field(min_length=12, max_length=700)
    expected_upstream_sha1: str = Field(pattern=_SHA1_RE)
    expected_source_mime: Literal["image/jpeg", "image/png"]
    output_file_name: str = Field(min_length=5, max_length=180)
    rights_basis: str = Field(min_length=20, max_length=500)
    attribution_text: str = Field(min_length=10, max_length=300)
    acquisition_kind: Literal["direct_image"]
    provider_write_performed: Literal[False]

    @model_validator(mode="after")
    def transport_boundary(self) -> "HistoricalMediaAcquisitionAsset":
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
        download_host = urlparse(self.download_url).hostname
        if download_host not in _ALLOWED_DOWNLOAD_HOSTS:
            raise ValueError(f"historical media download host is not allowlisted: {download_host}")
        if "/" in self.output_file_name or "\\" in self.output_file_name:
            raise ValueError("historical media output filename must be a basename")
        expected_suffix = ".jpg" if self.expected_source_mime == "image/jpeg" else ".png"
        if not self.output_file_name.casefold().endswith(expected_suffix):
            raise ValueError("historical media output filename suffix differs from MIME")
        return self


class HistoricalMediaAcquisitionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-media-acquisition-manifest"]
    schema_version: Literal[1]
    manifest_id: str = Field(pattern=r"^historical-media-acquisition-[a-z0-9][a-z0-9-]{4,100}$")
    owning_issue: Literal[561]
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    state: Literal["provider_inert"]
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    batch_manifest: HistoricalRevisionGitBlobRef
    assets: tuple[HistoricalMediaAcquisitionAsset, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_assets(self) -> "HistoricalMediaAcquisitionManifest":
        asset_ids = [asset.asset_id for asset in self.assets]
        output_names = [asset.output_file_name for asset in self.assets]
        source_keys = [(asset.publication_id, asset.slot) for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("historical media acquisition asset ids must be unique")
        if len(output_names) != len(set(output_names)):
            raise ValueError("historical media acquisition output filenames must be unique")
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("historical media acquisition publication/slot pairs must be unique")
        return self


class HistoricalMediaAcquisitionResult(BaseModel):
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
    mime: Literal["image/jpeg", "image/png"]
    width: int = Field(gt=0, le=20_000)
    height: int = Field(gt=0, le=20_000)
    output_file_name: str
    etag: str | None = None
    last_modified: str | None = None
    rights_basis: str
    attribution_text: str
    provider_write_performed: Literal[False]


class HistoricalMediaAcquisitionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-media-acquisition-receipt"]
    schema_version: Literal[1]
    status: Literal["PASS"]
    manifest_id: str
    asset_count: int = Field(ge=1, le=16)
    results: tuple[HistoricalMediaAcquisitionResult, ...]
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    provider_write_performed: Literal[False]


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical media acquisition JSON {path}: {exc}") from exc


def _resolve_repo_path(repo_root: Path, value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("historical media acquisition paths must be repository-relative")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("historical media acquisition path escapes repository root")
    return resolved


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()  # noqa: S324 - upstream Commons identity is SHA-1 by contract


def _image_probe(data: bytes) -> tuple[Literal["image/jpeg", "image/png"], int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise ValueError("invalid PNG historical media")
        width, height = struct.unpack(">II", data[16:24])
        return "image/png", width, height
    if data.startswith(b"\xff\xd8"):
        offset = 2
        sof_markers = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        while offset + 4 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in {0xD8, 0xD9}:
                continue
            if marker == 0xDA:
                break
            if offset + 2 > len(data):
                break
            segment_length = int.from_bytes(data[offset : offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(data):
                raise ValueError("invalid JPEG segment length")
            if marker in sof_markers:
                if segment_length < 7:
                    raise ValueError("invalid JPEG SOF segment")
                height = int.from_bytes(data[offset + 3 : offset + 5], "big")
                width = int.from_bytes(data[offset + 5 : offset + 7], "big")
                if width <= 0 or height <= 0:
                    raise ValueError("invalid JPEG dimensions")
                return "image/jpeg", width, height
            offset += segment_length
        raise ValueError("JPEG dimensions not found")
    raise ValueError("historical media source is not an accepted JPEG or PNG")


def _load_manifest(path: Path, *, repo_root: Path) -> HistoricalMediaAcquisitionManifest:
    resolved = path if path.is_absolute() else _resolve_repo_path(repo_root, path)
    manifest = HistoricalMediaAcquisitionManifest.model_validate(_read_json(resolved))
    _validate_manifest_bindings(manifest, repo_root=repo_root)
    return manifest


def _validate_manifest_bindings(manifest: HistoricalMediaAcquisitionManifest, *, repo_root: Path) -> None:
    batch_value = load_historical_revision_git_blob_json(
        repo_root,
        manifest.batch_manifest,
        label="historical v3 batch manifest",
    )
    if not isinstance(batch_value, dict):
        raise ValueError("historical v3 batch manifest must be an object")
    if (
        batch_value.get("schema_name") != "video-channel-manager.telegram-historical-v3-batch-manifest"
        or batch_value.get("owning_issue") != 561
        or batch_value.get("provider_writes_authorized") is not False
        or batch_value.get("live_eligible") is not False
    ):
        raise ValueError("historical v3 batch manifest is not the provider-inert Issue #561 contract")
    topics = batch_value.get("topics")
    if not isinstance(topics, list):
        raise ValueError("historical v3 batch manifest topics are invalid")

    topic_by_publication: dict[str, dict[str, object]] = {}
    for topic in topics:
        if not isinstance(topic, dict):
            raise ValueError("historical v3 batch topic must be an object")
        publication_id = topic.get("publication_id")
        if not isinstance(publication_id, str):
            raise ValueError("historical v3 batch topic publication id is invalid")
        topic_by_publication[publication_id] = topic

    for asset in manifest.assets:
        topic = topic_by_publication.get(asset.publication_id)
        if topic is None:
            raise ValueError(f"historical media publication is not in bound batch: {asset.publication_id}")
        shard_refs = topic.get("source_shards")
        verification_ref = topic.get("verification")
        if not isinstance(shard_refs, list) or not isinstance(verification_ref, dict):
            raise ValueError("historical v3 batch topic bindings are invalid")

        source_by_id: dict[str, HistoricalSource] = {}
        for index, raw_ref in enumerate(shard_refs, start=1):
            ref = HistoricalRevisionGitBlobRef.model_validate(raw_ref)
            shard = HistoricalSourceShardV1.model_validate(
                load_historical_revision_git_blob_json(repo_root, ref, label=f"media source shard {index}")
            )
            for source in shard.sources:
                source_by_id[source.source_id] = source
        bound_source = source_by_id.get(asset.source_id)
        if bound_source is None:
            raise ValueError(f"historical media source is not bound to topic: {asset.source_id}")
        source_url = bound_source.url
        if source_url != asset.source_page_url:
            raise ValueError(f"historical media source page differs from bound source registry: {asset.source_id}")

        verification = load_historical_revision_git_blob_json(
            repo_root,
            HistoricalRevisionGitBlobRef.model_validate(verification_ref),
            label="historical media topic verification",
        )
        if not isinstance(verification, dict):
            raise ValueError("historical media topic verification must be an object")
        visual_plan = verification.get("visual_plan")
        if not isinstance(visual_plan, list):
            raise ValueError("historical media topic verification has no visual plan")
        matches = [
            item
            for item in visual_plan
            if isinstance(item, dict) and item.get("slot") == asset.slot and item.get("source_id") == asset.source_id
        ]
        if len(matches) != 1:
            raise ValueError(f"historical media asset does not match exactly one planned visual slot: {asset.asset_id}")
        if matches[0].get("production_ready") is not False:
            raise ValueError("historical media acquisition must start from a provider-inert visual slot")


def _fetch_asset(
    asset: HistoricalMediaAcquisitionAsset,
    *,
    client: httpx.Client,
    output_dir: Path,
) -> HistoricalMediaAcquisitionResult:
    with client.stream("GET", asset.download_url) as response:
        response.raise_for_status()
        final_url = str(response.url)
        final_host = urlparse(final_url).hostname
        if final_host not in _ALLOWED_DOWNLOAD_HOSTS:
            raise ValueError(f"historical media redirect escaped allowlist: {final_host}")
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
    mime, width, height = _image_probe(data)
    if mime != asset.expected_source_mime:
        raise ValueError(f"historical media MIME differs for {asset.asset_id}: {mime}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / asset.output_file_name
    if output_path.exists():
        raise ValueError(f"historical media output already exists: {output_path}")
    output_path.write_bytes(data)

    return HistoricalMediaAcquisitionResult(
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


def _build_acquisition_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=15.0),
        headers={
            "User-Agent": _ACQUISITION_USER_AGENT,
            "Accept": _ACQUISITION_ACCEPT,
        },
    )


def acquire_historical_media(
    manifest_path: Path,
    *,
    output_dir: Path,
    repo_root: Path = Path("."),
    client: httpx.Client | None = None,
) -> HistoricalMediaAcquisitionReceipt:
    manifest = _load_manifest(manifest_path, repo_root=repo_root)
    owns_client = client is None
    active_client = client or _build_acquisition_client()
    try:
        results = tuple(_fetch_asset(asset, client=active_client, output_dir=output_dir) for asset in manifest.assets)
    finally:
        if owns_client:
            active_client.close()

    receipt = HistoricalMediaAcquisitionReceipt(
        schema_name="video-channel-manager.telegram-historical-media-acquisition-receipt",
        schema_version=1,
        status="PASS",
        manifest_id=manifest.manifest_id,
        asset_count=len(results),
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
    root = argparse.ArgumentParser(description="Acquire provider-inert LordChrist historical archive media")
    root.add_argument("manifest", type=Path)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--repo-root", type=Path, default=Path("."))
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    receipt = acquire_historical_media(args.manifest, output_dir=args.output_dir, repo_root=args.repo_root)
    print(json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
