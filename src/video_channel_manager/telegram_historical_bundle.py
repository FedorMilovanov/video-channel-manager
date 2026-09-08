from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from video_channel_manager.telegram_historical_editorial import (
    HistoricalEditorialQueueV1,
    HistoricalPost,
    HistoricalSchedule,
    HistoricalSource,
    HistoricalSourceRegistry,
    HistoricalVerification,
    TheologyProfile,
    _validate_post_evidence,
)
from video_channel_manager.telegram_historical_workflow import (
    HistoricalBundlePreflightV1,
    HistoricalCycleScaffoldV1,
    build_cycle_scaffold,
    write_scaffold,
)
from video_channel_manager.telegram_research import sha256_json

SHA_RE = r"^sha256:[0-9a-f]{64}$"
GIT_BLOB_RE = r"^[0-9a-f]{40}$"


class HistoricalSourceShardV1(BaseModel):
    """One bounded, reviewable shard of the reusable historical source catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-source-shard"]
    schema_version: Literal[1]
    shard_id: str = Field(pattern=r"^history-sources-[a-z0-9][a-z0-9-]{3,80}$")
    checked_on: date
    sources: tuple[HistoricalSource, ...] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def shard_contract(self) -> "HistoricalSourceShardV1":
        ids = [source.source_id for source in self.sources]
        urls = [source.url for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("historical source shard ids must be unique")
        if len(urls) != len(set(urls)):
            raise ValueError("historical source shard URLs must be unique")
        if any(source.checked_on > self.checked_on for source in self.sources):
            raise ValueError("historical source shard checked_on cannot predate a source check")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalSourceShardRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shard_id: str = Field(pattern=r"^history-sources-[a-z0-9][a-z0-9-]{3,80}$")
    path: str = Field(min_length=5, max_length=300)
    sha256: str = Field(pattern=SHA_RE)
    source_count: int = Field(ge=1, le=25)


class HistoricalSupplementalSourceShardRef(BaseModel):
    """Exact Git-byte binding for cycle-local evidence added on top of a stable catalog.

    The reusable base catalog stays immutable.  A later historical revision may
    add a small set of newly reviewed primary documents without copying or
    resealing every pre-existing source record.  Git blob identity binds the
    exact supplemental bytes; the materializer then derives one combined
    registry digest that is carried by the queue and re-proved at render time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    shard_id: str = Field(pattern=r"^history-sources-[a-z0-9][a-z0-9-]{3,80}$")
    path: str = Field(min_length=5, max_length=300)
    git_blob_sha: str = Field(pattern=GIT_BLOB_RE)
    source_count: int = Field(ge=1, le=25)


class HistoricalSourceCatalogManifestV1(BaseModel):
    """Hash-bound catalog of source shards.

    New cycles reuse this manifest instead of copying dozens of source records.
    A topic shard can evolve independently while the combined registry digest
    keeps every consuming cycle reproducible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-source-catalog"]
    schema_version: Literal[1]
    catalog_id: str = Field(pattern=r"^history-source-catalog-[a-z0-9][a-z0-9-]{3,80}$")
    checked_on: date
    total_sources: int = Field(ge=50, le=500)
    registry_sha256: str = Field(pattern=SHA_RE)
    shards: tuple[HistoricalSourceShardRef, ...] = Field(min_length=2, max_length=40)

    @model_validator(mode="after")
    def catalog_contract(self) -> "HistoricalSourceCatalogManifestV1":
        ids = [shard.shard_id for shard in self.shards]
        paths = [shard.path for shard in self.shards]
        if len(ids) != len(set(ids)):
            raise ValueError("historical source catalog shard ids must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("historical source catalog shard paths must be unique")
        if sum(shard.source_count for shard in self.shards) != self.total_sources:
            raise ValueError("historical source catalog total_sources must equal shard counts")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class HistoricalPostRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1, le=9)
    publication_id: str = Field(pattern=r"^lordchrist-history-[a-z0-9][a-z0-9-]{4,90}$")
    path: str = Field(min_length=5, max_length=300)
    sha256: str = Field(pattern=SHA_RE)


class HistoricalEditorialBundleManifestV1(BaseModel):
    """Small canonical cycle manifest; post bodies live in independent files.

    ``source_registry_sha256`` continues to bind the reusable base catalog.
    Optional cycle-local supplemental shards are independently byte-bound by
    Git blob identity and are combined with that base registry only during
    materialization.  This avoids mutable mega-catalogs while preserving a
    single derived registry digest at the queue/render boundary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-channel-manager.telegram-historical-editorial-bundle"]
    schema_version: Literal[1]
    cycle_id: str = Field(pattern=r"^history-cycle-[a-z0-9][a-z0-9-]{3,80}$")
    project_key: Literal["lord-god-strength"]
    channel_username: Literal["@lordchrist"]
    series_id: str = Field(pattern=r"^series-history-[a-z0-9][a-z0-9-]{3,80}$")
    purpose: Literal["evidence_backed_historical_edification"]
    state: Literal["provider_inert"]
    verification: HistoricalVerification
    schedule: HistoricalSchedule
    source_catalog_path: str = Field(min_length=5, max_length=300)
    source_catalog_sha256: str = Field(pattern=SHA_RE)
    source_registry_sha256: str = Field(pattern=SHA_RE)
    supplemental_source_shards: tuple[HistoricalSupplementalSourceShardRef, ...] = Field(
        default=(), max_length=10
    )
    theology_profile_path: str = Field(min_length=5, max_length=300)
    theology_profile_sha256: str = Field(pattern=SHA_RE)
    posts: tuple[HistoricalPostRefV1, ...] = Field(min_length=9, max_length=9)

    @model_validator(mode="after")
    def bundle_contract(self) -> "HistoricalEditorialBundleManifestV1":
        if [post.sequence for post in self.posts] != list(range(1, 10)):
            raise ValueError("historical bundle post sequence must be exactly 1..9")
        if len({post.publication_id for post in self.posts}) != 9:
            raise ValueError("historical bundle publication ids must be unique")
        if len({post.path for post in self.posts}) != 9:
            raise ValueError("historical bundle post paths must be unique")
        supplemental_ids = [shard.shard_id for shard in self.supplemental_source_shards]
        supplemental_paths = [shard.path for shard in self.supplemental_source_shards]
        if len(supplemental_ids) != len(set(supplemental_ids)):
            raise ValueError("historical supplemental source shard ids must be unique")
        if len(supplemental_paths) != len(set(supplemental_paths)):
            raise ValueError("historical supplemental source shard paths must be unique")
        return self

    @property
    def digest(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical bundle JSON {path}: {exc}") from exc


def _load_bound_json(path: Path, expected_sha256: str, *, label: str) -> object:
    payload = _load_json(path)
    actual_sha256 = sha256_json(payload)
    if actual_sha256 != expected_sha256:
        raise ValueError(f"{label} digest mismatch")
    return payload


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()  # noqa: S324


def resolve_repo_path(repo_root: Path, value: str) -> Path:
    """Resolve one manifest-owned path without allowing repository escape."""

    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("historical bundle paths must be repository-relative")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("historical bundle path escapes repository root")
    return resolved


def load_source_catalog_manifest(path: Path) -> HistoricalSourceCatalogManifestV1:
    return HistoricalSourceCatalogManifestV1.model_validate(_load_json(path))


def load_source_catalog(
    manifest_path: Path,
    *,
    repo_root: Path = Path("."),
) -> tuple[HistoricalSourceCatalogManifestV1, HistoricalSourceRegistry]:
    resolved_manifest = (
        manifest_path if manifest_path.is_absolute() else resolve_repo_path(repo_root, str(manifest_path))
    )
    manifest = load_source_catalog_manifest(resolved_manifest)

    sources: list[HistoricalSource] = []
    for ref in manifest.shards:
        shard_path = resolve_repo_path(repo_root, ref.path)
        shard_payload = _load_bound_json(
            shard_path,
            ref.sha256,
            label=f"historical source shard {ref.shard_id}",
        )
        shard = HistoricalSourceShardV1.model_validate(shard_payload)
        if shard.shard_id != ref.shard_id:
            raise ValueError(f"historical source shard identity mismatch: {ref.shard_id}")
        if len(shard.sources) != ref.source_count:
            raise ValueError(f"historical source shard count mismatch: {ref.shard_id}")
        if shard.checked_on > manifest.checked_on:
            raise ValueError(f"historical source shard is newer than catalog: {ref.shard_id}")
        sources.extend(shard.sources)

    registry = HistoricalSourceRegistry(
        schema_name="video-channel-manager.telegram-historical-source-registry",
        schema_version=1,
        checked_on=manifest.checked_on,
        sources=tuple(sources),
    )
    if len(registry.sources) != manifest.total_sources:
        raise ValueError("historical source catalog materialized count mismatch")
    if registry.digest != manifest.registry_sha256:
        raise ValueError("historical source catalog registry digest mismatch")
    return manifest, registry


def load_historical_bundle_manifest(path: Path) -> HistoricalEditorialBundleManifestV1:
    return HistoricalEditorialBundleManifestV1.model_validate(_load_json(path))


def materialize_historical_bundle(
    manifest_path: Path,
    *,
    repo_root: Path = Path("."),
) -> tuple[HistoricalEditorialBundleManifestV1, HistoricalEditorialQueueV1, HistoricalSourceRegistry, TheologyProfile]:
    resolved_manifest = (
        manifest_path if manifest_path.is_absolute() else resolve_repo_path(repo_root, str(manifest_path))
    )
    manifest = load_historical_bundle_manifest(resolved_manifest)

    catalog_path = resolve_repo_path(repo_root, manifest.source_catalog_path)
    _load_bound_json(catalog_path, manifest.source_catalog_sha256, label="historical source catalog")
    catalog, base_registry = load_source_catalog(catalog_path, repo_root=repo_root)
    if base_registry.digest != manifest.source_registry_sha256:
        raise ValueError("historical bundle base source registry digest mismatch")

    base_shard_ids = {shard.shard_id for shard in catalog.shards}
    base_shard_paths = {shard.path for shard in catalog.shards}
    supplemental_sources: list[HistoricalSource] = []
    supplemental_dates: list[date] = []
    for ref in manifest.supplemental_source_shards:
        if ref.shard_id in base_shard_ids or ref.path in base_shard_paths:
            raise ValueError("historical supplemental source shard collides with reusable base catalog")
        shard_path = resolve_repo_path(repo_root, ref.path)
        raw = shard_path.read_bytes()
        actual_blob = _git_blob_sha(raw)
        if actual_blob != ref.git_blob_sha:
            raise ValueError(f"historical supplemental source shard Git blob mismatch: {ref.shard_id}")
        shard = HistoricalSourceShardV1.model_validate(_load_json(shard_path))
        if shard.shard_id != ref.shard_id:
            raise ValueError(f"historical supplemental source shard identity mismatch: {ref.shard_id}")
        if len(shard.sources) != ref.source_count:
            raise ValueError(f"historical supplemental source shard count mismatch: {ref.shard_id}")
        if shard.checked_on > manifest.verification.checked_on:
            raise ValueError(f"historical supplemental source shard is newer than cycle verification: {ref.shard_id}")
        supplemental_sources.extend(shard.sources)
        supplemental_dates.append(shard.checked_on)

    registry = base_registry
    if supplemental_sources:
        combined_checked_on = max((base_registry.checked_on, *supplemental_dates))
        registry = HistoricalSourceRegistry(
            schema_name="video-channel-manager.telegram-historical-source-registry",
            schema_version=1,
            checked_on=combined_checked_on,
            sources=(*base_registry.sources, *supplemental_sources),
        )

    theology_path = resolve_repo_path(repo_root, manifest.theology_profile_path)
    theology_payload = _load_bound_json(
        theology_path,
        manifest.theology_profile_sha256,
        label="historical theology profile",
    )
    theology = TheologyProfile.model_validate(theology_payload)

    posts: list[HistoricalPost] = []
    for ref in manifest.posts:
        post_path = resolve_repo_path(repo_root, ref.path)
        post_payload = _load_bound_json(
            post_path,
            ref.sha256,
            label=f"historical post {ref.publication_id}",
        )
        post = HistoricalPost.model_validate(post_payload)
        if post.sequence != ref.sequence or post.publication_id != ref.publication_id:
            raise ValueError(f"historical post identity mismatch: {ref.path}")
        posts.append(post)

    queue = HistoricalEditorialQueueV1(
        schema_name="video-channel-manager.telegram-historical-editorial-queue",
        schema_version=1,
        project_key=manifest.project_key,
        channel_username=manifest.channel_username,
        series_id=manifest.series_id,
        purpose=manifest.purpose,
        state=manifest.state,
        verification=manifest.verification,
        schedule=manifest.schedule,
        source_binding_kind="catalog",
        source_binding_path=manifest.source_catalog_path,
        source_binding_sha256=manifest.source_catalog_sha256,
        source_registry_sha256=registry.digest,
        theology_profile_path=manifest.theology_profile_path,
        theology_profile_sha256=theology.digest,
        posts=tuple(posts),
    )

    if queue.verification.reviewed_urls < len(registry.sources):
        raise ValueError("reviewed_urls cannot be lower than persisted source registry size")
    if queue.verification.checked_on < registry.checked_on:
        raise ValueError("historical verification cannot predate source catalog or supplemental source shards")
    if queue.verification.checked_on < theology.checked_on:
        raise ValueError("historical verification cannot predate theology profile")
    for post in queue.posts:
        _validate_post_evidence(post, registry, theology, queue.verification.checked_on)
    return manifest, queue, registry, theology


def preflight_historical_bundle_manifest(
    manifest_path: Path,
    *,
    repo_root: Path = Path("."),
) -> HistoricalBundlePreflightV1:
    _manifest, queue, registry, theology = materialize_historical_bundle(manifest_path, repo_root=repo_root)
    return HistoricalBundlePreflightV1(
        schema_name="video-channel-manager.telegram-historical-bundle-preflight",
        schema_version=1,
        status="PASS",
        queue_digest=queue.digest,
        source_registry_digest=registry.digest,
        theology_profile_digest=theology.digest,
        source_count=len(registry.sources),
        grade_a_count=sum(source.grade == "A" for source in registry.sources),
        grade_bplus_count=sum(source.grade == "B+" for source in registry.sources),
        independent_evidence_groups=len({source.independence_group for source in registry.sources}),
        claim_count=sum(len(post.claims) for post in queue.posts),
        direct_quote_count=sum(claim.direct_quote for post in queue.posts for claim in post.claims),
        controversy_post_count=sum(post.topic_kind == "controversy" for post in queue.posts),
        martyrdom_post_count=sum(post.topic_kind == "martyrdom" for post in queue.posts),
        image_plan_count=sum(len(post.images) for post in queue.posts),
        production_ready_image_count=sum(image.production_ready for post in queue.posts for image in post.images),
        provider_writes_authorized=False,
        live_eligible=False,
        backfill_policy=queue.schedule.backfill_policy,
    )


def build_next_scaffold_from_manifest(
    manifest_path: Path,
    *,
    cycle_id: str,
    start_on: date,
    repo_root: Path = Path("."),
    slot_count: int = 9,
) -> HistoricalCycleScaffoldV1:
    manifest, _queue, registry, theology = materialize_historical_bundle(manifest_path, repo_root=repo_root)
    return build_cycle_scaffold(
        cycle_id=cycle_id,
        start_on=start_on,
        source_binding_kind="catalog",
        source_binding_path=manifest.source_catalog_path,
        source_binding_sha256=manifest.source_catalog_sha256,
        source_registry_sha256=registry.digest,
        theology_profile_path=manifest.theology_profile_path,
        theology_profile_sha256=theology.digest,
        slot_count=slot_count,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LordChrist sharded historical editorial bundles")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight", help="validate a hash-bound historical bundle manifest")
    preflight.add_argument("manifest", type=Path)
    preflight.add_argument("--repo-root", type=Path, default=Path("."))

    scaffold = sub.add_parser("scaffold-next", help="create the next provider-inert cycle scaffold")
    scaffold.add_argument("manifest", type=Path)
    scaffold.add_argument("--cycle-id", required=True)
    scaffold.add_argument("--start-on", required=True, type=date.fromisoformat)
    scaffold.add_argument("--slot-count", type=int, default=9)
    scaffold.add_argument("--repo-root", type=Path, default=Path("."))
    scaffold.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "preflight":
        report = preflight_historical_bundle_manifest(args.manifest, repo_root=args.repo_root)
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    scaffold = build_next_scaffold_from_manifest(
        args.manifest,
        cycle_id=args.cycle_id,
        start_on=args.start_on,
        repo_root=args.repo_root,
        slot_count=args.slot_count,
    )
    write_scaffold(args.output, scaffold)
    print(json.dumps({"status": "CREATED", "path": str(args.output), "digest": scaffold.digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "HistoricalEditorialBundleManifestV1",
    "HistoricalPostRefV1",
    "HistoricalSourceCatalogManifestV1",
    "HistoricalSourceShardRef",
    "HistoricalSourceShardV1",
    "HistoricalSupplementalSourceShardRef",
    "build_next_scaffold_from_manifest",
    "load_historical_bundle_manifest",
    "load_source_catalog",
    "load_source_catalog_manifest",
    "materialize_historical_bundle",
    "preflight_historical_bundle_manifest",
    "resolve_repo_path",
]
