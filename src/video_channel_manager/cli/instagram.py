from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError
from rich.console import Console

from video_channel_manager.config import get_settings
from video_channel_manager.editorial._project_profiles import LEGENDARY_POET, PROJECT_CHANNEL_IDS, PROJECT_KEYS
from video_channel_manager.editorial.instagram_factory_coverage import (
    InstagramFactoryCoverageError,
    build_instagram_factory_coverage,
)
from video_channel_manager.editorial.instagram_historical_backlog import (
    InstagramHistoricalBacklogError,
    build_instagram_historical_backlog,
)
from video_channel_manager.editorial.instagram_media_routing import (
    InstagramMediaRoutingError,
    build_instagram_video_routes,
)
from video_channel_manager.editorial.instagram_reel_queue import (
    InstagramReelQueueError,
    build_instagram_reel_queue,
)
from video_channel_manager.editorial.instagram_video_intake import (
    InstagramVideoIntakeError,
    build_instagram_video_intake,
)
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.exchange.instagram_reels import InstagramReelFactoryRegistry
from video_channel_manager.exchange.instagram_video import (
    InstagramMediaReview,
    InstagramVideoIntakeArtifact,
    InstagramVideoRouteArtifact,
)
from video_channel_manager.local_media import MediaArtifactError, MediaArtifactEvidence, load_media_artifact_manifest


console = Console()
instagram_app = typer.Typer(no_args_is_help=True, help="Provider-inert Instagram content preparation.")

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_LEGENDARY_POET_MAPPING = _REPOSITORY_ROOT / "content" / "mappings" / "youtube-vk-reviewed-20260727.json"
_LEGENDARY_POET_REVIEWED = _REPOSITORY_ROOT / "content" / "youtube-comments"


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def _load_mapping(path: Path) -> tuple[dict[str, str], str]:
    raw = _read_bytes(path)
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid mapping JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected mapping JSON object: {path}")

    mapping: dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ValueError(f"mapping contains an invalid YouTube video ID: {raw_key!r}")
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError(f"mapping contains an invalid provider target for {raw_key!r}")
        mapping[raw_key.strip()] = raw_value.strip()
    return mapping, _sha256_bytes(raw)


def _load_reviewed_video_ids(path: Path, *, project_key: str) -> tuple[set[str], str]:
    if not path.is_dir():
        raise ValueError(f"reviewed editorial directory does not exist: {path}")

    expected_channels = PROJECT_CHANNEL_IDS.get(project_key, frozenset())
    ids: set[str] = set()
    digest = hashlib.sha256()
    for source_path in sorted(path.glob("*.json"), key=lambda item: item.name):
        raw = _read_bytes(source_path)
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid reviewed editorial JSON {source_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"expected reviewed editorial JSON object: {source_path}")

        video_id = payload.get("video_id")
        channel_id = payload.get("channel_id")
        if not isinstance(video_id, str) or video_id.strip() != source_path.stem:
            raise ValueError(f"reviewed editorial video_id does not match filename: {source_path}")
        if not isinstance(channel_id, str) or channel_id.strip() not in expected_channels:
            raise ValueError(f"reviewed editorial channel does not match project {project_key}: {source_path}")
        if video_id in ids:
            raise ValueError(f"duplicate reviewed editorial video_id: {video_id}")
        ids.add(video_id)

        digest.update(source_path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")

    return ids, f"sha256:{digest.hexdigest()}"


def _resolve_supporting_sources(
    *,
    project_key: str,
    mapping_path: Path | None,
    reviewed_dir: Path | None,
) -> tuple[dict[str, str], str | None, set[str], str | None]:
    if project_key == LEGENDARY_POET:
        mapping_path = mapping_path or _LEGENDARY_POET_MAPPING
        reviewed_dir = reviewed_dir or _LEGENDARY_POET_REVIEWED

    if mapping_path is None:
        mapping: dict[str, str] = {}
        mapping_sha256 = None
    else:
        mapping, mapping_sha256 = _load_mapping(mapping_path)

    if reviewed_dir is None:
        reviewed_ids: set[str] = set()
        reviewed_sha256 = None
    else:
        reviewed_ids, reviewed_sha256 = _load_reviewed_video_ids(reviewed_dir, project_key=project_key)

    return mapping, mapping_sha256, reviewed_ids, reviewed_sha256


def _read_audit_package(path: Path) -> tuple[AuditPackage, str]:
    raw = _read_bytes(path)
    try:
        audit = AuditPackage.model_validate_json(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid AuditPackage {path}: {exc}") from exc
    return audit, _sha256_bytes(raw)


def _read_intake(path: Path) -> tuple[InstagramVideoIntakeArtifact, str]:
    raw = _read_bytes(path)
    try:
        intake = InstagramVideoIntakeArtifact.model_validate_json(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Instagram video intake {path}: {exc}") from exc
    return intake, _sha256_bytes(raw)


def _read_reel_registry(path: Path) -> tuple[InstagramReelFactoryRegistry, str]:
    raw = _read_bytes(path)
    try:
        registry = InstagramReelFactoryRegistry.model_validate_json(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Instagram Reel registry {path}: {exc}") from exc
    return registry, _sha256_bytes(raw)


def _read_media_route(path: Path) -> tuple[InstagramVideoRouteArtifact, str]:
    raw = _read_bytes(path)
    try:
        route = InstagramVideoRouteArtifact.model_validate_json(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid Instagram media route {path}: {exc}") from exc
    return route, _sha256_bytes(raw)


def _load_media_manifest_dir(path: Path | None) -> dict[str, MediaArtifactEvidence]:
    if path is None:
        return {}
    if not path.is_dir():
        raise ValueError(f"media manifest directory does not exist: {path}")

    by_video_id: dict[str, MediaArtifactEvidence] = {}
    for manifest_path in sorted(path.glob("*.json"), key=lambda item: item.name):
        evidence = load_media_artifact_manifest(manifest_path)
        video_id = evidence.source.source_id
        if video_id in by_video_id:
            raise ValueError(f"duplicate media evidence source_id: {video_id}")
        by_video_id[video_id] = evidence
    return by_video_id


def _load_media_review_dir(path: Path | None) -> dict[str, InstagramMediaReview]:
    if path is None:
        return {}
    if not path.is_dir():
        raise ValueError(f"media review directory does not exist: {path}")

    by_video_id: dict[str, InstagramMediaReview] = {}
    for review_path in sorted(path.glob("*.json"), key=lambda item: item.name):
        raw = _read_bytes(review_path)
        try:
            review = InstagramMediaReview.model_validate_json(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid Instagram media review {review_path}: {exc}") from exc
        if review.youtube_video_id != review_path.stem:
            raise ValueError(f"Instagram media review video ID does not match filename: {review_path}")
        if review.youtube_video_id in by_video_id:
            raise ValueError(f"duplicate Instagram media review video ID: {review.youtube_video_id}")
        by_video_id[review.youtube_video_id] = review
    return by_video_id


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


@instagram_app.command("video-intake")
def video_intake(
    audit_package: Annotated[Path, typer.Argument(help="Exact read-only YouTube AuditPackage JSON")],
    project_key: Annotated[str, typer.Option("--project", help="Canonical repository project_key")],
    mapping: Annotated[
        Path | None,
        typer.Option("--mapping", help="Optional exact YouTube→provider identity mapping JSON"),
    ] = None,
    reviewed_dir: Annotated[
        Path | None,
        typer.Option("--reviewed-dir", help="Optional directory of reviewed YouTube editorial records"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Build an immutable-evidence, provider-inert Instagram video intake artifact."""

    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        choices = ", ".join(sorted(PROJECT_KEYS))
        console.print(f"[red]Unknown project:[/red] {project_key}. Registered projects: {choices}")
        raise typer.Exit(code=2)

    try:
        audit, audit_sha256 = _read_audit_package(audit_package)
        mapping_payload, mapping_sha256, reviewed_ids, reviewed_sha256 = _resolve_supporting_sources(
            project_key=normalized_project,
            mapping_path=mapping,
            reviewed_dir=reviewed_dir,
        )
        result = build_instagram_video_intake(
            audit,
            project_key=normalized_project,
            frozen_youtube_vk_mapping=mapping_payload,
            reviewed_video_ids=reviewed_ids,
            source_audit_sha256=audit_sha256,
            frozen_mapping_sha256=mapping_sha256,
            reviewed_corpus_sha256=reviewed_sha256,
        )
    except (InstagramVideoIntakeError, OSError, ValueError) as exc:
        console.print(f"[red]Instagram video intake failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        settings = get_settings()
        output = settings.data_dir / "reports" / f"instagram-{normalized_project}-{audit.snapshot_id}-video-intake.json"
    _write_json(output, result)

    counts = result["counts"]
    console.print(
        f"[green]Built provider-inert Instagram video intake → {output}[/green]\n"
        f"Project: {normalized_project} | Current: {counts['current_videos']} | "
        f"New vs mapping: {counts['new_current_vs_frozen_mapping']} | "
        f"Format unknown: {counts['format_unknown']}"
    )


@instagram_app.command("media-route")
def media_route(
    intake_path: Annotated[Path, typer.Argument(help="Exact Instagram video intake JSON")],
    media_manifest_dir: Annotated[
        Path | None,
        typer.Option("--media-manifest-dir", help="Directory of exact MediaArtifactEvidence JSON manifests"),
    ] = None,
    media_review_dir: Annotated[
        Path | None,
        typer.Option("--media-review-dir", help="Directory of exact Instagram media-review JSON records"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Route all intake videos from exact technical and rights/provenance evidence."""

    try:
        intake, intake_sha256 = _read_intake(intake_path)
        media = _load_media_manifest_dir(media_manifest_dir)
        reviews = _load_media_review_dir(media_review_dir)
        result = build_instagram_video_routes(
            intake,
            source_intake_sha256=intake_sha256,
            media_by_video_id=media,
            reviews_by_video_id=reviews,
        )
    except (InstagramMediaRoutingError, MediaArtifactError, OSError, ValueError) as exc:
        console.print(f"[red]Instagram media routing failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        settings = get_settings()
        output = (
            settings.data_dir
            / "reports"
            / f"instagram-{intake.project_key}-{intake.source_snapshot_id}-media-route.json"
        )
    _write_json(output, result.model_dump(mode="json"))

    counts = result.counts
    console.print(
        f"[green]Built provider-inert Instagram media routing → {output}[/green]\n"
        f"Total: {counts.total} | Direct remaster: {counts.direct_remaster} | "
        f"Editorial extract: {counts.editorial_extract} | Rebuild: {counts.editorial_rebuild} | "
        f"Hold: {counts.hold} | Source binding required: {counts.source_binding_required}"
    )


@instagram_app.command("reel-queue")
def reel_queue(
    registry_path: Annotated[Path, typer.Argument(help="Exact Instagram Reel factory registry JSON")],
    media_route_path: Annotated[
        Path | None,
        typer.Option("--media-route", help="Optional exact Instagram media-route artifact JSON"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Build a deterministic provider-inert Reel production-readiness queue."""

    try:
        registry, registry_sha256 = _read_reel_registry(registry_path)
        if media_route_path is None:
            route = None
            route_sha256 = None
        else:
            route, route_sha256 = _read_media_route(media_route_path)
        result = build_instagram_reel_queue(
            registry,
            source_registry_sha256=registry_sha256,
            media_route=route,
            source_media_route_sha256=route_sha256,
        )
    except (InstagramReelQueueError, OSError, ValueError) as exc:
        console.print(f"[red]Instagram Reel queue failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        settings = get_settings()
        output = settings.data_dir / "reports" / f"instagram-{registry.project_key}-reel-queue.json"
    _write_json(output, result.model_dump(mode="json"))

    counts = result.counts
    console.print(
        f"[green]Built provider-inert Instagram Reel queue → {output}[/green]\n"
        f"Total: {counts.total} | Source-led ready: {counts.source_led_ready} | "
        f"Text binding: {counts.exact_text_binding_required} | "
        f"Source binding: {counts.source_binding_required} | "
        f"Materialization: {counts.materialization_required} | "
        f"Timing: {counts.timing_selection_required} | Media edit ready: {counts.media_edit_ready} | "
        f"Rebuild: {counts.editorial_rebuild_required} | Hold: {counts.hold}"
    )


@instagram_app.command("factory-coverage")
def factory_coverage(
    intake_path: Annotated[Path, typer.Argument(help="Exact Instagram video intake JSON")],
    registry_path: Annotated[Path, typer.Argument(help="Exact Instagram Reel factory registry JSON")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Partition every current intake video by exact Reel-factory editorial coverage."""

    try:
        intake, intake_sha256 = _read_intake(intake_path)
        registry, registry_sha256 = _read_reel_registry(registry_path)
        result = build_instagram_factory_coverage(
            intake,
            registry,
            source_intake_sha256=intake_sha256,
            source_registry_sha256=registry_sha256,
        )
    except (InstagramFactoryCoverageError, OSError, ValueError) as exc:
        console.print(f"[red]Instagram factory coverage failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        settings = get_settings()
        output = (
            settings.data_dir
            / "reports"
            / f"instagram-{intake.project_key}-{intake.source_snapshot_id}-factory-coverage.json"
        )
    _write_json(output, result.model_dump(mode="json"))

    counts = result.counts
    console.print(
        f"[green]Built provider-inert Instagram factory coverage → {output}[/green]\n"
        f"Current: {counts.total_current_videos} | Covered: {counts.covered_by_factory} | "
        f"Reviewed unexpanded: {counts.reviewed_unexpanded} | "
        f"Editorial review required: {counts.editorial_review_required} | "
        f"Factory sources missing current snapshot: {counts.factory_sources_missing_from_current_snapshot}"
    )


@instagram_app.command("historical-backlog")
def historical_backlog(
    registry_path: Annotated[Path, typer.Argument(help="Exact Instagram Reel factory registry JSON")],
    mapping: Annotated[
        Path | None,
        typer.Option("--mapping", help="Exact historical YouTube→provider identity mapping JSON"),
    ] = None,
    reviewed_dir: Annotated[
        Path | None,
        typer.Option("--reviewed-dir", help="Directory of reviewed YouTube editorial records"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Build a historical identity backlog without claiming current provider state."""

    try:
        registry, registry_sha256 = _read_reel_registry(registry_path)
        mapping_payload, mapping_sha256, reviewed_ids, reviewed_sha256 = _resolve_supporting_sources(
            project_key=registry.project_key,
            mapping_path=mapping,
            reviewed_dir=reviewed_dir,
        )
        if mapping_sha256 is None or reviewed_sha256 is None:
            raise ValueError("historical backlog requires exact mapping and reviewed-corpus evidence")
        channels = PROJECT_CHANNEL_IDS.get(registry.project_key, frozenset())
        if len(channels) != 1:
            raise ValueError(
                f"historical backlog requires exactly one canonical YouTube channel for {registry.project_key}"
            )
        channel_id = next(iter(channels))
        result = build_instagram_historical_backlog(
            registry,
            historical_mapping=mapping_payload,
            reviewed_video_ids=reviewed_ids,
            youtube_channel_id=channel_id,
            source_mapping_sha256=mapping_sha256,
            source_reviewed_corpus_sha256=reviewed_sha256,
            source_registry_sha256=registry_sha256,
        )
    except (InstagramHistoricalBacklogError, OSError, ValueError) as exc:
        console.print(f"[red]Instagram historical backlog failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        settings = get_settings()
        output = settings.data_dir / "reports" / f"instagram-{registry.project_key}-historical-backlog.json"
    _write_json(output, result.model_dump(mode="json"))

    counts = result.counts
    console.print(
        f"[green]Built provider-inert Instagram historical backlog → {output}[/green]\n"
        f"Historical floor: {counts.total_historical_floor_ids} | Covered: {counts.already_covered} | "
        f"Design Reel jobs: {counts.design_reel_jobs} | "
        f"Build editorial record: {counts.build_editorial_record} | "
        f"Reviewed outside floor: {counts.reviewed_ids_outside_historical_floor} | "
        f"Factory sources outside floor: {counts.factory_youtube_sources_outside_historical_floor}"
    )
