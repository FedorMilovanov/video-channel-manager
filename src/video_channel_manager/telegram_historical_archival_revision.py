from __future__ import annotations

import argparse
import hashlib
import json
import struct
from datetime import date
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalPost, HistoricalSource, TheologyProfile
from video_channel_manager.telegram_historical_revision import (
    HistoricalRevisionGitBlobRef,
    load_historical_revision_git_blob_json,
    validate_historical_claim_evidence,
    validate_historical_topic_verification,
)
from video_channel_manager.telegram_research import sha256_json

_SHA256_RE = r"^sha256:[0-9a-f]{64}$"
_PUBLICATION_RE = r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$"
_ASSET_RE = r"^img-[a-z0-9][a-z0-9-]{2,100}$"


class HistoricalRevisionArchivalMediaV2(BaseModel):
    """One accepted archival exhibit derived from an exact acquired source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(pattern=_ASSET_RE)
    slot: Literal["hero", "document", "opposition"]
    source_id: str = Field(min_length=5, max_length=120)
    acquisition_asset_id: str = Field(pattern=_ASSET_RE)
    exhibit_kind: Literal[
        "archival_portrait",
        "primary_document_facsimile",
        "critical_edition_facsimile",
        "contextual_historical_map",
        "institutional_catalog_record",
        "official_document_excerpt",
    ]
    accepted_file: HistoricalRevisionGitBlobRef
    accepted_mime: Literal["image/jpeg", "image/png"]
    accepted_byte_length: int = Field(gt=0, le=10_000_000)
    accepted_width: int = Field(gt=0, le=20_000)
    accepted_height: int = Field(gt=0, le=20_000)
    accepted_sha256: str = Field(pattern=_SHA256_RE)
    placement_after: str = Field(min_length=3, max_length=40)
    depicts: str = Field(min_length=10, max_length=400)
    purpose: str = Field(min_length=10, max_length=400)
    claim_boundary: str = Field(min_length=20, max_length=500)
    rights_basis: str = Field(min_length=20, max_length=500)
    attribution_text: str = Field(min_length=10, max_length=300)
    transport_ready: Literal[False]
    provider_write_performed: Literal[False]

    @model_validator(mode="after")
    def archival_media_contract(self) -> "HistoricalRevisionArchivalMediaV2":
        suffix = ".jpg" if self.accepted_mime == "image/jpeg" else ".png"
        if not self.accepted_file.path.casefold().endswith(suffix):
            raise ValueError("archival revision media suffix differs from accepted MIME")
        if self.accepted_width / self.accepted_height > 20 or self.accepted_height / self.accepted_width > 20:
            raise ValueError("archival revision media aspect ratio is unreasonable")
        return self


class HistoricalRevisionPackageV2(BaseModel):
    """Provider-inert revision package for exact archival source exhibits.

    V2 is deliberately separate from V1 editorial reconstruction. It binds each
    accepted image to the exact source registry identity, acquisition asset,
    deterministic render receipt and committed Git blob without creating any
    Telegram transport authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-revision-package"]
    schema_version: Literal[2]
    revision_id: str = Field(pattern=r"^historical-revision-[a-z0-9][a-z0-9-]{4,100}$")
    owning_issue: Literal[561]
    checked_on: date
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    publication_id: str = Field(pattern=_PUBLICATION_RE)
    state: Literal["provider_inert"]
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    post: HistoricalRevisionGitBlobRef
    verification: HistoricalRevisionGitBlobRef
    theology_profile: HistoricalRevisionGitBlobRef
    source_shards: tuple[HistoricalRevisionGitBlobRef, ...] = Field(min_length=2, max_length=12)
    acquisition_manifest: HistoricalRevisionGitBlobRef
    render_receipt: HistoricalRevisionGitBlobRef
    archival_media: tuple[HistoricalRevisionArchivalMediaV2, ...] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def package_contract(self) -> "HistoricalRevisionPackageV2":
        refs = [
            self.post,
            self.verification,
            self.theology_profile,
            self.acquisition_manifest,
            self.render_receipt,
            *self.source_shards,
        ]
        ref_paths = [ref.path for ref in refs]
        if len(ref_paths) != len(set(ref_paths)):
            raise ValueError("archival revision Git blob paths must be unique")
        ids = [media.asset_id for media in self.archival_media]
        files = [media.accepted_file.path for media in self.archival_media]
        slots = [media.slot for media in self.archival_media]
        if len(ids) != len(set(ids)):
            raise ValueError("archival revision media asset ids must be unique")
        if len(files) != len(set(files)):
            raise ValueError("archival revision media paths must be unique")
        if len(slots) != len(set(slots)):
            raise ValueError("archival revision media slots must be unique")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalRevisionPreflightV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-revision-preflight"]
    schema_version: Literal[2]
    status: Literal["PASS"]
    revision_id: str
    revision_sha256: str = Field(pattern=_SHA256_RE)
    publication_id: str
    source_count: int = Field(ge=1)
    grade_a_count: int = Field(ge=1)
    grade_bplus_count: int = Field(ge=0)
    independent_evidence_groups: int = Field(ge=2)
    claim_count: int = Field(ge=1)
    direct_quote_count: int = Field(ge=0)
    archival_media_count: int = Field(ge=1)
    transport_ready_media_count: Literal[0]
    provider_writes_authorized: Literal[False]
    live_eligible: Literal[False]
    provider_write_performed: Literal[False]


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical archival revision JSON {path}: {exc}") from exc


def _resolve_repo_path(repo_root: Path, value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("historical archival revision paths must be repository-relative")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("historical archival revision path escapes repository root")
    return resolved


def _probe_image(data: bytes) -> tuple[Literal["image/jpeg", "image/png"], int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise ValueError("invalid archival revision PNG")
        width, height = struct.unpack(">II", data[16:24])
        if width <= 0 or height <= 0:
            raise ValueError("invalid archival revision PNG dimensions")
        return "image/png", width, height
    if data.startswith(b"\xff\xd8"):
        offset = 2
        sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
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
                raise ValueError("invalid archival revision JPEG segment")
            if marker in sof_markers:
                if segment_length < 7:
                    raise ValueError("invalid archival revision JPEG SOF segment")
                height = int.from_bytes(data[offset + 3 : offset + 5], "big")
                width = int.from_bytes(data[offset + 5 : offset + 7], "big")
                if width <= 0 or height <= 0:
                    raise ValueError("invalid archival revision JPEG dimensions")
                return "image/jpeg", width, height
            offset += segment_length
        raise ValueError("archival revision JPEG dimensions not found")
    raise ValueError("archival revision media must be JPEG or PNG")


def _verify_binary_identity(
    ref: HistoricalRevisionGitBlobRef,
    *,
    repo_root: Path,
    sha256: str,
    byte_length: int,
    mime: str,
    width: int,
    height: int,
) -> None:
    path = _resolve_repo_path(repo_root, ref.path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"missing archival revision media: {ref.path}") from exc
    if _git_blob(data) != ref.git_blob_sha:
        raise ValueError(f"archival revision media Git blob differs: {ref.path}")
    if "sha256:" + hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"archival revision media SHA-256 differs: {ref.path}")
    if len(data) != byte_length:
        raise ValueError(f"archival revision media byte length differs: {ref.path}")
    actual_mime, actual_width, actual_height = _probe_image(data)
    if (actual_mime, actual_width, actual_height) != (mime, width, height):
        raise ValueError(f"archival revision media probe differs: {ref.path}")


def load_historical_archival_revision_package(
    package_path: Path,
    *,
    repo_root: Path = Path("."),
) -> HistoricalRevisionPackageV2:
    resolved = package_path if package_path.is_absolute() else _resolve_repo_path(repo_root, package_path)
    return HistoricalRevisionPackageV2.model_validate(_read_json(resolved))


def preflight_historical_archival_revision(
    package_path: Path,
    *,
    repo_root: Path = Path("."),
) -> HistoricalRevisionPreflightV2:
    package = load_historical_archival_revision_package(package_path, repo_root=repo_root)
    post = HistoricalPost.model_validate(load_historical_revision_git_blob_json(repo_root, package.post, label="post"))
    theology = TheologyProfile.model_validate(
        load_historical_revision_git_blob_json(repo_root, package.theology_profile, label="theology profile")
    )
    if post.publication_id != package.publication_id:
        raise ValueError("historical archival revision publication id differs from bound post")
    if post.images:
        raise ValueError("historical archival revision media must remain separate from HistoricalPost.images")
    if theology.checked_on > package.checked_on:
        raise ValueError("historical archival revision theology profile is newer than package")

    sources: list[HistoricalSource] = []
    shard_paths: list[str] = []
    for index, ref in enumerate(package.source_shards, start=1):
        shard = HistoricalSourceShardV1.model_validate(
            load_historical_revision_git_blob_json(repo_root, ref, label=f"source shard {index}")
        )
        if shard.checked_on > package.checked_on:
            raise ValueError(f"historical archival revision source shard is newer than package: {ref.path}")
        shard_paths.append(ref.path)
        sources.extend(shard.sources)
    source_ids = [source.source_id for source in sources]
    source_urls = [source.url for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("historical archival revision source ids must be unique across shards")
    if len(source_urls) != len(set(source_urls)):
        raise ValueError("historical archival revision source URLs must be unique across shards")
    source_tuple = tuple(sources)
    source_by_id = {source.source_id: source for source in source_tuple}
    validate_historical_claim_evidence(post, source_tuple)

    verification = load_historical_revision_git_blob_json(repo_root, package.verification, label="topic verification")
    validate_historical_topic_verification(
        verification,
        publication_id=package.publication_id,
        checked_on=package.checked_on,
        shard_paths=tuple(shard_paths),
    )
    if not isinstance(verification, dict) or not isinstance(verification.get("visual_plan"), list):
        raise ValueError("historical archival revision verification has no visual plan")
    planned = {
        (item.get("slot"), item.get("source_id"))
        for item in verification["visual_plan"]
        if isinstance(item, dict) and item.get("production_ready") is False
    }
    actual = {(media.slot, media.source_id) for media in package.archival_media}
    if actual != planned:
        raise ValueError("historical archival revision media do not exactly close the bound visual plan")

    acquisition = load_historical_revision_git_blob_json(
        repo_root, package.acquisition_manifest, label="acquisition manifest"
    )
    if not isinstance(acquisition, dict):
        raise ValueError("historical archival acquisition manifest must be an object")
    if (
        acquisition.get("schema_name") != "video-channel-manager.telegram-historical-media-acquisition-manifest"
        or acquisition.get("provider_writes_authorized") is not False
        or acquisition.get("live_eligible") is not False
    ):
        raise ValueError("historical archival acquisition manifest is not provider-inert")
    acquisition_assets = acquisition.get("assets")
    if not isinstance(acquisition_assets, list):
        raise ValueError("historical archival acquisition manifest assets are invalid")
    acquired_by_id = {
        item.get("asset_id"): item
        for item in acquisition_assets
        if isinstance(item, dict) and isinstance(item.get("asset_id"), str)
    }

    render = load_historical_revision_git_blob_json(repo_root, package.render_receipt, label="render receipt")
    if not isinstance(render, dict):
        raise ValueError("historical archival render receipt must be an object")
    if (
        render.get("schema_name") != "video-channel-manager.telegram-historical-media-render-receipt"
        or render.get("provider_writes_authorized") is not False
        or render.get("live_eligible") is not False
        or render.get("provider_write_performed") is not False
    ):
        raise ValueError("historical archival render receipt is not provider-inert")
    render_outputs = render.get("outputs")
    if not isinstance(render_outputs, list):
        raise ValueError("historical archival render receipt outputs are invalid")

    placement_targets = {"title", "lead", "evidence", "theology"}
    placement_targets.update(section.section_id for section in post.sections)
    for media in package.archival_media:
        source = source_by_id.get(media.source_id)
        if source is None:
            raise ValueError(f"historical archival media source is not in bound shards: {media.source_id}")
        if media.placement_after not in placement_targets:
            raise ValueError(f"historical archival media placement does not exist: {media.placement_after}")
        acquired = acquired_by_id.get(media.acquisition_asset_id)
        if not isinstance(acquired, dict):
            raise ValueError(f"historical archival acquisition asset is missing: {media.acquisition_asset_id}")
        if (
            acquired.get("publication_id") != package.publication_id
            or acquired.get("slot") != media.slot
            or acquired.get("source_id") != media.source_id
            or acquired.get("source_page_url") != source.url
            or acquired.get("rights_basis") != media.rights_basis
            or acquired.get("attribution_text") != media.attribution_text
            or acquired.get("provider_write_performed") is not False
        ):
            raise ValueError(f"historical archival acquisition binding differs: {media.asset_id}")
        matches = [
            item
            for item in render_outputs
            if isinstance(item, dict)
            and item.get("publication_id") == package.publication_id
            and item.get("slot") == media.slot
            and item.get("source_asset_id") == media.acquisition_asset_id
            and item.get("path") == media.accepted_file.path
        ]
        if len(matches) != 1:
            raise ValueError(f"historical archival render binding is not unique: {media.asset_id}")
        rendered = matches[0]
        if (
            rendered.get("sha256") != media.accepted_sha256
            or rendered.get("byte_length") != media.accepted_byte_length
            or rendered.get("mime") != media.accepted_mime
            or rendered.get("width") != media.accepted_width
            or rendered.get("height") != media.accepted_height
        ):
            raise ValueError(f"historical archival render identity differs: {media.asset_id}")
        _verify_binary_identity(
            media.accepted_file,
            repo_root=repo_root,
            sha256=media.accepted_sha256,
            byte_length=media.accepted_byte_length,
            mime=media.accepted_mime,
            width=media.accepted_width,
            height=media.accepted_height,
        )

    return HistoricalRevisionPreflightV2(
        schema_name="video-channel-manager.telegram-historical-revision-preflight",
        schema_version=2,
        status="PASS",
        revision_id=package.revision_id,
        revision_sha256=package.digest,
        publication_id=package.publication_id,
        source_count=len(source_tuple),
        grade_a_count=sum(source.grade == "A" for source in source_tuple),
        grade_bplus_count=sum(source.grade == "B+" for source in source_tuple),
        independent_evidence_groups=len({source.independence_group for source in source_tuple}),
        claim_count=len(post.claims),
        direct_quote_count=sum(claim.direct_quote for claim in post.claims),
        archival_media_count=len(package.archival_media),
        transport_ready_media_count=0,
        provider_writes_authorized=False,
        live_eligible=False,
        provider_write_performed=False,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Validate provider-inert LordChrist archival revision packages v2")
    root.add_argument("package", type=Path)
    root.add_argument("--repo-root", type=Path, default=Path("."))
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = preflight_historical_archival_revision(args.package, repo_root=args.repo_root)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
