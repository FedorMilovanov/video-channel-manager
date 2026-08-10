from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import (
    VkAccessToken,
    VkAccount,
    VkAccountNotFoundError,
    VkApiClient,
    VkApiError,
    VkConfigurationError,
    VkInventoryService,
    VkTokenStore,
)
from video_channel_manager.platforms.vk.clips_audit import build_vk_clips_audit_snapshot

console = Console()
vk_app = typer.Typer(no_args_is_help=True, help="Read-only VK community, video, and album inventory.")


def _components(account: str) -> tuple[VkTokenStore, VkApiClient]:
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    client = VkApiClient(
        token_store=store,
        account_alias=account,
        api_version=settings.vk_api_version,
    )
    return store, client


def _read_token_input(token_file: Path | None) -> VkAccessToken:
    settings = get_settings()
    if token_file is not None:
        return VkAccessToken.from_file(token_file)
    if settings.vk_access_token is not None:
        return VkAccessToken.from_text(settings.vk_access_token.get_secret_value())
    raw = typer.prompt(
        "Paste a VK user access token or the complete redirect URL",
        hide_input=True,
        confirmation_prompt=False,
    )
    return VkAccessToken.from_text(raw)


@vk_app.command("login")
def login(
    account: Annotated[str, typer.Option("--account", "-a", help="Local alias, e.g. legendary-poet")] = "default",
    token_file: Annotated[
        Path | None,
        typer.Option("--token-file", help="Local ignored text/JSON file containing the user token or redirect URL"),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing token for this alias")] = False,
) -> None:
    """Import and validate a VK user token with video and groups permissions."""

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    try:
        account = store.validate_alias(account)
        if store.token_exists(account) and not force:
            console.print(
                f"[yellow]Account '{account}' is already authorized.[/yellow] "
                "Use --force only when you intentionally want to replace its token."
            )
            raise typer.Exit(code=2)
        token = _read_token_input(token_file)
        with TemporaryDirectory(prefix="video-manager-vk-login-") as temp_dir:
            validation_store = VkTokenStore(Path(temp_dir))
            validation_store.save_token(account, token)
            client = VkApiClient(
                token_store=validation_store,
                account_alias=account,
                api_version=settings.vk_api_version,
            )
            user = client.get_current_user()
            client.validate_video_access(user.user_id)
            communities = client.list_managed_communities()
        token.user_id = user.user_id
        store.save_token(account, token)
        store.save_account(
            VkAccount(
                alias=account,
                token_file=str(store.token_path(account)),
                user=user,
                communities=communities,
            )
        )
    except typer.Exit:
        raise
    except (OSError, ValueError, VkApiError, VkConfigurationError) as exc:
        console.print(f"[red]VK authorization failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(f"[green]Validated VK user account '{user.display_name}' as alias '{account}'.[/green]")
    console.print("The token is used only for read-only API calls by this version.")
    table = Table(title="Managed VK communities")
    table.add_column("Title")
    table.add_column("Community ID")
    table.add_column("Screen name")
    table.add_column("URL")
    for community in communities:
        table.add_row(
            community.title,
            str(community.community_id),
            community.screen_name or "",
            community.url,
        )
    console.print(table)
    if not communities:
        console.print("[yellow]No managed VK communities were returned for this user token.[/yellow]")


@vk_app.command("accounts")
def accounts() -> None:
    """List locally registered VK accounts without calling VK."""

    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    try:
        registered = store.list_accounts()
    except (OSError, ValueError) as exc:
        console.print(f"[red]Cannot read VK account registry:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if not registered:
        console.print("No VK accounts are registered. Run: video-manager vk login")
        return
    table = Table(title="VK user-token accounts")
    table.add_column("Alias")
    table.add_column("Token")
    table.add_column("User")
    table.add_column("Communities")
    table.add_column("Updated")
    for item in registered:
        community_titles = ", ".join(community.title for community in item.communities) or "none"
        table.add_row(
            item.alias,
            "present" if store.token_exists(item.alias) else "missing",
            item.user.display_name,
            community_titles,
            item.updated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        )
    console.print(table)


@vk_app.command("communities")
def communities(
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
) -> None:
    """Fetch communities currently managed by one authorized VK user."""

    try:
        store, client = _components(account)
        user = client.get_current_user()
        records = client.list_managed_communities()
        store.save_account(
            VkAccount(
                alias=account,
                token_file=str(store.token_path(account)),
                user=user,
                communities=records,
            )
        )
    except (VkAccountNotFoundError, OSError, ValueError, VkApiError) as exc:
        console.print(f"[red]Cannot read VK communities:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    table = Table(title=f"Managed VK communities for '{account}'")
    table.add_column("Title")
    table.add_column("Community ID")
    table.add_column("Screen name")
    table.add_column("URL")
    for item in records:
        table.add_row(item.title, str(item.community_id), item.screen_name or "", item.url)
    console.print(table)
    if not records:
        console.print("[yellow]No managed communities were returned.[/yellow]")


@vk_app.command("scan")
def scan(
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    community: Annotated[
        str | None,
        typer.Option("--community", "-c", help="Exact numeric VK community ID or screen name"),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Export a complete read-only AuditPackage for VK videos, albums, and memberships."""

    settings = get_settings()
    try:
        _, client = _components(account)
        if community is None:
            available = client.list_managed_communities()
            if len(available) != 1:
                choices = ", ".join(str(item.community_id) for item in available) or "none"
                raise ValueError(
                    f"Specify --community because this account has {len(available)} managed choices: {choices}"
                )
            community = str(available[0].community_id)
        with console.status("Reading VK community inventory..."):
            package = VkInventoryService(client).build_audit_package(community)
    except (VkAccountNotFoundError, OSError, ValueError, VkApiError) as exc:
        console.print(f"[red]VK scan failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        community_id = package.channel.ref.channel_id
        output = settings.data_dir / "exports" / f"vk-{account}-{community_id}-{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(package.model_dump_json(indent=2), encoding="utf-8")
    system_albums = sum(1 for item in package.collections if bool(item.metadata.get("is_system")))
    console.print(
        f"[green]Exported AuditPackage -> {output}[/green]\n"
        f"Videos: {len(package.videos)} | Albums: {len(package.collections)} "
        f"({system_albums} system) | Memberships: {len(package.memberships)}"
    )


@vk_app.command("clips-scan")
def clips_scan(
    project: Annotated[str, typer.Option("--project", help="Canonical project key")],
    community: Annotated[int, typer.Option("--community", "-c", help="Exact positive VK community ID")],
    owner_id: Annotated[int, typer.Option("--owner-id", help="Exact negative VK owner ID")],
    account: Annotated[str, typer.Option("--account", "-a", help="Local VK credential alias")] = "default",
    require_remote_id: Annotated[
        list[str] | None,
        typer.Option(
            "--require-remote-id",
            help="Exact Clip remote ID that must appear in the completed scan; repeat for multiple probes",
        ),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Export the exact read-only VK Clips surface for one canonical project."""

    settings = get_settings()
    try:
        _, client = _components(account)
        with console.status("Reading exact VK Clips surface..."):
            snapshot = build_vk_clips_audit_snapshot(
                client,
                project_key=project,
                community_id=community,
                owner_id=owner_id,
                required_remote_ids=require_remote_id or (),
            )
        if output is None:
            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            output = settings.data_dir / "exports" / f"vk-clips-{project}-{community}-{timestamp}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    except (VkAccountNotFoundError, OSError, ValueError, VkApiError) as exc:
        console.print(f"[red]VK Clips scan failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    coverage = snapshot["coverage"]
    console.print(
        f"[green]Exported exact VK Clips snapshot -> {output}[/green]\n"
        f"Project: {snapshot['project_key']} | Community: {community} | Owner: {owner_id} | "
        f"Clips: {coverage['clip_count']} | Provider writes: 0"
    )
