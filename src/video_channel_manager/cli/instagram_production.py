from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from video_channel_manager.config import get_settings
from video_channel_manager.instagram.local_resumable import (
    InstagramLocalResumableService,
    InstagramResumableUploadLedger,
    build_local_publish_manifest,
)
from video_channel_manager.instagram.production import (
    InstagramConfigurationError,
    InstagramIdentityMismatchError,
    InstagramProductionError,
    InstagramProductionService,
    InstagramProviderError,
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

_META_REEL_MAX_BYTES = 1_000_000_000
_META_OAUTH_INVALID_TOKEN_CODE = "190"


def _read_manifest(path: Path) -> InstagramPublishManifest:
    try:
        return InstagramPublishManifest.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise InstagramProductionError(f"Invalid Instagram publish manifest {path}: {exc}") from exc


def _enforce_local_reel_size(path: Path) -> None:
    try:
        size_bytes = path.expanduser().stat().st_size
    except OSError:
        return
    if size_bytes > _META_REEL_MAX_BYTES:
        raise InstagramProductionError(
            f"Instagram local video is {size_bytes} bytes; Meta Reels accepts at most {_META_REEL_MAX_BYTES} bytes"
        )


def _preflight_failure_message(exc: InstagramProductionError, *, login_mode: str | None) -> str:
    """Return a secret-safe operator diagnosis for read-only preflight failures."""

    if isinstance(exc, InstagramProviderError) and exc.error_code == _META_OAUTH_INVALID_TOKEN_CODE:
        if login_mode == "facebook":
            return (
                "Meta rejected the configured Facebook Login credential (OAuth error code 190: access token is "
                "invalid or expired). Keep VCM_INSTAGRAM_WRITES_ENABLED=false, renew the Facebook User credential "
                "outside Git, derive a fresh Page Access Token for the exact registered Facebook Page, and rerun "
                "the read-only Instagram preflight. No provider write was attempted."
            )
        return (
            "Meta rejected the configured Instagram credential (OAuth error code 190: access token is invalid or "
            "expired). Keep VCM_INSTAGRAM_WRITES_ENABLED=false, renew the credential outside Git, and rerun the "
            "read-only Instagram preflight. No provider write was attempted."
        )
    return str(exc)


def _open_service() -> tuple[InstagramProductionService, Database]:
    settings = get_settings()
    config = InstagramRuntimeConfig.from_settings(settings)
    database = Database(settings.database_url)
    ledger = InstagramPublicationLedger(database)
    return InstagramProductionService(config, ledger), database


def _open_local_service() -> tuple[InstagramLocalResumableService, Database]:
    settings = get_settings()
    config = InstagramRuntimeConfig.from_settings(settings)
    database = Database(settings.database_url)
    ledger = InstagramPublicationLedger(database)
    upload_ledger = InstagramResumableUploadLedger(database)
    return InstagramLocalResumableService(config, ledger, upload_ledger), database


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
    table.add_row("Container requested", str(snapshot.container_requested_at or "-"))
    table.add_row("Publish requested", str(snapshot.publish_requested_at or "-"))
    table.add_row("Published", str(snapshot.published_at or "-"))
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
        login_mode = service.config.login_mode if service is not None else None
        message = _preflight_failure_message(exc, login_mode=login_mode)
        console.print(f"[red]Instagram preflight failed:[/red] {message}")
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
    """Persist/inspect one publication plan without provider credentials or requests."""

    database: Database | None = None
    try:
        manifest = _read_manifest(manifest_path)
        settings = get_settings()
        if settings.instagram_account_id is not None and manifest.account_id != settings.instagram_account_id:
            raise InstagramIdentityMismatchError(
                f"Manifest account {manifest.account_id!r} does not match configured account "
                f"{settings.instagram_account_id!r}"
            )
        database = Database(settings.database_url)
        snapshot = InstagramPublicationLedger(database).ensure_planned(manifest)
    except InstagramProductionError as exc:
        console.print(f"[red]Instagram publish plan failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    finally:
        if database is not None:
            database.close()
    _render_snapshot(snapshot)
    console.print("[yellow]Provider writes: none; provider credentials: not required.[/yellow]")


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
        typer.Option(
            "--execute",
            help="Authorize this invocation to make provider writes; kill switch must also be on",
        ),
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


@instagram_production_app.command("publish-local")
def publish_local(
    video_path: Annotated[Path, typer.Argument(help="Reviewed local MP4 to upload directly to Instagram")],
    publication_key: Annotated[
        str,
        typer.Option("--publication-key", help="Stable idempotency/publication key for this exact Reel"),
    ],
    caption: Annotated[str, typer.Option("--caption", help="Exact Instagram Reel caption")] = "",
    share_to_feed: Annotated[
        bool,
        typer.Option("--share-to-feed/--no-share-to-feed", help="Ask Instagram to share the Reel to the feed"),
    ] = True,
    thumb_offset_ms: Annotated[
        int | None,
        typer.Option("--thumb-offset-ms", min=0, help="Optional thumbnail offset in milliseconds"),
    ] = None,
    execute: Annotated[
        bool,
        typer.Option(
            "--execute",
            help="Authorize this invocation to make provider writes; kill switch must also be on",
        ),
    ] = False,
) -> None:
    """Upload one local MP4 with Meta resumable upload, then process and publish it as a Reel."""

    service: InstagramLocalResumableService | None = None
    database: Database | None = None
    try:
        _enforce_local_reel_size(video_path)
        service, database = _open_local_service()
        manifest = build_local_publish_manifest(
            video_path,
            publication_key=publication_key,
            account_id=service.config.account_id,
            caption=caption,
            share_to_feed=share_to_feed,
            thumb_offset_ms=thumb_offset_ms,
        )
        snapshot = service.publish_local(manifest, video_path, execute=execute)
    except (InstagramProductionError, InstagramConfigurationError) as exc:
        console.print(f"[red]Instagram local publish refused/failed:[/red] {exc}")
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
    observed_container_id: Annotated[
        str | None,
        typer.Option(
            "--observed-container-id",
            "--container-id",
            help="Exact provider container ID from independently verified evidence after ambiguous creation",
        ),
    ] = None,
) -> None:
    """Resolve an in-flight or ambiguous publication without blind republishing."""

    service: InstagramProductionService | None = None
    database: Database | None = None
    try:
        service, database = _open_service()
        snapshot = service.reconcile(
            publication_key,
            published_media_id=published_media_id,
            observed_container_id=observed_container_id,
        )
    except InstagramProductionError as exc:
        console.print(f"[red]Instagram reconciliation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    finally:
        if service is not None:
            service.close()
        if database is not None:
            database.close()
    _render_snapshot(snapshot)
