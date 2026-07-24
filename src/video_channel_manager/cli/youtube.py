from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.youtube import (
    AccountNotFoundError,
    ChannelIdentity,
    InstalledClientConfig,
    InstalledOAuthFlow,
    OAuthFlowError,
    TokenStore,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    YouTubeAccount,
    YouTubeApiClient,
    YouTubeApiError,
    YouTubeDescriptionWriter,
    YouTubeInventoryService,
    YouTubeRevisionConflictError,
    YouTubeWriteError,
)

console = Console()
youtube_app = typer.Typer(no_args_is_help=True, help="YouTube OAuth, inventory, and guarded description fixes.")


def _components(account: str, client_secret: Path | None = None) -> tuple[TokenStore, InstalledClientConfig, YouTubeApiClient]:
    settings = get_settings()
    secret_path = client_secret or settings.youtube_client_secret_file
    config = InstalledClientConfig.from_file(secret_path)
    store = TokenStore(settings.data_dir)
    client = YouTubeApiClient(client_config=config, token_store=store, account_alias=account)
    return store, config, client


def _writer_components(
    account: str,
    client_secret: Path | None = None,
) -> tuple[TokenStore, InstalledClientConfig, YouTubeDescriptionWriter]:
    settings = get_settings()
    secret_path = client_secret or settings.youtube_client_secret_file
    config = InstalledClientConfig.from_file(secret_path)
    store = TokenStore(settings.data_dir)
    writer = YouTubeDescriptionWriter(client_config=config, token_store=store, account_alias=account)
    return store, config, writer


def _load_copy_fix_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read copy-fix plan: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_name") != "video-manager.youtube-copy-fix-plan":
        raise ValueError("Expected a video-manager.youtube-copy-fix-plan JSON object.")
    operations = payload.get("operations")
    if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
        raise ValueError("Copy-fix plan operations must be a list of objects.")
    return payload


def _required_text(operation: dict[str, Any], field: str) -> str:
    value = operation.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Copy-fix operation is missing required string field: {field}")
    return value


@youtube_app.command("login")
def login(
    account: Annotated[str, typer.Option("--account", "-a", help="Local alias, e.g. legendary-poet")] = "default",
    client_secret: Annotated[
        Path | None,
        typer.Option("--client-secret", help="Downloaded Google Desktop OAuth JSON file"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing token for this alias")] = False,
    write: Annotated[
        bool,
        typer.Option("--write", help="Request guarded YouTube description write access"),
    ] = False,
) -> None:
    """Authorize one Google/YouTube account; read-only unless --write is explicit."""

    settings = get_settings()
    secret_path = client_secret or settings.youtube_client_secret_file
    try:
        config = InstalledClientConfig.from_file(secret_path)
        store = TokenStore(settings.data_dir)
        account = store.validate_alias(account)
    except (ValueError, OSError) as exc:
        console.print(f"[red]YouTube configuration error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if store.token_exists(account) and not force:
        console.print(
            f"[yellow]Account '{account}' is already authorized.[/yellow] "
            "Use --force only when you intentionally want to replace its token."
        )
        raise typer.Exit(code=2)

    scopes = (YOUTUBE_READONLY_SCOPE, YOUTUBE_FORCE_SSL_SCOPE) if write else (YOUTUBE_READONLY_SCOPE,)
    flow = InstalledOAuthFlow(config, scopes=scopes)
    console.print("[bold]Opening Google authorization in your browser…[/bold]")
    if write:
        console.print(
            "[yellow]Write access requested.[/yellow] The application still writes only through explicit "
            "revision-guarded commands with backups and --execute."
        )
    else:
        console.print("Only the read-only YouTube scope is requested. No channel changes can be made.")
    try:
        token = flow.authorize(
            timeout_seconds=settings.youtube_oauth_timeout_seconds,
            force_consent=True,
            on_authorization_url=lambda url: console.print(
                "If the browser does not open, copy this URL:\n" f"[link={url}]{url}[/link]"
            ),
        )
        store.save_token(account, token)
        client = YouTubeApiClient(client_config=config, token_store=store, account_alias=account)
        channels = client.list_my_channels()
        account_record = YouTubeAccount(
            alias=account,
            token_file=str(store.token_path(account)),
            channels=[
                ChannelIdentity(channel_id=item.ref.remote_id, title=item.title, url=item.url or "") for item in channels
            ],
        )
        store.save_account(account_record)
    except (OAuthFlowError, YouTubeApiError, ValueError) as exc:
        console.print(f"[red]YouTube authorization failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    access = "guarded write" if YOUTUBE_FORCE_SSL_SCOPE in token.scopes else "read-only"
    console.print(f"[green]Authorized YouTube account alias '{account}' ({access}).[/green]")
    if not channels:
        console.print("[yellow]No YouTube channel was returned for the selected Google identity.[/yellow]")
        return
    table = Table(title="Authorized YouTube channels")
    table.add_column("Title")
    table.add_column("Channel ID")
    table.add_column("URL")
    for channel in channels:
        table.add_row(channel.title, channel.ref.remote_id, channel.url or "")
    console.print(table)


@youtube_app.command("accounts")
def accounts() -> None:
    """List locally registered OAuth accounts without calling Google."""

    settings = get_settings()
    store = TokenStore(settings.data_dir)
    try:
        registered = store.list_accounts()
    except (OSError, ValueError) as exc:
        console.print(f"[red]Cannot read account registry:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if not registered:
        console.print("No YouTube accounts are registered. Run: video-manager youtube login")
        return
    table = Table(title="YouTube OAuth accounts")
    table.add_column("Alias")
    table.add_column("Token")
    table.add_column("Access")
    table.add_column("Channels")
    table.add_column("Updated")
    for item in registered:
        channel_titles = ", ".join(channel.title for channel in item.channels) or "none"
        access = "missing"
        if store.token_exists(item.alias):
            try:
                token = store.load_token(item.alias)
                access = "write" if YOUTUBE_FORCE_SSL_SCOPE in token.scopes else "read-only"
            except (OSError, ValueError):
                access = "invalid"
        table.add_row(
            item.alias,
            "present" if store.token_exists(item.alias) else "missing",
            access,
            channel_titles,
            item.updated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        )
    console.print(table)


@youtube_app.command("channels")
def channels(
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Fetch channels currently available to one authorized account."""

    try:
        store, _, client = _components(account, client_secret)
        records = client.list_my_channels()
        store.save_account(
            YouTubeAccount(
                alias=account,
                token_file=str(store.token_path(account)),
                channels=[
                    ChannelIdentity(channel_id=item.ref.remote_id, title=item.title, url=item.url or "")
                    for item in records
                ],
            )
        )
    except (AccountNotFoundError, OSError, ValueError, YouTubeApiError) as exc:
        console.print(f"[red]Cannot read YouTube channels:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    table = Table(title=f"YouTube channels for '{account}'")
    table.add_column("Title")
    table.add_column("Channel ID")
    table.add_column("URL")
    for item in records:
        table.add_row(item.title, item.ref.remote_id, item.url or "")
    console.print(table)
    if not records:
        console.print("[yellow]No channels returned. Verify which Google or Brand Account was selected.[/yellow]")


@youtube_app.command("scan")
def scan(
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    channel_id: Annotated[str | None, typer.Option("--channel", help="Exact YouTube channel ID")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Export a complete read-only AuditPackage for videos, playlists, and memberships."""

    settings = get_settings()
    try:
        _, _, client = _components(account, client_secret)
        available_channels = client.list_my_channels()
        if channel_id is None:
            if len(available_channels) != 1:
                choices = ", ".join(item.ref.remote_id for item in available_channels) or "none"
                raise ValueError(f"Specify --channel because this account has {len(available_channels)} choices: {choices}")
            channel_id = available_channels[0].ref.remote_id
        with console.status("Reading YouTube channel inventory…"):
            package = YouTubeInventoryService(client).build_audit_package(channel_id)
    except (AccountNotFoundError, OSError, ValueError, YouTubeApiError) as exc:
        console.print(f"[red]YouTube scan failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        output = settings.data_dir / "exports" / f"youtube-{account}-{channel_id}-{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(package.model_dump_json(indent=2), encoding="utf-8")
    console.print(
        f"[green]Exported AuditPackage → {output}[/green]\n"
        f"Videos: {len(package.videos)} | Playlists: {len(package.collections)} | "
        f"Memberships: {len(package.memberships)}"
    )


@youtube_app.command("apply-copy-fixes")
def apply_copy_fixes(
    plan: Annotated[Path, typer.Argument(help="JSON plan created by scripts/autofix_youtube_copy.py")],
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    confirm_channel: Annotated[
        str,
        typer.Option("--confirm-channel", help="Exact channel ID that every operation must target"),
    ] = "",
    execute: Annotated[
        bool,
        typer.Option("--execute", help="Apply changes after a successful full preflight"),
    ] = False,
    max_operations: Annotated[
        int,
        typer.Option("--max-operations", min=1, max=500, help="Safety cap for one run"),
    ] = 100,
    backup_output: Annotated[Path | None, typer.Option("--backup-output")] = None,
    result_output: Annotated[Path | None, typer.Option("--result-output")] = None,
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Preflight or apply revision-guarded description-only fixes with rollback."""

    settings = get_settings()
    try:
        payload = _load_copy_fix_plan(plan)
        raw_operations = payload["operations"]
        operations = [item for item in raw_operations if isinstance(item, dict)]
        if not operations:
            raise ValueError("Copy-fix plan has no operations.")
        if len(operations) > max_operations:
            raise ValueError(f"Plan has {len(operations)} operations, above --max-operations {max_operations}.")
        if not confirm_channel:
            raise ValueError("--confirm-channel with the exact YouTube channel ID is required.")
        store, _, writer = _writer_components(account, client_secret)
    except (AccountNotFoundError, OSError, ValueError) as exc:
        console.print(f"[red]Cannot load copy-fix plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    prepared: list[dict[str, Any]] = []
    already_applied = 0
    try:
        with console.status(f"Preflighting {len(operations)} descriptions against live YouTube…"):
            for operation in operations:
                video_id = _required_text(operation, "video_id")
                channel_id = _required_text(operation, "channel_id")
                expected_revision = _required_text(operation, "expected_revision")
                before = _required_text(operation, "before_description")
                after = _required_text(operation, "after_description")
                if channel_id != confirm_channel:
                    raise ValueError(
                        f"Plan operation {video_id} targets {channel_id}, not confirmed channel {confirm_channel}."
                    )
                current = writer.read_description(video_id)
                if current.channel_id != confirm_channel:
                    raise YouTubeRevisionConflictError(
                        f"Live video {video_id} belongs to {current.channel_id}, not {confirm_channel}."
                    )
                if current.description == after:
                    already_applied += 1
                    continue
                if current.revision != expected_revision or current.description != before:
                    raise YouTubeRevisionConflictError(
                        f"Live video {video_id} changed after the audit; regenerate scan and plan."
                    )
                prepared.append(
                    {
                        "video_id": video_id,
                        "channel_id": channel_id,
                        "title": current.title,
                        "expected_revision": expected_revision,
                        "before_description": before,
                        "after_description": after,
                    }
                )
    except (ValueError, YouTubeWriteError) as exc:
        console.print(f"[red]Preflight failed; nothing was changed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(
        f"[green]Preflight passed.[/green] Ready: {len(prepared)} | Already applied: {already_applied} | "
        f"Channel: {confirm_channel}"
    )
    if not execute:
        console.print("Dry-run only. Re-run with --execute after authorizing --write access.")
        return

    try:
        token = store.load_token(account)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Cannot read OAuth token:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if YOUTUBE_FORCE_SSL_SCOPE not in token.scopes:
        console.print(
            "[red]Stored OAuth token is read-only.[/red] Run:\n"
            f"video-manager youtube login --account {account} --write --force"
        )
        raise typer.Exit(code=2)

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if backup_output is None:
        backup_output = settings.data_dir / "reports" / f"youtube-copy-backup-{timestamp}.json"
    if result_output is None:
        result_output = settings.data_dir / "reports" / f"youtube-copy-apply-{timestamp}.json"
    backup_payload = {
        "schema_name": "video-manager.youtube-copy-backup",
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "source_plan": str(plan),
        "account": account,
        "channel_id": confirm_channel,
        "operations": prepared,
    }
    backup_output.parent.mkdir(parents=True, exist_ok=True)
    backup_output.write_text(json.dumps(backup_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print(f"Backup written before mutation → {backup_output}")

    applied: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema_name": "video-manager.youtube-copy-apply-result",
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "source_plan": str(plan),
        "backup": str(backup_output),
        "account": account,
        "channel_id": confirm_channel,
        "status": "running",
        "applied": applied,
        "rollback": [],
    }

    failure: str | None = None
    try:
        for operation in prepared:
            verified = writer.replace_description(
                video_id=str(operation["video_id"]),
                expected_channel_id=str(operation["channel_id"]),
                expected_revision=str(operation["expected_revision"]),
                expected_description=str(operation["before_description"]),
                new_description=str(operation["after_description"]),
            )
            applied.append(
                {
                    **operation,
                    "after_revision": verified.revision,
                    "verified": True,
                }
            )
            console.print(f"[green]Updated and verified[/green] {verified.video_id} — {verified.title}")
    except YouTubeWriteError as exc:
        failure = str(exc)
        console.print(f"[red]Apply failed; starting rollback:[/red] {exc}")

    if failure is not None:
        rollback_results: list[dict[str, Any]] = result["rollback"]
        for operation in reversed(applied):
            video_id = str(operation["video_id"])
            try:
                restored = writer.replace_description(
                    video_id=video_id,
                    expected_channel_id=str(operation["channel_id"]),
                    expected_revision=str(operation["after_revision"]),
                    expected_description=str(operation["after_description"]),
                    new_description=str(operation["before_description"]),
                )
                rollback_results.append(
                    {"video_id": video_id, "status": "restored", "revision": restored.revision}
                )
                console.print(f"[yellow]Rolled back[/yellow] {video_id}")
            except YouTubeWriteError as rollback_exc:
                rollback_results.append(
                    {"video_id": video_id, "status": "failed", "error": str(rollback_exc)}
                )
                console.print(f"[red]Rollback failed[/red] {video_id}: {rollback_exc}")
        result["status"] = "failed_rolled_back"
        result["error"] = failure
    else:
        result["status"] = "completed"

    result["finished_at"] = datetime.now(UTC).isoformat()
    result_output.parent.mkdir(parents=True, exist_ok=True)
    result_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print(f"Result log → {result_output}")

    if failure is not None:
        raise typer.Exit(code=2)
    console.print(f"[bold green]Completed {len(applied)} verified description updates.[/bold green]")
