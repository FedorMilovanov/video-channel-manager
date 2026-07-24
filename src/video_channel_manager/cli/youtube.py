from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

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
    YouTubeAccount,
    YouTubeApiClient,
    YouTubeApiError,
    YouTubeInventoryService,
)

console = Console()
youtube_app = typer.Typer(no_args_is_help=True, help="Read-only YouTube OAuth and channel inventory.")


def _components(account: str, client_secret: Path | None = None) -> tuple[TokenStore, InstalledClientConfig, YouTubeApiClient]:
    settings = get_settings()
    secret_path = client_secret or settings.youtube_client_secret_file
    config = InstalledClientConfig.from_file(secret_path)
    store = TokenStore(settings.data_dir)
    client = YouTubeApiClient(client_config=config, token_store=store, account_alias=account)
    return store, config, client


@youtube_app.command("login")
def login(
    account: Annotated[str, typer.Option("--account", "-a", help="Local alias, e.g. legendary-poet")] = "default",
    client_secret: Annotated[
        Path | None,
        typer.Option("--client-secret", help="Downloaded Google Desktop OAuth JSON file"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing token for this alias")] = False,
) -> None:
    """Authorize one Google/YouTube account with the read-only scope."""

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

    flow = InstalledOAuthFlow(config)
    console.print("[bold]Opening Google authorization in your browser…[/bold]")
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

    console.print(f"[green]Authorized YouTube account alias '{account}'.[/green]")
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
    table.add_column("Channels")
    table.add_column("Updated")
    for item in registered:
        channel_titles = ", ".join(channel.title for channel in item.channels) or "none"
        table.add_row(
            item.alias,
            "present" if store.token_exists(item.alias) else "missing",
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
