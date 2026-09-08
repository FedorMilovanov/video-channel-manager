from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from video_channel_manager.config import get_settings
from video_channel_manager.instagram.production import (
    InstagramConfigurationError,
    InstagramProductionError,
    InstagramProductionService,
    InstagramPublicationLedger,
    InstagramPublishManifest,
    InstagramRuntimeConfig,
    PublicationSnapshot,
)
from video_channel_manager.persistence import Database


console = Console()
instagram_production_app = typer.Typer(
    no_args_is_help=True,
    help="Production-capable Instagram publishing with explicit write gates and durable reconciliation.",
)


def _read_manifest(path: Path) -> InstagramPublishManifest:
    try:
        return InstagramPublishManifest.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise InstagramProductionError(f"Invalid Instagram publish manifest {path}: {exc}") from exc


def _open_service() -> tuple[InstagramProductionService, Database]:
    settings = get_settings()
    config = InstagramRuntimeConfig.from_settings(settings)
    database = Database(settings.database_url)
    ledger = InstagramPublicationLedger(database)
    return InstagramProductionService(config, ledger), database


def _render_snapshot(snapshot: PublicationSnapshot) -> None:
    table = Table(title=f"Instagram publication {snapshot.publication_key}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Account", snapshot.account_id)
    table.add_row("Status", snapshot.status.value)
    table.add_row("Content hash", snapshot.content_hash)
    table.add_row("Container", snapshot.provider_container_id or "-")
    table.add_row("Media", snapshot.provider_media_id or "-")
    table.add_row("Provider status", snapshot.provider_status or "-")
    table.add_row("Attempts", str(snapshot.attempt_count))
    table.add_row("Last error", snapshot.last_error_message or "-")
    console.print(table)


@instagram_production_app.command("preflight")
def preflight() -> None:
    """Read-only verification of exact provider identity and publishing quota access."""

    service: InstagramProductionService | None = None
    database: Database | None = None
    try:
        service, database = _open_service()
        result = service.preflight()
    except InstagramProductionError as exc:
        console.print(f"[red]Instagram preflight failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    finally:
        if service is not None:
            service.close()
        if database is not None:
            database.close()
    console.print("[green]Instagram provider preflight passed.[/green]")
    console.print_json(json.dumps(result, ensure_ascii=False, default=str))


@instagram_production_app.command("plan")
def plan(
    manifest_path: Annotated[Path, typer.Argument(help="Exact Instagram publish manifest JSON")],
) -> None:
    """Persist/inspect one publication plan without making any provider request."""

    service: InstagramProductionService | None = None
    database: Database | None = None
    try:
        manifest = _read_manifest(manifest_path)
        service, database = _open_service()
        snapshot = service.plan(manifest)
    except InstagramProductionError as exc:
        console.print(f"[red]Instagram publish plan failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    finally:
        if service is not None:
            service.close()
        if database is not None:
            database.close()
    _render_snapshot(snapshot)
    console.print("[yellow]Provider writes: none.[/yellow]")


@instagram_production_app.command("status")
def status(
    publication_key: Annotated[str, typer.Argument(help="Stable publication key")],
) -> None:
    """Show durable local publication state without contacting Meta."""

    database: Database | None = None
    try:
        settings = get_settings()
        database = Database(settings.database_url)
        snapshot = InstagramPublicationLedger(database).get(publication_key)
        if snapshot is None:
            raise InstagramProductionError(f"Unknown publication key: {publication_key}")
    except InstagramProductionError as exc:
        console.print(f"[red]Instagram status failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    finally:
        if database is not None:
            database.close()
    _render_snapshot(snapshot)


@instagram_production_app.command("publish")
def publish(
    manifest_path: Annotated[Path, typer.Argument(help="Exact Instagram publish manifest JSON")],
    execute: Annotated[
        bool,
        typer.Option("--execute", help="Authorize this invocation to make provider writes; kill switch must also be on"),
    ] = False,
) -> None:
    """Create, process and publish one Reel through the durable write ledger."""

    service: InstagramProductionService | None = None
    database: Database | None = None
    try:
        manifest = _read_manifest(manifest_path)
        service, database = _open_service()
        snapshot = service.publish(manifest, execute=execute)
    except (InstagramProductionError, InstagramConfigurationError) as exc:
        console.print(f"[red]Instagram publish refused/failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    finally:
        if service is not None:
            service.close()
        if database is not None:
            database.close()
    _render_snapshot(snapshot)


@instagram_production_app.command("reconcile")
def reconcile(
    publication_key: Annotated[str, typer.Argument(help="Stable publication key")],
    published_media_id: Annotated[
        str | None,
        typer.Option(
            "--published-media-id",
            help="Exact provider media ID from independently verified provider evidence; never guessed",
        ),
    ] = None,
) -> None:
    """Resolve an in-flight or ambiguous publication without blind republishing."""

    service: InstagramProductionService | None = None
    database: Database | None = None
    try:
        service, database = _open_service()
        snapshot = service.reconcile(publication_key, published_media_id=published_media_id)
    except InstagramProductionError as exc:
        console.print(f"[red]Instagram reconciliation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    finally:
        if service is not None:
            service.close()
        if database is not None:
            database.close()
    _render_snapshot(snapshot)
