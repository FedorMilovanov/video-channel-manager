from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import urllib.parse
from datetime import date
from pathlib import Path
from typing import Literal, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA1_RE = r"^[0-9a-f]{40}$"
_SHA256_RE = r"^sha256:[0-9a-f]{64}$"
_PUBLICATION_RE = r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$"
_SOURCE_RE = r"^src-[a-z0-9][a-z0-9-]{2,100}$"
_FILE_RE = r"^[a-z0-9][a-z0-9._-]{2,160}$"

_ALLOWED_EXACT_HOSTS = {
    "commons.wikimedia.org",
    "upload.wikimedia.org",
    "www.gospelstudies.org.uk",
    "gospelstudies.org.uk",
    "baptiststudiesonline.com",
    "missiology.org.uk",
    "www.missiology.org.uk",
    "capito.iterpubs.org",
    "archive.org",
}
_ALLOWED_HOST_SUFFIXES = (".archive.org",)
_ALLOWED_MIME = {"image/jpeg", "image/png", "application/pdf"}
_USER_AGENT = "video-channel-manager-historical-media/1 (+https://github.com/FedorMilovanov/video-channel-manager)"
_MAX_REDIRECTS = 5


class HistoricalMediaAcquisitionItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=_SOURCE_RE)
    publication_id: str = Field(pattern=_PUBLICATION_RE)
    slot: Literal["hero", "document", "opposition"]
    source_page_url: str = Field(min_length=12, max_length=500)
    download_url: str = Field(min_length=12, max_length=800)
    expected_mime: Literal["image/jpeg", "image/png", "application/pdf"]
    expected_source_sha1: str | None = Field(default=None, pattern=_SHA1_RE)
    max_bytes: int = Field(gt=0, le=50_000_000)
    output_file: str = Field(pattern=_FILE_RE)
    rights_status: Literal[
        "public_domain",
        "cc_by_4_0",
        "cc_by_sa_4_0",
        "source_only_rights_review_required",
    ]
    rights_evidence_url: str = Field(min_length=12, max_length=500)
    attribution_text: str = Field(min_length=5, max_length=400)
    evidence_use: Literal["historical_primary_visual", "historical_context_visual", "source_only"]

    @model_validator(mode="after")
    def validate_urls_and_output(self) -> "HistoricalMediaAcquisitionItem":
        _validate_https_url(self.source_page_url, allow_any_host=True)
        _validate_https_url(self.rights_evidence_url, allow_any_host=True)
        _validate_https_url(self.download_url, allow_any_host=False)
        suffix = Path(self.output_file).suffix.casefold()
        expected_suffixes = {
            "image/jpeg": {".jpg", ".jpeg"},
            "image/png": {".png"},
            "application/pdf": {".pdf"},
        }
        if suffix not in expected_suffixes[self.expected_mime]:
            raise ValueError("historical media output extension differs from expected MIME")
        if self.rights_status == "source_only_rights_review_required" and self.evidence_use != "source_only":
            raise ValueError("rights-review-required acquisition cannot be used as a historical visual")
        return self


class HistoricalMediaAcquisitionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-media-acquisition-manifest"]
    schema_version: Literal[1]
    manifest_id: str = Field(pattern=r"^historical-media-acquisition-[a-z0-9][a-z0-9-]{4,100}$")
    owning_issue: Literal[561]
    checked_on: date
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    state: Literal["provider_inert"]
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    provider_write_performed: Literal[False]
    items: tuple[HistoricalMediaAcquisitionItem, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def unique_items(self) -> "HistoricalMediaAcquisitionManifest":
        source_ids = [item.source_id for item in self.items]
        outputs = [item.output_file for item in self.items]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("historical media acquisition source ids must be unique")
        if len(outputs) != len(set(outputs)):
            raise ValueError("historical media acquisition output files must be unique")
        return self

    @property
    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


class HistoricalMediaAcquisitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    publication_id: str
    slot: str
    source_page_url: str
    requested_url: str
    final_url: str
    content_type: str
    byte_length: int = Field(gt=0)
    sha1: str = Field(pattern=_SHA1_RE)
    sha256: str = Field(pattern=_SHA256_RE)
    git_blob_sha: str = Field(pattern=_SHA1_RE)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    output_file: str
    rights_status: str
    rights_evidence_url: str
    attribution_text: str
    evidence_use: str
    provider_write_performed: Literal[False]


class HistoricalMediaAcquisitionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-media-acquisition-report"]
    schema_version: Literal[1]
    status: Literal["PASS"]
    manifest_id: str
    manifest_sha256: str = Field(pattern=_SHA256_RE)
    acquired_count: int = Field(ge=1)
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    provider_write_performed: Literal[False]
    items: tuple[HistoricalMediaAcquisitionResult, ...]

    @model_validator(mode="after")
    def report_contract(self) -> "HistoricalMediaAcquisitionReport":
        if self.acquired_count != len(self.items):
            raise ValueError("historical media acquisition report count does not reconcile")
        source_ids = [item.source_id for item in self.items]
        output_files = [item.output_file for item in self.items]
        if len(source_ids) != len(set(source_ids)) or len(output_files) != len(set(output_files)):
            raise ValueError("historical media acquisition report identities must be unique")
        return self


def _host_allowed(host: str) -> bool:
    normalized = host.casefold().rstrip(".")
    return normalized in _ALLOWED_EXACT_HOSTS or any(normalized.endswith(suffix) for suffix in _ALLOWED_HOST_SUFFIXES)


def _validate_https_url(value: str, *, allow_any_host: bool) -> None:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("historical media URLs must use HTTPS with a hostname")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("historical media URLs must not contain credentials or fragments")
    if not allow_any_host and not _host_allowed(parsed.hostname):
        raise ValueError(f"historical media download host is not allowlisted: {parsed.hostname}")


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data, usedforsecurity=False).hexdigest()


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("historical media claimed JPEG but JPEG signature is absent")
    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9}:
            continue
        if position + 2 > len(data):
            break
        segment_length = int.from_bytes(data[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > len(data):
            raise ValueError("historical media JPEG has an invalid marker segment")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_length < 7:
                raise ValueError("historical media JPEG SOF segment is too short")
            height = int.from_bytes(data[position + 3 : position + 5], "big")
            width = int.from_bytes(data[position + 5 : position + 7], "big")
            if width <= 0 or height <= 0:
                raise ValueError("historical media JPEG dimensions are invalid")
            return width, height
        position += segment_length
    raise ValueError("historical media JPEG dimensions could not be located")


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 24:
        raise ValueError("historical media claimed PNG but PNG signature/IHDR is absent")
    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        raise ValueError("historical media PNG dimensions are invalid")
    return width, height


def _validate_binary(data: bytes, expected_mime: str) -> tuple[int | None, int | None]:
    if expected_mime == "image/jpeg":
        return _jpeg_dimensions(data)
    if expected_mime == "image/png":
        return _png_dimensions(data)
    if expected_mime == "application/pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("historical media claimed PDF but PDF signature is absent")
        return None, None
    raise ValueError(f"unsupported historical media MIME: {expected_mime}")


def _read_response_bytes(response: httpx.Response, *, max_bytes: int) -> bytes:
    declared = response.headers.get("Content-Length")
    if declared:
        try:
            declared_length = int(declared)
        except ValueError as exc:
            raise ValueError("historical media Content-Length is invalid") from exc
        if declared_length > max_bytes:
            raise ValueError("historical media Content-Length exceeds declared max_bytes")

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("historical media download exceeds declared max_bytes")
        chunks.append(chunk)
    if total == 0:
        raise ValueError("historical media download is empty")
    return b"".join(chunks)


def _download(item: HistoricalMediaAcquisitionItem) -> tuple[str, bytes]:
    current_url = item.download_url
    headers = {"User-Agent": _USER_AGENT, "Accept": item.expected_mime}
    timeout = httpx.Timeout(45.0)
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout) as client:
            for redirect_count in range(_MAX_REDIRECTS + 1):
                with client.stream("GET", current_url, headers=headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if redirect_count >= _MAX_REDIRECTS:
                            raise ValueError("historical media download exceeded redirect limit")
                        location = response.headers.get("Location")
                        if not location:
                            raise ValueError("historical media redirect has no Location header")
                        next_url = urllib.parse.urljoin(current_url, location)
                        _validate_https_url(next_url, allow_any_host=False)
                        current_url = next_url
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
                    if content_type not in _ALLOWED_MIME or content_type != item.expected_mime:
                        raise ValueError(
                            "historical media Content-Type differs: "
                            f"expected {item.expected_mime}, got {content_type or 'missing'}"
                        )
                    return str(response.url), _read_response_bytes(response, max_bytes=item.max_bytes)
    except httpx.HTTPError as exc:
        raise ValueError(f"historical media acquisition failed for {item.source_id}: {exc}") from exc
    raise ValueError(f"historical media acquisition did not resolve for {item.source_id}")


def acquire_item(item: HistoricalMediaAcquisitionItem, *, output_dir: Path) -> HistoricalMediaAcquisitionResult:
    _validate_https_url(item.download_url, allow_any_host=False)
    final_url, data = _download(item)
    width, height = _validate_binary(data, item.expected_mime)
    sha1 = hashlib.sha1(data, usedforsecurity=False).hexdigest()
    if item.expected_source_sha1 and sha1 != item.expected_source_sha1:
        raise ValueError(
            f"historical media source SHA-1 differs for {item.source_id}: "
            f"expected {item.expected_source_sha1}, got {sha1}"
        )
    sha256 = f"sha256:{hashlib.sha256(data).hexdigest()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / item.output_file
    output_path.write_bytes(data)

    return HistoricalMediaAcquisitionResult(
        source_id=item.source_id,
        publication_id=item.publication_id,
        slot=item.slot,
        source_page_url=item.source_page_url,
        requested_url=item.download_url,
        final_url=final_url,
        content_type=item.expected_mime,
        byte_length=len(data),
        sha1=sha1,
        sha256=sha256,
        git_blob_sha=_git_blob_sha(data),
        width=width,
        height=height,
        output_file=item.output_file,
        rights_status=item.rights_status,
        rights_evidence_url=item.rights_evidence_url,
        attribution_text=item.attribution_text,
        evidence_use=item.evidence_use,
        provider_write_performed=False,
    )


def load_manifest(path: Path) -> HistoricalMediaAcquisitionManifest:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical media acquisition manifest {path}: {exc}") from exc
    return HistoricalMediaAcquisitionManifest.model_validate(value)


def acquire_manifest(
    manifest_path: Path,
    *,
    output_dir: Path,
    report_path: Path,
) -> HistoricalMediaAcquisitionReport:
    manifest = load_manifest(manifest_path)
    results = tuple(acquire_item(item, output_dir=output_dir) for item in manifest.items)
    report = HistoricalMediaAcquisitionReport(
        schema_name="video-channel-manager.telegram-historical-media-acquisition-report",
        schema_version=1,
        status="PASS",
        manifest_id=manifest.manifest_id,
        manifest_sha256=manifest.digest,
        acquired_count=len(results),
        provider_writes_authorized=False,
        live_eligible=False,
        provider_write_performed=False,
        items=results,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + os.linesep,
        encoding="utf-8",
    )
    return report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Acquire immutable provider-free historical media source bytes")
    root.add_argument("manifest", type=Path)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--report", type=Path, required=True)
    root.add_argument("--validate-only", action="store_true")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.validate_only:
        manifest = load_manifest(args.manifest)
        print(json.dumps({"status": "PASS", "manifest_id": manifest.manifest_id, "manifest_sha256": manifest.digest}))
        return 0
    report = acquire_manifest(args.manifest, output_dir=args.output_dir, report_path=args.report)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
