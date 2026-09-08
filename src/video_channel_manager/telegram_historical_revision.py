from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_historical_bundle import HistoricalSourceShardV1
from video_channel_manager.telegram_historical_editorial import HistoricalPost, HistoricalSource, TheologyProfile
from video_channel_manager.telegram_research import sha256_json

_GIT_BLOB_RE = r"^[0-9a-f]{40}$"
_SHA256_RE = r"^sha256:[0-9a-f]{64}$"
_PUBLICATION_RE = r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$"
_ASSET_RE = r"^img-[a-z0-9][a-z0-9-]{2,80}$"
_PRIMARY_QUOTE_ROLES = {"primary_document", "critical_edition", "official_archive", "university_archive"}


class HistoricalRevisionGitBlobRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=5, max_length=320)
    git_blob_sha: str = Field(pattern=_GIT_BLOB_RE)


class HistoricalRevisionEditorialMedia(BaseModel):
    """Reviewed editorial artwork identity, deliberately separate from historical evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(pattern=_ASSET_RE)
    asset_role: Literal["editorial_reconstruction"]
    accepted_file_name: str = Field(min_length=5, max_length=180)
    accepted_mime: Literal["image/jpeg", "image/png"]
    accepted_byte_length: int = Field(gt=0, le=10_000_000)
    accepted_width: int = Field(gt=0, le=10_000)
    accepted_height: int = Field(gt=0, le=10_000)
    accepted_sha256: str = Field(pattern=_SHA256_RE)
    placement_after: str = Field(min_length=3, max_length=40)
    depicts: str = Field(min_length=10, max_length=300)
    purpose: str = Field(min_length=10, max_length=300)
    disclosure: str = Field(min_length=30, max_length=300)
    rights_basis: str = Field(min_length=20, max_length=400)
    attribution_text: str = Field(min_length=10, max_length=300)
    transport_ready: Literal[False]
    provider_write_performed: Literal[False]

    @model_validator(mode="after")
    def editorial_media_contract(self) -> "HistoricalRevisionEditorialMedia":
        disclosure = self.disclosure.casefold()
        if "редакцион" not in disclosure or "не историческая фотография" not in disclosure:
            raise ValueError("editorial reconstruction must be explicitly disclosed as non-historical photography")
        if self.accepted_width / self.accepted_height > 20 or self.accepted_height / self.accepted_width > 20:
            raise ValueError("editorial reconstruction aspect ratio is unreasonable")
        return self


class HistoricalRevisionPackageV1(BaseModel):
    """Provider-inert additive revision package for one historical post.

    It binds reviewed copy/evidence and accepted editorial artwork bytes without
    mutating the sealed v1 HistoricalPost image model or creating Telegram
    transport authority. A later production release must separately bind a
    durable public transport locator to these exact accepted bytes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-revision-package"]
    schema_version: Literal[1]
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
    editorial_media: tuple[HistoricalRevisionEditorialMedia, ...] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def package_contract(self) -> "HistoricalRevisionPackageV1":
        paths = [self.post.path, self.verification.path, self.theology_profile.path]
        paths.extend(ref.path for ref in self.source_shards)
        if len(paths) != len(set(paths)):
            raise ValueError("revision package Git blob paths must be unique")
        media_ids = [media.asset_id for media in self.editorial_media]
        file_names = [media.accepted_file_name for media in self.editorial_media]
        media_digests = [media.accepted_sha256 for media in self.editorial_media]
        if len(media_ids) != len(set(media_ids)):
            raise ValueError("revision editorial media asset ids must be unique")
        if len(file_names) != len(set(file_names)):
            raise ValueError("revision editorial media filenames must be unique")
        if len(media_digests) != len(set(media_digests)):
            raise ValueError("revision editorial media byte identities must be unique")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalRevisionPreflightV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-revision-preflight"]
    schema_version: Literal[1]
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
    editorial_media_count: int = Field(ge=1)
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
        raise ValueError(f"invalid historical revision JSON {path}: {exc}") from exc


def _resolve_repo_path(repo_root: Path, value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("historical revision paths must be repository-relative")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("historical revision path escapes repository root")
    return resolved


def _load_bound_json(repo_root: Path, ref: HistoricalRevisionGitBlobRef, *, label: str) -> object:
    path = _resolve_repo_path(repo_root, ref.path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"missing historical revision {label}: {path}") from exc
    actual = _git_blob(data)
    if actual != ref.git_blob_sha:
        raise ValueError(f"historical revision {label} Git blob differs: {ref.path} ({actual})")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical revision {label} JSON: {ref.path}") from exc


def _validate_claim_evidence(post: HistoricalPost, sources: tuple[HistoricalSource, ...]) -> None:
    by_id = {source.source_id: source for source in sources}
    known = set(by_id)
    for claim in post.claims:
        unknown = set(claim.source_ids) - known
        if unknown:
            raise ValueError(f"historical revision claim {claim.claim_id} uses unknown sources: {sorted(unknown)}")
        bound = [by_id[source_id] for source_id in claim.source_ids]
        if claim.direct_quote:
            quoted_source = by_id.get(claim.quoted_fragment_source_id or "")
            if quoted_source is None:
                raise ValueError(f"historical revision quote {claim.claim_id} has no bound quoted source")
            if quoted_source.grade != "A" or quoted_source.evidence_role not in _PRIMARY_QUOTE_ROLES:
                raise ValueError(f"historical revision quote {claim.claim_id} lacks grade-A primary/archive evidence")
        elif claim.voice != "editorial_evaluation":
            if len({source.independence_group for source in bound}) < 2:
                raise ValueError(f"historical revision claim {claim.claim_id} requires two evidence groups")
            if not any(source.grade == "A" for source in bound):
                raise ValueError(f"historical revision claim {claim.claim_id} requires grade-A evidence")
        if claim.voice == "editorial_evaluation" and not post.theology_review.scripture_refs:
            raise ValueError("historical revision editorial evaluation requires Scripture references")


def _validate_topic_verification(
    value: object,
    package: HistoricalRevisionPackageV1,
    shard_paths: tuple[str, ...],
) -> None:
    if not isinstance(value, dict):
        raise ValueError("historical topic verification must be an object")
    if (
        value.get("schema_name") != "video-channel-manager.telegram-historical-topic-verification"
        or value.get("schema_version") != 1
        or value.get("publication_id") != package.publication_id
        or value.get("reader_copy_result") != "accepted_for_v3_integration"
        or value.get("provider_write_performed") is not False
    ):
        raise ValueError("historical topic verification header differs from the revision package")
    checked_on = date.fromisoformat(str(value.get("checked_on") or ""))
    if checked_on > package.checked_on:
        raise ValueError("historical topic verification is newer than the revision package")
    reviewed = value.get("reviewed_document_urls")
    primary = value.get("primary_document_urls")
    secondary = value.get("institutional_or_scholarly_urls")
    if not all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in (reviewed, primary, secondary)):
        raise ValueError("historical topic verification URL counts are invalid")
    assert isinstance(reviewed, int) and isinstance(primary, int) and isinstance(secondary, int)
    if reviewed <= 0 or primary + secondary != reviewed:
        raise ValueError("historical topic verification URL counts do not reconcile")
    verified_shards = value.get("source_shards")
    if not isinstance(verified_shards, list) or any(not isinstance(item, str) for item in verified_shards):
        raise ValueError("historical topic verification source_shards are invalid")
    if not set(verified_shards).issubset(set(shard_paths)):
        raise ValueError("historical topic verification references an unbound source shard")


def load_historical_revision_package(
    package_path: Path,
    *,
    repo_root: Path = Path("."),
) -> HistoricalRevisionPackageV1:
    resolved = package_path if package_path.is_absolute() else _resolve_repo_path(repo_root, package_path)
    return HistoricalRevisionPackageV1.model_validate(_read_json(resolved))


def preflight_historical_revision(
    package_path: Path,
    *,
    repo_root: Path = Path("."),
) -> HistoricalRevisionPreflightV1:
    package = load_historical_revision_package(package_path, repo_root=repo_root)
    post = HistoricalPost.model_validate(_load_bound_json(repo_root, package.post, label="post"))
    theology = TheologyProfile.model_validate(
        _load_bound_json(repo_root, package.theology_profile, label="theology profile")
    )
    if post.publication_id != package.publication_id:
        raise ValueError("historical revision publication id differs from the bound post")
    if post.images:
        raise ValueError("historical revision editorial artwork must remain separate from HistoricalPost.images")
    if theology.checked_on > package.checked_on:
        raise ValueError("historical revision theology profile is newer than the package")

    sources: list[HistoricalSource] = []
    shard_paths: list[str] = []
    for index, ref in enumerate(package.source_shards, start=1):
        shard = HistoricalSourceShardV1.model_validate(
            _load_bound_json(repo_root, ref, label=f"source shard {index}")
        )
        if shard.checked_on > package.checked_on:
            raise ValueError(f"historical revision source shard is newer than the package: {ref.path}")
        shard_paths.append(ref.path)
        sources.extend(shard.sources)

    source_ids = [source.source_id for source in sources]
    source_urls = [source.url for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("historical revision source ids must be unique across bound shards")
    if len(source_urls) != len(set(source_urls)):
        raise ValueError("historical revision source URLs must be unique across bound shards")
    source_tuple = tuple(sources)
    _validate_claim_evidence(post, source_tuple)

    verification = _load_bound_json(repo_root, package.verification, label="topic verification")
    _validate_topic_verification(verification, package, tuple(shard_paths))

    placement_targets = {"title", "lead", "evidence", "theology"}
    placement_targets.update(section.section_id for section in post.sections)
    for media in package.editorial_media:
        if media.placement_after not in placement_targets:
            raise ValueError(f"historical revision media placement does not exist: {media.placement_after}")

    return HistoricalRevisionPreflightV1(
        schema_name="video-channel-manager.telegram-historical-revision-preflight",
        schema_version=1,
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
        editorial_media_count=len(package.editorial_media),
        transport_ready_media_count=0,
        provider_writes_authorized=False,
        live_eligible=False,
        provider_write_performed=False,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Validate provider-inert LordChrist historical revision packages")
    root.add_argument("package", type=Path)
    root.add_argument("--repo-root", type=Path, default=Path("."))
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = preflight_historical_revision(args.package, repo_root=args.repo_root)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
