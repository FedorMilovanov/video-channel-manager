from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.config import get_settings
from video_channel_manager.domain.models import ChannelRecord
from video_channel_manager.platforms.youtube import (
    AccountNotFoundError,
    ChannelIdentity,
    InstalledClientConfig,
    InstalledOAuthFlow,
    OAuthFlowError,
    OAuthToken,
    TokenStore,
    YOUTUBE_FORCE_SSL_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    YouTubeAccount,
    YouTubeApiClient,
    YouTubeApiError,
    YouTubeDescriptionWriter,
    YouTubeInventoryService,
    YouTubeWriteError,
)
from video_channel_manager.platforms.youtube.lord_god_presentation import (
    presentation_issues,
    require_lord_god_youtube_presentation,
)
from video_channel_manager.platforms.youtube.lord_god_source_preservation import source_preservation_issues
from video_channel_manager.platforms.youtube.lord_god_source_preservation import LORD_GOD_OWNER_CHANNEL
from video_channel_manager.platforms.youtube.copy_execution import (
    preflight_copy_operations,
    reconcile_copy_operations,
    verify_copy_operations,
)
from video_channel_manager.platforms.youtube.chapter_release import require_chapter_release
from video_channel_manager.platforms.youtube.copy_plan import validate_copy_plan
from video_channel_manager.platforms.youtube.copy_output_safety import (
    prepare_windows_youtube_console,
    reserve_youtube_copy_journals,
)
from video_channel_manager.platforms.youtube.store import ProjectQuotaGuard, YouTubeQuotaBlocked
from video_channel_manager.platforms.youtube.write_lock import local_youtube_write_lock

console = Console()
youtube_app = typer.Typer(no_args_is_help=True, help="YouTube OAuth, inventory, and guarded description fixes.")


def _is_youtube_quota_exhaustion(exc: BaseException) -> bool:
    """Only classify an explicit YouTube 403 quota rejection; never infer from an arbitrary failure."""

    if not isinstance(exc, YouTubeWriteError):
        return False
    if isinstance(exc.__cause__, YouTubeQuotaBlocked):
        return True
    message = str(exc).casefold()
    return "youtube api 403" in message and ("quota" in message or "dailylimitexceeded" in message)


def _components(
    account: str, client_secret: Path | None = None
) -> tuple[TokenStore, InstalledClientConfig, YouTubeApiClient]:
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


def _require_lord_god_copy_execute_confirmation(
    payload: dict[str, Any],
    operations: list[dict[str, Any]],
    *,
    execute: bool,
    confirm_channel: str,
    confirm_target: str,
    confirm_after_sha256: str,
) -> None:
    """Block accidental Lord God description PUT before OAuth/API or file journals.

    Operator flags are separate from a frozen plan, but are NOT evidence of
    fresh human authorization. That permission must be established outside code.
    Other registered projects retain their existing CLI write contract.
    """
    if not execute:
        return
    targets_lord_god = (
        confirm_channel == LORD_GOD_OWNER_CHANNEL
        or payload.get("target_channel_id") == LORD_GOD_OWNER_CHANNEL
        or any(operation.get("channel_id") == LORD_GOD_OWNER_CHANNEL for operation in operations)
    )
    if not targets_lord_god:
        return
    if (
        payload.get("project_key") != "lord-god-strength"
        or payload.get("target_channel_id") != LORD_GOD_OWNER_CHANNEL
        or confirm_channel != LORD_GOD_OWNER_CHANNEL
        or len(operations) != 1
        or operations[0].get("channel_id") != LORD_GOD_OWNER_CHANNEL
    ):
        raise ValueError("Lord God descriptions require one exact owner-bound operation per execution")
    operation = operations[0]
    video_id = operation.get("video_id")
    after = operation.get("after_description")
    if not isinstance(video_id, str) or not video_id or not isinstance(after, str):
        raise ValueError("Lord God operation lacks an exact video ID or new description")
    expected_sha = "sha256:" + hashlib.sha256(after.encode("utf-8")).hexdigest()
    if confirm_target != video_id or confirm_after_sha256 != expected_sha:
        raise ValueError(
            "Lord God copy execution requires independent --confirm-target VIDEO_ID "
            "and --confirm-after-sha256 matching the reviewed new description."
        )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Durable atomic JSON replacement with a unique, exclusive temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _show_oauth_storage(store: TokenStore) -> None:
    """Expose the actual credential location without logging credential contents."""
    console.print(f"[dim]YouTube OAuth token directory: {store.token_dir.resolve()}[/dim]", soft_wrap=True)
    if not store.data_dir.is_absolute():
        console.print(
            "[yellow]VCM_DATA_DIR is relative to the current working directory. "
            "A command launched from another folder uses a DIFFERENT OAuth token store. "
            "Pin VCM_DATA_DIR to an absolute path for operator workflows.[/yellow]"
        )


class _CandidateOAuthTokenStore(TokenStore):
    """In-memory candidate grant: do not replace a real alias until identity matches."""

    def __init__(self, token: OAuthToken) -> None:
        super().__init__(get_settings().data_dir)
        self._token = token

    def load_token(self, alias: str) -> OAuthToken:
        self.validate_alias(alias)
        return self._token

    def save_token(self, alias: str, token: OAuthToken) -> Path:
        self.validate_alias(alias)
        self._token = token
        return Path(":not-persisted:")


def _read_candidate_oauth_channels(
    *,
    config: InstalledClientConfig,
    account: str,
    token: OAuthToken,
) -> list[ChannelRecord]:
    """Owner GET before touching the durable token or account registry."""
    ephemeral = _CandidateOAuthTokenStore(token)
    client = YouTubeApiClient(client_config=config, token_store=ephemeral, account_alias=account)
    try:
        return client.list_my_channels()
    finally:
        client.close()


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

    _show_oauth_storage(store)
    try:
        registered = next((item for item in store.list_accounts() if item.alias == account), None)
    except (OSError, ValueError) as exc:
        console.print(f"[red]YouTube account registry unavailable:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    expected_channel_ids = {channel.channel_id for channel in registered.channels} if registered else set()
    if (registered and not expected_channel_ids) or (store.token_exists(account) and not registered):
        console.print(
            "[red]Existing OAuth alias has no trusted channel identity; refusing replacement. "
            "Repair the account registry before reauthorization.[/red]"
        )
        raise typer.Exit(code=2)
    if store.token_exists(account) and not force:
        console.print(
            f"[yellow]Account '{account}' is already authorized.[/yellow] "
            "Use --force only when you intentionally want to replace its token."
        )
        raise typer.Exit(code=2)

    # force-ssl already permits owner reads and writes; requesting a second
    # optional read-only consent can silently produce an unusable partial grant.
    scopes = (YOUTUBE_FORCE_SSL_SCOPE,) if write else (YOUTUBE_READONLY_SCOPE,)
    flow = InstalledOAuthFlow(config, scopes=scopes)
    console.print("[bold]Opening Google authorization in your browser…[/bold]")
    if write:
        console.print(
            "[yellow]Write access requested.[/yellow] The application still writes only through explicit "
            "description-guarded commands with backups, a local process lock, and --execute."
        )
    else:
        console.print("Only the read-only YouTube scope is requested. No channel changes can be made.")
    try:
        token = flow.authorize(
            timeout_seconds=settings.youtube_oauth_timeout_seconds,
            force_consent=True,
            on_authorization_url=lambda url: console.print(
                f"If the browser does not open, copy this URL:\n[link={url}]{url}[/link]"
            ),
        )
        missing_scopes = set(scopes).difference(token.scopes)
        if missing_scopes:
            requested_access = (
                "YouTube write access" if YOUTUBE_FORCE_SSL_SCOPE in missing_scopes else "YouTube read access"
            )
            raise OAuthFlowError(
                f"Google did not grant the requested {requested_access}. "
                "Review the requested permissions on the Google consent screen. "
                "No account token was saved or replaced."
            )
        if not token.refresh_token:
            raise OAuthFlowError(
                "Google did not issue an offline refresh token. The existing YouTube account token was not replaced."
            )
        channels = _read_candidate_oauth_channels(config=config, account=account, token=token)
        actual_channel_ids = {item.ref.remote_id for item in channels}
        if expected_channel_ids and actual_channel_ids != expected_channel_ids:
            raise OAuthFlowError(
                "Google authorized a different YouTube channel than the existing alias. "
                f"Expected {sorted(expected_channel_ids)!r}; received {sorted(actual_channel_ids)!r}. "
                "Neither the original token nor the account registry was changed."
            )
        if not channels:
            raise OAuthFlowError(
                "Google authorization returned no owned YouTube channels; "
                "neither the original token nor the account registry was changed."
            )
        account_record = YouTubeAccount(
            alias=account,
            token_file=str(store.token_path(account)),
            channels=[
                ChannelIdentity(channel_id=item.ref.remote_id, title=item.title, url=item.url or "")
                for item in channels
            ],
        )
        # Only an exact provider-confirmed channel and complete scope grant can replace
        # a trusted alias. The previous token stays untouched on every failed preflight.
        store.save_token(account, token)
        store.save_account(account_record)
    except (OAuthFlowError, YouTubeApiError, ValueError, OSError) as exc:
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
    _show_oauth_storage(store)
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
    except (AccountNotFoundError, OAuthFlowError, OSError, ValueError, YouTubeApiError) as exc:
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


def _local_quota_guard(client_secret: Path | None) -> ProjectQuotaGuard:
    settings = get_settings()
    config = InstalledClientConfig.from_file(client_secret or settings.youtube_client_secret_file)
    guard = ProjectQuotaGuard.for_client(settings.data_dir, config.client_id, "quota-operator")
    if guard is None:
        raise ValueError("Cannot derive the Google Cloud project number from the installed OAuth client.")
    return guard


@youtube_app.command("quota-status")
def quota_status(
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Report local quota accounting without contacting Google."""
    try:
        guard = _local_quota_guard(client_secret)
        console.print_json(data={"project_number": guard.path.stem, **guard.budget_status()})
    except (OSError, ValueError, YouTubeQuotaBlocked) as exc:
        console.print(f"[red]Quota status failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@youtube_app.command("quota-configure")
def quota_configure(
    project_number: Annotated[str, typer.Option("--confirm-project-number")],
    day: Annotated[str, typer.Option("--pacific-day")],
    shared: Annotated[int, typer.Option("--shared", min=0)],
    search: Annotated[int, typer.Option("--search", min=0)],
    uploads: Annotated[int, typer.Option("--uploads", min=0)],
    evidence: Annotated[
        str, typer.Option("--evidence", help="Non-secret reference to reviewed Cloud Console evidence")
    ],
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Enable one immutable daily LOCAL allowance, not a Google quota grant."""
    try:
        guard = _local_quota_guard(client_secret)
        if project_number != guard.path.stem:
            raise ValueError("Google Cloud project number mismatch; no local allowance changed.")
        guard.configure_day(
            day=day, allowances={"shared": shared, "search": search, "uploads": uploads}, evidence=evidence
        )
        console.print_json(data={"project_number": guard.path.stem, **guard.budget_status()})
    except (OSError, ValueError, YouTubeQuotaBlocked) as exc:
        console.print(f"[red]Quota configuration failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@youtube_app.command("recent")
def recent(
    account: Annotated[str, typer.Option("--account", "-a")],
    channel_id: Annotated[str, typer.Option("--channel", help="Exact YouTube owner channel ID")],
    limit: Annotated[int, typer.Option("--limit", min=1, max=50)] = 10,
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Read one bounded uploads page for exact-ID candidate discovery, without writes."""

    prepare_windows_youtube_console()
    try:
        _, _, client = _components(account, client_secret)
        with client:
            if channel_id not in {item.ref.remote_id for item in client.list_my_channels()}:
                raise ValueError("Requested --channel does not belong to the authenticated --account.")
            records = client.list_recent_videos(channel_id, limit=limit)
        console.print_json(
            data={
                "scope": "bounded_recent_upload_candidates_not_full_inventory",
                "channel_id": channel_id,
                "limit": limit,
                "items": [
                    {
                        "video_id": item.ref.remote_id,
                        "title": item.title,
                        "duration_seconds": item.duration_seconds,
                        "published_at": item.published_at.isoformat() if item.published_at else None,
                        "privacy_status": item.privacy_status,
                        "file_details": item.metadata.get("fileDetails"),
                    }
                    for item in records
                ],
            }
        )
    except (AccountNotFoundError, OAuthFlowError, OSError, ValueError, YouTubeApiError) as exc:
        console.print(f"[red]YouTube recent lookup failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@youtube_app.command("scan")
def scan(
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    channel_id: Annotated[str | None, typer.Option("--channel", help="Exact YouTube channel ID")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Export a complete read-only AuditPackage for videos, playlists, and memberships."""

    # The AuditPackage is already durable when the completion receipt prints.
    # A cp1252/cp866 Windows terminal must not turn that successful scan into
    # a misleading nonzero result when the receipt contains a Unicode arrow
    # or a Cyrillic operator-selected output path.
    prepare_windows_youtube_console()
    settings = get_settings()
    try:
        _, _, client = _components(account, client_secret)
        available_channels = client.list_my_channels()
        if channel_id is None:
            if len(available_channels) != 1:
                choices = ", ".join(item.ref.remote_id for item in available_channels) or "none"
                raise ValueError(
                    f"Specify --channel because this account has {len(available_channels)} choices: {choices}"
                )
            channel_id = available_channels[0].ref.remote_id
        elif channel_id not in {item.ref.remote_id for item in available_channels}:
            raise ValueError(
                "Requested --channel does not belong to the authenticated --account; "
                "select the matching YouTube/Brand Account."
            )
        with console.status("Reading YouTube channel inventory…"):
            package = YouTubeInventoryService(client).build_audit_package(channel_id)
    except (AccountNotFoundError, OAuthFlowError, OSError, ValueError, YouTubeApiError) as exc:
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
    confirm_target: Annotated[
        str,
        typer.Option("--confirm-target", help="Lord God one-video write: type exact YouTube VIDEO_ID"),
    ] = "",
    confirm_after_sha256: Annotated[
        str,
        typer.Option("--confirm-after-sha256", help="Lord God write: type reviewed SHA of new description"),
    ] = "",
    max_operations: Annotated[
        int,
        typer.Option("--max-operations", min=1, max=500, help="Safety cap for one run"),
    ] = 100,
    backup_output: Annotated[Path | None, typer.Option("--backup-output")] = None,
    result_output: Annotated[Path | None, typer.Option("--result-output")] = None,
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
    confirm_chapter_review_sha256: Annotated[
        str, typer.Option("--confirm-chapter-review-sha256", help="Exact approved chapter review file SHA-256")
    ] = "",
) -> None:
    """Preflight or apply description-guarded fixes with retries, postflight, and rollback."""

    prepare_windows_youtube_console()
    settings = get_settings()
    try:
        payload = _load_copy_fix_plan(plan)
        # Project-bound YouTube display/retired-contact rules run BEFORE any OAuth or API use.
        require_lord_god_youtube_presentation(payload)
        raw_operations = payload["operations"]
        operations = [item for item in raw_operations if isinstance(item, dict)]
        if not operations:
            raise ValueError("Copy-fix plan has no operations.")
        if len(operations) > max_operations:
            raise ValueError(f"Plan has {len(operations)} operations, above --max-operations {max_operations}.")
        if not confirm_channel:
            raise ValueError("--confirm-channel with the exact YouTube channel ID is required.")
        _require_lord_god_copy_execute_confirmation(
            payload,
            operations,
            execute=execute,
            confirm_channel=confirm_channel,
            confirm_target=confirm_target,
            confirm_after_sha256=confirm_after_sha256,
        )
        require_chapter_release(payload, execute=execute, confirm_review_sha256=confirm_chapter_review_sha256)
        store, _, writer = _writer_components(account, client_secret)
    except (AccountNotFoundError, OSError, ValueError) as exc:
        console.print(f"[red]Cannot load copy-fix plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    lock_path = settings.data_dir / "locks" / f"youtube-{account}-{confirm_channel}.lock"
    lock_context = (
        local_youtube_write_lock(lock_path, account=account, channel_id=confirm_channel) if execute else nullcontext()
    )

    try:
        with lock_context:
            try:
                with console.status(f"Preflighting {len(operations)} descriptions against live YouTube…"):
                    preflight = preflight_copy_operations(
                        operations,
                        confirm_channel=confirm_channel,
                        writer=writer,
                        require_plan_title=(
                            payload.get("target_channel_id") == LORD_GOD_OWNER_CHANNEL
                            and payload.get("project_key") == "lord-god-strength"
                        ),
                    )
            except (ValueError, YouTubeWriteError) as exc:
                console.print(f"[red]Preflight failed; nothing was changed:[/red] {exc}")
                raise typer.Exit(code=2) from exc

            console.print(
                f"[green]Preflight passed.[/green] Ready: {len(preflight.prepared)} | "
                f"Already applied: {preflight.already_applied} | "
                f"Revision drift tolerated: {preflight.revision_drift_tolerated} | "
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

            if not preflight.prepared:
                console.print("[bold green]Nothing to change; every operation is already applied.[/bold green]")
                return

            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            if backup_output is None:
                backup_output = settings.data_dir / "reports" / f"youtube-copy-backup-{timestamp}.json"
            if result_output is None:
                result_output = settings.data_dir / "reports" / f"youtube-copy-apply-{timestamp}.json"

            # The exact approved chapter artifact may have changed during preflight.
            try:
                require_chapter_release(payload, execute=True, confirm_review_sha256=confirm_chapter_review_sha256)
            except (OSError, ValueError) as exc:
                console.print(f"[red]Chapter release blocked; no YouTube write:[/red] {exc}")
                raise typer.Exit(code=2) from exc

            # Before dispatching a YouTube write, reserve both unique journal
            # paths and prove that their volume has sufficient free space.
            # Existing backups/results are immutable recovery evidence.
            try:
                reserve_youtube_copy_journals(
                    plan_path=plan,
                    backup_output=backup_output,
                    result_output=result_output,
                )
            except (OSError, ValueError) as exc:
                console.print(f"[red]Output safety preflight failed; no YouTube write:[/red] {exc}")
                raise typer.Exit(code=2) from exc

            backup_payload = {
                "schema_name": "video-manager.youtube-copy-backup",
                "schema_version": 2,
                "created_at": datetime.now(UTC).isoformat(),
                "source_plan": str(plan),
                "account": account,
                "channel_id": confirm_channel,
                "already_applied": preflight.already_applied,
                "revision_drift_tolerated": preflight.revision_drift_tolerated,
                "operations": preflight.prepared,
            }
            _write_json(backup_output, backup_payload)
            console.print(f"Backup written before mutation → {backup_output}")

            attempted: list[dict[str, Any]] = []
            applied: list[dict[str, Any]] = []
            rollback_results: list[dict[str, Any]] = []
            result: dict[str, Any] = {
                "schema_name": "video-manager.youtube-copy-apply-result",
                "schema_version": 2,
                "started_at": datetime.now(UTC).isoformat(),
                "source_plan": str(plan),
                "backup": str(backup_output),
                "account": account,
                "channel_id": confirm_channel,
                "status": "running",
                "summary": {
                    "planned": len(operations),
                    "prepared": len(preflight.prepared),
                    "already_applied": preflight.already_applied,
                    "revision_drift_tolerated": preflight.revision_drift_tolerated,
                    "attempted": 0,
                    "applied": 0,
                    "postflight_verified": 0,
                    "rollback_safe_original": 0,
                    "rollback_failed": 0,
                },
                "attempted": attempted,
                "applied": applied,
                "postflight_failures": [],
                "rollback": rollback_results,
            }
            _write_json(result_output, result)

            failure: str | None = None
            interrupted: BaseException | None = None
            quota_reconciliation_pending = False
            try:
                for operation in preflight.prepared:
                    attempt_record = {
                        "video_id": operation["video_id"],
                        "title": operation["title"],
                        "started_at": datetime.now(UTC).isoformat(),
                        "status": "attempting",
                    }
                    attempted.append(attempt_record)
                    result["summary"]["attempted"] = len(attempted)
                    _write_json(result_output, result)

                    verified = writer.replace_description(
                        video_id=str(operation["video_id"]),
                        expected_channel_id=str(operation["channel_id"]),
                        expected_revision=str(operation["expected_revision"]),
                        expected_description=str(operation["before_description"]),
                        new_description=str(operation["after_description"]),
                    )
                    attempt_record["status"] = "verified"
                    attempt_record["finished_at"] = datetime.now(UTC).isoformat()
                    applied.append(
                        {
                            **operation,
                            "after_revision": verified.revision,
                            "verified": True,
                        }
                    )
                    result["summary"]["applied"] = len(applied)
                    _write_json(result_output, result)
                    console.print(f"[green]Updated and verified[/green] {verified.video_id} — {verified.title}")

                postflight_failures = verify_copy_operations(
                    preflight.prepared,
                    confirm_channel=confirm_channel,
                    writer=writer,
                )
                result["postflight_failures"] = postflight_failures
                if postflight_failures:
                    failed_ids = ", ".join(item["video_id"] for item in postflight_failures)
                    raise YouTubeWriteError(f"Final batch postflight failed for: {failed_ids}")
                result["summary"]["postflight_verified"] = len(preflight.prepared)
            except BaseException as exc:  # preserve journal even on Ctrl+C or unexpected runtime failures
                interrupted = exc
                failure = f"{type(exc).__name__}: {exc}"
                # Quota may disappear AFTER YouTube has accepted and verified the PUT.
                # An immediate rollback would use another quota-costly PUT and could
                # undo a successful change. Persist the unknown terminal state instead.
                quota_reconciliation_pending = bool(attempted) and _is_youtube_quota_exhaustion(exc)
                if quota_reconciliation_pending:
                    console.print(
                        "[yellow]YouTube quota exhausted after a write attempt; "
                        "no rollback or replay. Fresh owner reconciliation is required.[/yellow]"
                    )
                else:
                    console.print(f"[red]Apply failed; starting guarded rollback:[/red] {exc}")

            if failure is not None:
                if quota_reconciliation_pending:
                    result["status"] = "pending_reconciliation"
                    result["error"] = failure
                else:
                    for operation in reversed(preflight.prepared[: len(attempted)]):
                        video_id = str(operation["video_id"])
                        try:
                            restored = writer.restore_description_if_current(
                                video_id=video_id,
                                expected_channel_id=str(operation["channel_id"]),
                                expected_current_description=str(operation["after_description"]),
                                restore_description=str(operation["before_description"]),
                            )
                            rollback_results.append(
                                {
                                    "video_id": video_id,
                                    "status": "safe_original",
                                    "revision": restored.revision,
                                }
                            )
                            console.print(f"[yellow]Rollback safe/original[/yellow] {video_id}")
                        except YouTubeWriteError as rollback_exc:
                            rollback_results.append(
                                {"video_id": video_id, "status": "failed", "error": str(rollback_exc)}
                            )
                            console.print(f"[red]Rollback failed[/red] {video_id}: {rollback_exc}")
                        result["summary"]["rollback_safe_original"] = sum(
                            item["status"] == "safe_original" for item in rollback_results
                        )
                        result["summary"]["rollback_failed"] = sum(
                            item["status"] == "failed" for item in rollback_results
                        )
                        _write_json(result_output, result)

                    rollback_failed = int(result["summary"]["rollback_failed"])
                    result["status"] = "failed_rolled_back" if rollback_failed == 0 else "failed_partial_rollback"
                    result["error"] = failure
            else:
                result["status"] = "completed"

            result["finished_at"] = datetime.now(UTC).isoformat()
            _write_json(result_output, result)
            console.print(f"Result log → {result_output}")

            if failure is not None:
                if isinstance(interrupted, KeyboardInterrupt):
                    raise interrupted
                raise typer.Exit(code=2)
            console.print(
                f"[bold green]Completed {len(applied)} verified description updates; "
                f"final postflight verified the whole batch.[/bold green]"
            )
    except YouTubeWriteError as exc:
        console.print(f"[red]YouTube write safety error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


def _read_optional_youtube_recovery_json(path: Path) -> dict[str, Any] | None:
    """An absent journal is a reported uncertainty; a corrupt one is an error."""

    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read YouTube recovery evidence at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"YouTube recovery evidence at {path} is not a JSON object.")
    return value


@youtube_app.command("apply-localization-fix")
def apply_localization_fix(
    plan: Annotated[Path, typer.Argument(help="Frozen one-video non-default-language correction JSON")],
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    confirm_channel: Annotated[str, typer.Option("--confirm-channel")] = "",
    execute: Annotated[bool, typer.Option("--execute")] = False,
    confirm_target: Annotated[
        str, typer.Option("--confirm-target", help="Type exact VIDEO_ID@LOCALE for this one write")
    ] = "",
    confirm_after_sha256: Annotated[
        str, typer.Option("--confirm-after-sha256", help="Type exact reviewed SHA of the proposed new locale")
    ] = "",
    backup_output: Annotated[Path | None, typer.Option("--backup-output")] = None,
    result_output: Annotated[Path | None, typer.Option("--result-output")] = None,
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Guard a single non-default localized description; never replay or auto-rollback."""
    prepare_windows_youtube_console()

    def sha(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    try:
        payload = json.loads(plan.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Expected localization plan object.")
        if (
            payload.get("schema_name") != "video-manager.youtube-localization-fix-plan"
            or payload.get("schema_version") != 1
        ):
            raise ValueError("Unsupported localization-fix plan schema.")
        if payload.get("project_key") != "lord-god-strength":
            raise ValueError("Incorrect project identity.")
        if payload.get("channel_id") != LORD_GOD_OWNER_CHANNEL or confirm_channel != LORD_GOD_OWNER_CHANNEL:
            raise ValueError("Exact Lord God channel confirmation required.")
        video_id = payload["video_id"]
        language = payload["language"]
        expected_title = payload["expected_title"]
        before_primary = payload["expected_primary_description"]
        expected_locales = payload["expected_localizations"]
        before_locale = payload["expected_localized_description"]
        after_locale = payload["after_description"]
        expected_snippet = payload["expected_snippet_fields"]
        expected_privacy = payload["expected_privacy"]
        expected_duration = payload["expected_duration"]
        if not all(
            isinstance(v, str) and v
            for v in (
                video_id,
                language,
                expected_title,
                before_primary,
                before_locale,
                after_locale,
                expected_privacy,
                expected_duration,
            )
        ):
            raise ValueError("Incomplete localization plan.")
        if not isinstance(expected_snippet, dict) or set(expected_snippet) != {
            "title",
            "categoryId",
            "tags",
            "defaultLanguage",
            "defaultAudioLanguage",
        }:
            raise ValueError("Incomplete expected snippet fields.")
        if expected_snippet["title"] != expected_title or language == expected_snippet["defaultLanguage"]:
            raise ValueError("Only an existing non-default locale may be corrected.")
        if not isinstance(expected_locales, dict) or language not in expected_locales:
            raise ValueError("Missing frozen localization map.")
        if not all(
            isinstance(k, str)
            and k
            and isinstance(v, dict)
            and set(v) == {"title", "description"}
            and isinstance(v["title"], str)
            and v["title"]
            and isinstance(v["description"], str)
            for k, v in expected_locales.items()
        ):
            raise ValueError("Invalid frozen localization map.")
        if before_locale != expected_locales[language]["description"]:
            raise ValueError("Inconsistent target locale.")
        if (
            sha(before_primary) != payload.get("expected_primary_sha256")
            or sha(before_locale) != payload.get("before_sha256")
            or sha(after_locale) != payload.get("after_sha256")
        ):
            raise ValueError("Plan text SHA-256 mismatch.")
        if len(after_locale.encode("utf-8")) > 5000:
            raise ValueError("Localized description over 5,000 UTF-8 bytes.")
        if source_preservation_issues(before_locale, after_locale) or presentation_issues(after_locale):
            raise ValueError("Localized editorial/source-preservation gate failed.")
        if execute and payload.get("provider_mutation_authorized") is not True:
            raise ValueError("This frozen plan has no explicit provider-write authorization.")
        if execute and (confirm_target != f"{video_id}@{language}" or confirm_after_sha256 != sha(after_locale)):
            raise ValueError(
                "Executing localization requires independent --confirm-target VIDEO_ID@LOCALE "
                "and --confirm-after-sha256 matching the reviewed new text."
            )
        if expected_locales.get(expected_snippet["defaultLanguage"], {}).get("description") != before_primary:
            raise ValueError("Default-language locale differs from primary text; cannot safely PUT.")
        store, config, writer = _writer_components(account, client_secret)
        settings = get_settings()
    except (OSError, KeyError, TypeError, ValueError, AccountNotFoundError) as exc:
        console.print(f"[red]Localization plan rejected; no provider write:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    lock_path = settings.data_dir / "locks" / f"youtube-{account}-{confirm_channel}.lock"
    lock = (
        local_youtube_write_lock(lock_path, account=account, channel_id=confirm_channel) if execute else nullcontext()
    )
    try:
        with lock:
            try:
                api = YouTubeApiClient(client_config=config, token_store=store, account_alias=account)
                channels = api.list_my_channels()
                if len(channels) != 1 or channels[0].ref.remote_id != confirm_channel:
                    raise ValueError("OAuth owner-channel proof failed.")
                current = writer.read_description(video_id)
                sn = current.raw.get("snippet") or {}
                protected = ("title", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage")
                conditions = {
                    "owner": current.channel_id == confirm_channel,
                    "title": current.title == expected_title,
                    "primary_description": current.description == before_primary,
                    "snippet_metadata": {k: sn.get(k) for k in protected} == expected_snippet,
                    "privacy": (current.raw.get("status") or {}).get("privacyStatus") == expected_privacy,
                    "duration": (current.raw.get("contentDetails") or {}).get("duration") == expected_duration,
                    "localized_map": current.raw.get("localizations") == expected_locales,
                    "language": sn.get("defaultLanguage") != language and bool(sn.get("defaultAudioLanguage")),
                }
                if not all(conditions.values()):
                    raise ValueError(
                        f"Live localization preflight drift: {[k for k, v in conditions.items() if not v]}"
                    )
            except (ValueError, YouTubeWriteError, YouTubeApiError) as exc:
                console.print(f"[red]Localization preflight failed, no PUT:[/red] {exc}")
                raise typer.Exit(code=2) from exc
            if before_locale == after_locale:
                console.print("[green]Identical localized text, no provider action required.[/green]")
                return
            console.print(f"[green]Localization preflight passed.[/green] {video_id} | {language} | {confirm_channel}")
            if not execute:
                console.print("Dry-run only. An explicit --execute and fresh owner check are required.")
                return
            try:
                if YOUTUBE_FORCE_SSL_SCOPE not in store.load_token(account).scopes:
                    raise ValueError("OAuth write scope not granted.")
                if backup_output is None or result_output is None:
                    raise ValueError("Explicit separate --backup-output and --result-output required.")
                reserve_youtube_copy_journals(plan_path=plan, backup_output=backup_output, result_output=result_output)
                before_record = {
                    "schema_name": "video-manager.youtube-localization-before",
                    "video_id": video_id,
                    "channel_id": confirm_channel,
                    "locale": language,
                    "source_plan": str(plan),
                    "created_at": datetime.now(UTC).isoformat(),
                    "snapshot": current.raw,
                }
                _write_json(backup_output, before_record)
                record = {
                    "schema_name": "video-manager.youtube-localization-result",
                    "schema_version": 1,
                    "source_plan": str(plan),
                    "backup": str(backup_output),
                    "video_id": video_id,
                    "channel_id": confirm_channel,
                    "locale": language,
                    "started_at": datetime.now(UTC).isoformat(),
                    "status": "pending_reconciliation",
                    "provider_dispatch": "may_exist",
                    "before_sha256": sha(before_locale),
                    "after_sha256": sha(after_locale),
                }
                _write_json(result_output, record)
            except (OSError, ValueError) as exc:
                console.print(f"[red]Localization output safety failed; no PUT:[/red] {exc}")
                raise typer.Exit(code=2) from exc
            try:
                writer.replace_localized_description(
                    video_id=video_id,
                    expected_channel_id=confirm_channel,
                    expected_title=expected_title,
                    expected_primary_description=before_primary,
                    expected_snippet_fields=expected_snippet,
                    expected_privacy=expected_privacy,
                    expected_duration=expected_duration,
                    expected_localizations=expected_locales,
                    language=language,
                    expected_localized_description=before_locale,
                    new_description=after_locale,
                )
                independent = writer.read_description(video_id)
                new_map = dict(expected_locales)
                new_map[language] = {**expected_locales[language], "description": after_locale}
                if (
                    independent.channel_id != confirm_channel
                    or independent.description != before_primary
                    or independent.raw.get("localizations") != new_map
                    or (independent.raw.get("status") or {}).get("privacyStatus") != expected_privacy
                    or {k: (independent.raw.get("snippet") or {}).get(k) for k in protected} != expected_snippet
                ):
                    raise YouTubeWriteError("Independent localized postflight mismatch; no replay.")
                record["status"] = "completed"
                record["provider_dispatch"] = "verified"
                record["verified_at"] = datetime.now(UTC).isoformat()
                record["verified_locale_sha256"] = sha(independent.raw["localizations"][language]["description"])
                _write_json(result_output, record)
                console.print(f"[green]Localization updated and independently verified:[/green] {video_id} {language}")
            except BaseException as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
                _write_json(result_output, record)
                console.print(
                    f"[red]Localization outcome requires read-only reconciliation; do not replay:[/red] {exc}"
                )
                raise typer.Exit(code=2) from exc
    except TimeoutError as exc:
        console.print(f"[red]YouTube writer lock is busy; nothing dispatched:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@youtube_app.command("reconcile-copy-fixes")
def reconcile_copy_fixes(
    plan: Annotated[Path, typer.Argument(help="Existing signed v3 copy plan; read only")],
    backup: Annotated[Path, typer.Option("--backup", help="Exact existing backup path; not modified")],
    result: Annotated[Path, typer.Option("--result", help="Exact existing apply-result path; not modified")],
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    confirm_channel: Annotated[str, typer.Option("--confirm-channel", help="Exact owner YouTube channel ID")] = "",
    report_output: Annotated[
        Path | None, typer.Option("--report-output", help="Optional new JSON evidence path; never overwrite")
    ] = None,
    client_secret: Annotated[Path | None, typer.Option("--client-secret")] = None,
) -> None:
    """Read-only owner reconciliation. Never dispatch, repeat, or roll back a write."""

    prepare_windows_youtube_console()
    try:
        payload = _load_copy_fix_plan(plan)
        validate_copy_plan(payload)
        # Historical signed plans may predate today's publication/source-preservation
        # gate. They must remain readable for no-replay incident reconciliation.
        # This command performs owner GET only; the apply command retains the
        # strict publication guard before any provider preflight or mutation.
        if not confirm_channel or payload["target_channel_id"] != confirm_channel:
            raise ValueError("Signed plan target_channel_id differs from --confirm-channel.")
        if len({plan.resolve(), backup.resolve(), result.resolve()}) != 3:
            raise ValueError("Plan, backup, and result paths must be distinct.")
        if report_output is not None:
            if report_output.resolve() in {plan.resolve(), backup.resolve(), result.resolve()}:
                raise ValueError("Read-only report output cannot overwrite a plan, backup, or result.")
            if report_output.exists():
                raise FileExistsError(f"Read-only report already exists: {report_output}")
        back = _read_optional_youtube_recovery_json(backup)
        receipt = _read_optional_youtube_recovery_json(result)
        expected_operations: dict[str, dict[str, Any]] = {str(op["video_id"]): op for op in payload["operations"]}
        backup_ids: list[str] = []
        if back is None:
            backup_state = "missing"
        elif back.get("schema_name") == "video-manager.youtube-copy-output-reservation":
            backup_state = "reserved_only"
        elif back.get("schema_name") == "video-manager.youtube-copy-backup":
            if back.get("channel_id") != confirm_channel or back.get("account") != account:
                raise ValueError("Backup account or channel does not match the requested owner.")
            if Path(str(back.get("source_plan", ""))).resolve() != plan.resolve():
                raise ValueError("Backup source_plan does not match the signed plan path.")
            back_operations = back.get("operations")
            if not isinstance(back_operations, list):
                raise ValueError("Backup operations must be an array.")
            for operation in back_operations:
                if not isinstance(operation, dict):
                    raise ValueError("Backup operation must be an object.")
                video_id = str(operation.get("video_id", ""))
                expected = expected_operations.get(video_id)
                if expected is None:
                    raise ValueError(f"Backup contains an unapproved video: {video_id}")
                if video_id in backup_ids:
                    raise ValueError(f"Backup repeats a video ID: {video_id}")
                backup_ids.append(video_id)
                if any(
                    operation.get(key) != expected.get(key)
                    for key in ("channel_id", "before_description", "after_description")
                ):
                    raise ValueError(f"Backup before/after evidence differs from signed plan: {video_id}")
            backup_state = "bound_backup"
        else:
            raise ValueError("Backup file does not contain a supported YouTube copy backup or reservation.")

        if receipt is None:
            receipt_state = "missing"
        elif receipt.get("schema_name") == "video-manager.youtube-copy-output-reservation":
            receipt_state = "reserved_only"
        elif receipt.get("schema_name") == "video-manager.youtube-copy-apply-result":
            if receipt.get("account") != account or receipt.get("channel_id") != confirm_channel:
                raise ValueError("Result account or channel does not match the requested owner.")
            if Path(str(receipt.get("source_plan", ""))).resolve() != plan.resolve():
                raise ValueError("Result source_plan does not match signed plan path.")
            if Path(str(receipt.get("backup", ""))).resolve() != backup.resolve():
                raise ValueError("Result backup path differs from the supplied backup.")
            receipt_state = str(receipt.get("status") or "invalid_missing_status")
            if receipt_state not in {
                "running",
                "completed",
                "failed_rolled_back",
                "failed_partial_rollback",
                "pending_reconciliation",
            }:
                raise ValueError("Unsupported or missing result terminal/intermediate status.")
            for field in ("attempted", "applied"):
                entries = receipt.get(field)
                if not isinstance(entries, list) or any(
                    not isinstance(entry, dict) or str(entry.get("video_id", "")) not in expected_operations
                    for entry in entries
                ):
                    raise ValueError(f"Result contains invalid {field} entries.")
        else:
            raise ValueError("Result is not a supported YouTube copy receipt or reservation.")

        _, _, writer = _writer_components(account, client_secret)
        rows = reconcile_copy_operations(
            payload["operations"],
            confirm_channel=confirm_channel,
            writer=writer,
        )
        live_states = [str(row["state"]) for row in rows]
        if any(state == "live_third_state" for state in live_states):
            outcome = "manual_or_concurrent_description_conflict"
        elif all(state == "live_after" for state in live_states):
            if receipt_state == "completed" and backup_state == "bound_backup" and receipt is not None:
                summary = receipt.get("summary")
                complete = (
                    isinstance(summary, dict)
                    and summary.get("postflight_verified") == len(rows)
                    and summary.get("applied") == len(rows)
                    and summary.get("attempted") == len(rows)
                    and set(backup_ids) == set(expected_operations)
                    and len(backup_ids) == len(rows)
                    and len(receipt["applied"]) == len(rows)
                    and len(receipt["attempted"]) == len(rows)
                    and {str(entry["video_id"]) for entry in receipt["applied"]} == set(expected_operations)
                    and {str(entry["video_id"]) for entry in receipt["attempted"]} == set(expected_operations)
                )
                outcome = "completed_live_verified" if complete else "live_after_receipt_not_terminally_verified"
            else:
                outcome = "live_after_receipt_not_terminally_verified"
        else:
            outcome = "live_before_or_partial_unknown_no_replay"

        report: dict[str, Any] = {
            "schema_name": "video-manager.youtube-copy-readonly-reconciliation",
            "schema_version": 1,
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "plan_sha256": payload["plan_sha256"],
            "channel_id": confirm_channel,
            "account": account,
            "backup_state": backup_state,
            "receipt_state": receipt_state,
            "outcome": outcome,
            "terminally_verified": outcome == "completed_live_verified",
            "safe_to_replay": False,
            "provider_writes": 0,
            "rows": rows,
        }
        console.print(json.dumps(report, ensure_ascii=True, indent=2))
        if report_output is not None:
            report_output.parent.mkdir(parents=True, exist_ok=True)
            with report_output.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            console.print(f"Read-only evidence saved to {report_output}")

        if not report["terminally_verified"]:
            raise typer.Exit(code=2)
    except (AccountNotFoundError, OSError, ValueError, YouTubeWriteError) as exc:
        console.print(f"[red]YouTube reconciliation stopped without provider writes:[/red] {exc}")
        raise typer.Exit(code=2) from exc
