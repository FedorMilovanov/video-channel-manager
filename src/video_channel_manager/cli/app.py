from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from video_channel_manager import __version__
from video_channel_manager.application.plan_guard import PlanGuard
from video_channel_manager.application.plan_preview import build_plan_preview
from video_channel_manager.cli.album import album_app
from video_channel_manager.cli.compare import compare_app
from video_channel_manager.cli.content import content_app
from video_channel_manager.cli.instagram import instagram_app
from video_channel_manager.cli.instagram_launch import launch_preview_command
from video_channel_manager.cli.resi import resi_app
from video_channel_manager.cli.vk import vk_app
from video_channel_manager.cli.youtube import youtube_app
from video_channel_manager.config import get_settings
from video_channel_manager.domain.enums import ChannelKind, CollectionKind, OperationType, PlatformName, RiskLevel
from video_channel_manager.domain.models import ChannelRecord, CollectionRecord, RemoteRef, VideoRecord
from video_channel_manager.exchange.audit_package import AuditFinding, AuditPackage
from video_channel_manager.exchange.change_plan import ChangeOperation, ChangePlan
from video_channel_manager.exchange.instagram_content import (
    InstagramAnalyticsSnapshot,
    InstagramLaunchPack,
    InstagramLaunchPreviewArtifact,
)
from video_channel_manager.exchange.instagram_factory_coverage import InstagramFactoryCoverageArtifact
from video_channel_manager.exchange.instagram_historical_backlog import InstagramHistoricalBacklogArtifact
from video_channel_manager.exchange.instagram_identity import (
    InstagramAccountObservation,
    InstagramProjectBinding,
    InstagramProjectBindingRegistry,
)
from video_channel_manager.exchange.instagram_reels import InstagramReelFactoryRegistry, InstagramReelQueueArtifact
from video_channel_manager.exchange.instagram_video import (
    InstagramMediaReview,
    InstagramVideoIntakeArtifact,
    InstagramVideoRouteArtifact,
)
from video_channel_manager.local_media import scan_local_media
from video_channel_manager.persistence import Database
from video_channel_manager.wave_engine.cli import schema_documents as wave_schema_documents
from video_channel_manager.wave_engine.cli import wave_app

app = typer.Typer(no_args_is_help=True, help="Audit, organize, and safely synchronize video channels.")
db_app = typer.Typer(no_args_is_help=True, help="Database lifecycle commands.")
schema_app = typer.Typer(no_args_is_help=True, help="Versioned exchange schema commands.")
plan_app = typer.Typer(no_args_is_help=True, help="Validate and preview external change plans.")
local_app = typer.Typer(no_args_is_help=True, help="Read-only local media inventory.")
example_app = typer.Typer(no_args_is_help=True, help="Generate example exchange documents.")
app.add_typer(db_app, name="db")
app.add_typer(schema_app, name="schema")
app.add_typer(plan_app, name="plan")
app.add_typer(local_app, name="local")
app.add_typer(example_app, name="example")
app.add_typer(album_app, name="album")
app.add_typer(compare_app, name="compare")
app.add_typer(content_app, name="content")
instagram_app.command("launch-preview")(launch_preview_command)
app.add_typer(instagram_app, name="instagram")
app.add_typer(resi_app, name="resi")
app.add_typer(youtube_app, name="youtube")
app.add_typer(vk_app, name="vk")
app.add_typer(wave_app, name="wave")
console = Console()


@app.command()
def version() -> None:
    """Print the installed application version."""

    console.print(__version__)


@app.command()
def doctor() -> None:
    """Check runtime, tools, data directory, and safety configuration."""

    settings = get_settings()
    settings.ensure_runtime_directories()
    vk_registry = settings.data_dir / "vk" / "accounts.json"
    table = Table(title="Video Channel Manager doctor")
    table.add_column("Check")
    table.add_column("Result")
    checks = {
        "Python": platform.python_version(),
        "Operating system": platform.platform(),
        "ffmpeg": shutil.which("ffmpeg") or "not found (optional for foundation)",
        "ffprobe": shutil.which("ffprobe") or "not found (needed for media metadata)",
        "yt-dlp": shutil.which("yt-dlp") or "not found (needed for YouTube cache downloads)",
        "Data directory": str(settings.data_dir.resolve()),
        "Database URL": settings.database_url,
        "YouTube OAuth client": (
            str(settings.youtube_client_secret_file.resolve())
            if settings.youtube_client_secret_file.is_file()
            else "not found"
        ),
        "VK API version": settings.vk_api_version,
        "VK local accounts": "present" if vk_registry.is_file() else "none",
        "Safe mode": str(settings.safe_mode),
        "Destructive operations": "enabled" if settings.allow_destructive_operations else "disabled",
    }
    for name, value in checks.items():
        table.add_row(name, value)
    console.print(table)


@db_app.command("init")
def db_init() -> None:
    """Create development tables. Use Alembic migrations for deployed environments."""

    settings = get_settings()
    settings.ensure_runtime_directories()
    Database(settings.database_url).create_schema()
    console.print("[green]Database schema initialized.[/green]")


@schema_app.command("export")
def schema_export(
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("schemas/generated"),
) -> None:
    """Export versioned exchange JSON Schemas."""

    output_dir.mkdir(parents=True, exist_ok=True)
    documents = {
        "audit-package-v1.schema.json": AuditPackage.model_json_schema(),
        "change-plan-v1.schema.json": ChangePlan.model_json_schema(),
        "instagram-youtube-video-intake-v1.schema.json": InstagramVideoIntakeArtifact.model_json_schema(),
        "instagram-media-review-v1.schema.json": InstagramMediaReview.model_json_schema(),
        "instagram-video-route-v1.schema.json": InstagramVideoRouteArtifact.model_json_schema(),
        "instagram-reel-factory-v1.schema.json": InstagramReelFactoryRegistry.model_json_schema(),
        "instagram-reel-queue-v1.schema.json": InstagramReelQueueArtifact.model_json_schema(),
        "instagram-reel-factory-coverage-v1.schema.json": InstagramFactoryCoverageArtifact.model_json_schema(),
        "instagram-historical-factory-backlog-v1.schema.json": InstagramHistoricalBacklogArtifact.model_json_schema(),
        "instagram-account-observation-v1.schema.json": InstagramAccountObservation.model_json_schema(),
        "instagram-project-binding-v1.schema.json": InstagramProjectBinding.model_json_schema(),
        "instagram-project-binding-registry-v1.schema.json": InstagramProjectBindingRegistry.model_json_schema(),
        "instagram-launch-pack-v1.schema.json": InstagramLaunchPack.model_json_schema(),
        "instagram-launch-preview-v1.schema.json": InstagramLaunchPreviewArtifact.model_json_schema(),
        "instagram-analytics-snapshot-v1.schema.json": InstagramAnalyticsSnapshot.model_json_schema(),
        **wave_schema_documents(),
    }
    for filename, schema in documents.items():
        (output_dir / filename).write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]Exported {len(documents)} schemas to {output_dir}[/green]")


def _read_plan(path: Path) -> ChangePlan:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return ChangePlan.model_validate(payload)


@plan_app.command("validate")
def plan_validate(path: Path) -> None:
    """Validate a ChangePlan schema and local safety policy."""

    try:
        plan = _read_plan(path)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        console.print(f"[red]Invalid plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    result = PlanGuard(get_settings()).validate(plan)
    for warning in result.warnings:
        console.print(f"[yellow]WARNING {warning.code}:[/yellow] {warning.message}")
    for error in result.errors:
        console.print(f"[red]ERROR {error.code}:[/red] {error.message}")
    if not result.is_valid:
        raise typer.Exit(code=2)
    console.print("[green]Plan is valid under the current policy.[/green]")


@plan_app.command("preview")
def plan_preview(path: Path) -> None:
    """Print a mutation-free plan summary."""

    try:
        plan = _read_plan(path)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        console.print(f"[red]Invalid plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    preview = build_plan_preview(plan)
    table = Table(title=plan.title)
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Plan ID", str(plan.plan_id))
    table.add_row("Snapshot ID", str(plan.source_snapshot_id))
    table.add_row("Channel", plan.channel.stable_key)
    table.add_row("Total operations", str(preview.total_operations))
    table.add_row("Enabled", str(preview.enabled_operations))
    table.add_row("Disabled", str(preview.disabled_operations))
    console.print(table)
    for operation, count in sorted(preview.operations_by_type.items()):
        console.print(f"  {operation}: {count}")


@local_app.command("scan")
def local_scan(
    roots: Annotated[list[Path], typer.Argument(help="One or more files/directories to scan")],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("local-inventory.json"),
    include_hash: Annotated[bool, typer.Option("--hash/--no-hash")] = False,
) -> None:
    """Create a read-only inventory of local video files."""

    try:
        records = scan_local_media(roots, include_hash=include_hash)
    except FileNotFoundError as exc:
        console.print(f"[red]Path not found:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([item.model_dump(mode="json") for item in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    console.print(f"[green]Indexed {len(records)} video files → {output}[/green]")


@example_app.command("export")
def example_export(
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("examples/generated"),
) -> None:
    """Generate linked example AuditPackage and ChangePlan documents."""

    channel_ref = RemoteRef(platform=PlatformName.YOUTUBE, channel_id="UC_EXAMPLE", remote_id="UC_EXAMPLE")
    video_ref = RemoteRef(platform=PlatformName.YOUTUBE, channel_id="UC_EXAMPLE", remote_id="video_001")
    playlist_ref = RemoteRef(platform=PlatformName.YOUTUBE, channel_id="UC_EXAMPLE", remote_id="playlist_esenin")
    audit = AuditPackage(
        channel=ChannelRecord(ref=channel_ref, title="Example Channel", kind=ChannelKind.VIDEO_CHANNEL),
        videos=[VideoRecord(ref=video_ref, title="Example video", revision="sha256:video-revision")],
        collections=[
            CollectionRecord(
                ref=playlist_ref,
                title="Сергей Есенин",
                kind=CollectionKind.PLAYLIST,
                revision="sha256:playlist-revision",
            )
        ],
        findings=[
            AuditFinding(
                rule_id="playlist.author.required",
                severity="warning",
                subject_key=video_ref.stable_key,
                summary="Video is missing its author playlist.",
            )
        ],
    )
    plan = ChangePlan(
        source_snapshot_id=audit.snapshot_id,
        title="Add example video to author playlist",
        channel=channel_ref,
        operations=[
            ChangeOperation(
                operation=OperationType.ADD_TO_COLLECTION,
                target=video_ref,
                payload={"collection_id": playlist_ref.remote_id},
                expected_revision="sha256:video-revision",
                risk=RiskLevel.LOW,
                rationale="Audit rule playlist.author.required",
            )
        ],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit-package.json").write_text(audit.model_dump_json(indent=2), encoding="utf-8")
    (output_dir / "change-plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"[green]Generated examples in {output_dir}[/green]")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
