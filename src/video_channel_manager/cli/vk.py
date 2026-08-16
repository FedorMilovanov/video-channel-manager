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
from video_channel_manager.platforms.vk.clips_owner_probe import (
    VK_OWNER_CLIPS_PROBE_API_VERSION,
    build_vk_owner_clips_probe_snapshot,
)

console = Console()
vk_app = typer.Typer(
    no_args_is_help=True,
    help="VK read-only inventory plus explicitly guarded provider mutation workflows.",
)


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
    console.print(
        "This token supports read-only inventory and explicitly guarded mutation commands; "
        "provider writes require command-specific confirmation."
    )
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
            help="Exact known Clip remote ID to probe in the bounded search; repeat for multiple probes",
        ),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Export a read-only VK short-filter discovery snapshot for one canonical project."""

    settings = get_settings()
    try:
        _, client = _components(account)
        with console.status("Reading bounded VK short-filter candidates..."):
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
        f"[green]Exported VK short-filter discovery snapshot -> {output}[/green]\n"
        f"Project: {snapshot['project_key']} | Community: {community} | Owner: {owner_id} | "
        f"Candidates: {coverage['search_candidate_count']} | Clips detected: {coverage['clip_count']} | "
        f"Filter noise: {coverage['filter_noise_count']} | Provider writes: 0"
    )
    if coverage["required_remote_ids_returned_non_clip"]:
        console.print(
            "[yellow]Coverage probe warning: known Clip ID(s) were returned by search but not as type=short_video.[/yellow]"
        )
    if coverage["required_remote_ids_missing_from_search"]:
        console.print(
            "[yellow]Coverage probe warning: known Clip ID(s) were absent from the bounded short-filter search.[/yellow]"
        )
    console.print(
        "[yellow]This snapshot does not prove the complete native Clips surface; absence is not upload evidence.[/yellow]"
    )


@vk_app.command("clips-owner-probe")
def clips_owner_probe(
    project: Annotated[str, typer.Option("--project", help="Canonical project key")],
    community: Annotated[int, typer.Option("--community", "-c", help="Exact positive VK community ID")],
    owner_id: Annotated[int, typer.Option("--owner-id", help="Exact negative VK owner ID")],
    account: Annotated[str, typer.Option("--account", "-a", help="Local VK credential alias")] = "default",
    require_remote_id: Annotated[
        list[str] | None,
        typer.Option(
            "--require-remote-id",
            help="Exact known Clip remote ID to probe in the owner endpoint; repeat for multiple probes",
        ),
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Export an experimental read-only owner Clips endpoint probe for one canonical project."""

    settings = get_settings()
    try:
        store, _ = _components(account)
        client = VkApiClient(
            token_store=store,
            account_alias=account,
            api_version=VK_OWNER_CLIPS_PROBE_API_VERSION,
        )
        with console.status("Probing VK Video owner Clips surface without provider writes..."):
            snapshot = build_vk_owner_clips_probe_snapshot(
                client,
                project_key=project,
                community_id=community,
                owner_id=owner_id,
                required_remote_ids=require_remote_id or (),
            )
        if output is None:
            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            output = settings.data_dir / "exports" / f"vk-owner-clips-probe-{project}-{community}-{timestamp}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    except (VkAccountNotFoundError, OSError, ValueError, VkApiError) as exc:
        console.print(f"[red]VK owner Clips probe failed before evidence export:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    probe = snapshot["provider_probe"]
    coverage = snapshot["coverage"]
    console.print(
        f"[green]Exported VK owner Clips experimental probe -> {output}[/green]\n"
        f"Project: {snapshot['project_key']} | Community: {community} | Owner: {owner_id} | "
        f"Endpoint status: {probe['status']} | Provider total: {probe['provider_reported_total']} | "
        f"Retrieved: {probe['retrieved_raw_item_count']} | Native Clips: {coverage['clip_count']} | "
        "Provider writes: 0"
    )
    if probe["status"] != "ok":
        console.print(
            "[yellow]The undocumented owner endpoint returned an error; the JSON still preserves the read-only evidence.[/yellow]"
        )
    if coverage["required_remote_ids_missing_from_probe"]:
        console.print(
            "[yellow]Coverage warning: known Clip ID(s) were absent from this experimental endpoint response.[/yellow]"
        )
    console.print(
        "[yellow]Do not derive upload/delete actions from this probe until it is reconciled against independently observed wall Clips.[/yellow]"
    )


@vk_app.command("milovi-323-rollout")
def milovi_323_rollout(
    execute: Annotated[str, typer.Option("--execute", help="Exact Issue #323 execution confirmation")],
    output: Annotated[Path, typer.Option("--output", help="Exact rollout result JSON path")],
    journal: Annotated[Path, typer.Option("--journal", help="Exact durable rollout journal path")],
    work_dir: Annotated[Path, typer.Option("--work-dir", help="Exact source-freeze/work directory")],
    verify_timeout: Annotated[
        int,
        typer.Option("--verify-timeout", min=60, max=7200, help="Seconds to recover each exact native Clip"),
    ] = 1800,
) -> None:
    """Run the exact Issue #323 native-Clip canary/batch and immediate-wall rollout."""

    from video_channel_manager.platforms.vk.milovi_native_clip_rollout import run_issue_323_rollout

    try:
        result = run_issue_323_rollout(
            confirmation=execute,
            output_path=output,
            journal_path=journal,
            work_dir=work_dir,
            verify_timeout_seconds=verify_timeout,
        )
    except Exception as exc:
        console.print(f"[red]Milovi Issue #323 rollout stopped:[/red] {exc}")
        console.print(f"[yellow]Structured evidence: {output}[/yellow]")
        raise typer.Exit(code=3) from exc

    console.print(
        f"[green]Milovi Issue #323 rollout status: {result['status']}[/green]\n"
        f"Result: {output} | Canary verified: {result['canary_verified']} | "
        f"Postponed authorized: {result['postponed_wall_authorized']}"
    )


@vk_app.command("milovi-323-status")
def milovi_323_status(
    output: Annotated[
        Path,
        typer.Option("--output", help="Read-only Issue #323 status evidence JSON path"),
    ] = Path("operator-output/milovi-cake-issue-323-readonly-status.json"),
    journal: Annotated[
        Path,
        typer.Option("--journal", help="Existing durable Issue #323 rollout journal path"),
    ] = Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"),
    schedule: Annotated[
        Path,
        typer.Option("--schedule", help="Existing frozen Issue #323 wall schedule path"),
    ] = Path("data/vk/milovi-cake/issue-323-daily-wall-schedule.json"),
    prepared_manifest: Annotated[
        Path,
        typer.Option("--prepared-manifest", help="Existing reviewed prepared-source metadata manifest path"),
    ] = Path("operator-output/milovi-cake-issue-323-work/prepared-sources.json"),
) -> None:
    """Reconcile Milovi Issue #323 live state without provider mutation authority."""

    from video_channel_manager.platforms.vk.milovi_issue323_status_probe import (
        MiloviStatusProbeBlocked,
        run_issue_323_status_probe,
    )

    try:
        result = run_issue_323_status_probe(
            output_path=output,
            journal_path=journal,
            schedule_path=schedule,
            prepared_manifest_path=prepared_manifest,
        )
    except (MiloviStatusProbeBlocked, OSError, ValueError) as exc:
        console.print(f"[red]STOP: {type(exc).__name__}: {exc}[/red]")
        raise typer.Exit(code=3) from exc

    console.print(
        f"[green]Milovi #323 read-only status: {result['status']}[/green] | "
        f"next={result['first_action_source_id']}:{result['first_safe_next_action']} | "
        f"provider-writes=0 | result={output}"
    )


@vk_app.command("milovi-323-continue")
def milovi_323_continue(
    promotion_spec: Annotated[
        Path,
        typer.Option("--promotion-spec", help="Exact reviewed 12x2 PromotionSpec JSON path"),
    ],
    promotion_journal: Annotated[
        Path,
        typer.Option("--promotion-journal", help="Durable promotion operation journal JSON path"),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Canonical read-only continuation plan/evidence JSON path"),
    ] = Path("operator-output/milovi-cake-issue-323-continue-preview.json"),
    status_output: Annotated[
        Path,
        typer.Option("--status-output", help="Fresh read-only provider observation JSON path"),
    ] = Path("operator-output/milovi-cake-issue-323-readonly-status.json"),
    journal: Annotated[
        Path,
        typer.Option("--journal", help="Existing durable Issue #323 rollout journal path"),
    ] = Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"),
    schedule: Annotated[
        Path,
        typer.Option("--schedule", help="Existing frozen Issue #323 wall schedule path"),
    ] = Path("data/vk/milovi-cake/issue-323-daily-wall-schedule.json"),
    prepared_manifest: Annotated[
        Path,
        typer.Option("--prepared-manifest", help="Existing reviewed prepared-source metadata manifest path"),
    ] = Path("operator-output/milovi-cake-issue-323-work/prepared-sources.json"),
    confirm_journal_init: Annotated[
        str | None,
        typer.Option(
            "--confirm-journal-init",
            help="Exact local-journal initialization confirmation; this never authorizes provider mutation",
        ),
    ] = None,
    confirm_preflight_digest: Annotated[
        str | None,
        typer.Option(
            "--confirm-preflight-digest",
            help="Exact fresh preflight sha256 digest confirmation; this never authorizes provider mutation",
        ),
    ] = None,
) -> None:
    """Build or confirm the canonical Issue #323 continuation preflight; execute zero provider writes."""

    from video_channel_manager.platforms.vk.milovi_issue323_continue import run_issue_323_continue_preview
    from video_channel_manager.platforms.vk.milovi_issue323_status_probe import MiloviStatusProbeBlocked

    try:
        result = run_issue_323_continue_preview(
            output_path=output,
            status_output_path=status_output,
            rollout_journal_path=journal,
            schedule_path=schedule,
            prepared_manifest_path=prepared_manifest,
            promotion_spec_path=promotion_spec,
            promotion_journal_path=promotion_journal,
            journal_init_confirmation=confirm_journal_init,
            preflight_digest_confirmation=confirm_preflight_digest,
        )
    except (MiloviStatusProbeBlocked, OSError, ValueError) as exc:
        console.print(f"[red]STOP: {type(exc).__name__}: {exc}[/red]")
        raise typer.Exit(code=3) from exc

    status = str(result["continuation_status"])
    successful_statuses = {
        "ready_for_digest_confirmation",
        "digest_confirmed_provider_execution_not_available",
    }
    color = "green" if status in successful_statuses else "yellow"
    console.print(
        f"[{color}]Milovi #323 continuation: {status}[/{color}] | "
        f"planned-writes={result.get('promotion_preflight', {}).get('expected_provider_writes', 0) if isinstance(result.get('promotion_preflight'), dict) else 0} | "
        f"digest-confirmed={result['preflight_digest_confirmed']} | provider-writes-executed=0 | "
        f"digest={result['promotion_preflight_digest']} | result={output}"
    )
    if status not in successful_statuses:
        raise typer.Exit(code=3)
