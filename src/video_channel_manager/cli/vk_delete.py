from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk import VkAccountNotFoundError, VkApiClient, VkTokenStore
from video_channel_manager.platforms.vk.delete_orchestrator import (
    DeleteEvidence,
    DeleteLedger,
    DeleteOrchestrator,
    DeletePolicy,
    OrchestratorConfig,
    VkDeleteGateway,
)
from video_channel_manager.platforms.vk.lock import local_vk_write_lock

app = typer.Typer(no_args_is_help=True, help="Durable, asynchronous VK video-delete orchestrator.")
console = Console()


def _read_json_or_zip(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".zip":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"JSON root must be an object: {path}")
        return payload
    with zipfile.ZipFile(path) as archive:
        candidates = [
            name for name in archive.namelist() if name.endswith("10-journal.json") or name.endswith("journal.json")
        ]
        if len(candidates) != 1:
            raise ValueError(f"Diagnostic ZIP must contain exactly one journal JSON: {candidates}")
        payload = json.loads(archive.read(candidates[0]).decode("utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("Legacy journal root must be an object")
        return payload


def _available_token_aliases(store: VkTokenStore) -> tuple[str, ...]:
    aliases = {account.alias for account in store.list_accounts() if store.token_exists(account.alias)}
    if store.token_dir.is_dir():
        for token_path in store.token_dir.glob("*.json"):
            try:
                alias = store.validate_alias(token_path.stem)
            except ValueError:
                continue
            if store.token_exists(alias):
                aliases.add(alias)
    return tuple(sorted(aliases))


def _resolve_account_alias(store: VkTokenStore, requested: str) -> str:
    requested = store.validate_alias(requested)
    if store.token_exists(requested):
        return requested
    available = _available_token_aliases(store)
    if requested == "default" and len(available) == 1:
        selected = available[0]
        console.print(
            f"[yellow]VK account 'default' is not stored; using the only available account '{selected}'.[/yellow]"
        )
        return selected
    available_text = ", ".join(available) if available else "none"
    raise VkAccountNotFoundError(
        f"VK account token not found: {requested}. Available stored aliases: {available_text}"
    )


def _print_progress(stage: str, payload: dict[str, object]) -> None:
    details = " ".join(f"{key}={value}" for key, value in payload.items())
    console.print(f"[cyan]VK READ[/cyan] {stage} {details}".rstrip())


def _components(account: str) -> tuple[VkTokenStore, VkApiClient, str]:
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    resolved_account = _resolve_account_alias(store, account)
    http_client = httpx.Client(
        timeout=httpx.Timeout(connect=10.0, read=20.0, write=20.0, pool=10.0),
        follow_redirects=True,
    )
    return (
        store,
        VkApiClient(
            token_store=store,
            account_alias=resolved_account,
            api_version=settings.vk_api_version,
            http_client=http_client,
            max_attempts=2,
        ),
        resolved_account,
    )


def _build(
    *,
    account: str,
    policy_path: Path,
    wall_audit_zip: Path,
    ledger_path: Path,
    legacy_journal_path: Path | None,
) -> tuple[DeleteOrchestrator, str, str]:
    policy = DeletePolicy.from_file(policy_path)
    evidence = DeleteEvidence.from_wall_audit_zip(wall_audit_zip, policy)
    ledger = DeleteLedger(ledger_path)
    _, client, resolved_account = _components(account)
    orchestrator = DeleteOrchestrator(
        policy=policy,
        evidence=evidence,
        ledger=ledger,
        gateway=VkDeleteGateway(client, progress_callback=_print_progress),
        config=OrchestratorConfig(),
    )
    legacy = _read_json_or_zip(legacy_journal_path) if legacy_journal_path is not None else None
    run_id = orchestrator.bootstrap(policy_path=policy_path, legacy_journal=legacy)
    return orchestrator, run_id, resolved_account


def _print_summary(summary: dict[str, Any]) -> None:
    table = Table(title=f"VK delete run {summary['run_id']}")
    table.add_column("State")
    table.add_column("Count", justify="right")
    for state, count in sorted(summary["states"].items()):
        table.add_row(state, str(count))
    table.add_section()
    table.add_row("TOTAL", str(summary["total"]))
    table.add_row("UNRESOLVED", str(summary["unresolved"]))
    table.add_row("RUN", str(summary["status"]))
    console.print(table)
    if summary.get("paused_reason"):
        console.print(f"[yellow]Reason:[/yellow] {summary['paused_reason']}")


@app.command("run")
def run_delete(
    policy: Annotated[Path, typer.Option("--policy", exists=True, dir_okay=False)],
    wall_audit: Annotated[Path, typer.Option("--wall-audit", exists=True, dir_okay=False)],
    account: Annotated[str, typer.Option("--account", "-a")] = "default",
    legacy_journal: Annotated[
        Path | None,
        typer.Option("--legacy-journal", exists=True, dir_okay=False, help="V10 diagnostic ZIP or journal JSON"),
    ] = None,
    ledger: Annotated[Path, typer.Option("--ledger")] = Path("data/vk/delete-orchestrator.db"),
    execute: Annotated[bool, typer.Option("--execute", help="Enable the signed destructive dispatcher")] = False,
    watch_read_only: Annotated[
        bool,
        typer.Option(
            "--watch-read-only",
            help="Keep reconciling accepted legacy operations without enabling new VK writes",
        ),
    ] = False,
    confirm_policy_sha256: Annotated[str | None, typer.Option("--confirm-policy-sha256")] = None,
    confirm_community: Annotated[int | None, typer.Option("--confirm-community")] = None,
    confirm_operations: Annotated[int | None, typer.Option("--confirm-operations")] = None,
    idle_poll_seconds: Annotated[float, typer.Option("--idle-poll-seconds", min=5.0, max=300.0)] = 30.0,
    max_cycles: Annotated[int | None, typer.Option("--max-cycles", hidden=True)] = None,
) -> None:
    """Bootstrap/import once, then reconcile and continue automatically from SQLite."""

    if execute and watch_read_only:
        raise typer.BadParameter("--execute and --watch-read-only are mutually exclusive")
    settings = get_settings()
    settings.ensure_runtime_directories()
    orchestrator, run_id, resolved_account = _build(
        account=account,
        policy_path=policy,
        wall_audit_zip=wall_audit,
        ledger_path=ledger,
        legacy_journal_path=legacy_journal,
    )
    if execute:
        if not settings.allow_destructive_operations:
            raise typer.BadParameter("Set VCM_ALLOW_DESTRUCTIVE_OPERATIONS=true before --execute")
        if confirm_policy_sha256 != orchestrator.policy.policy_sha256:
            raise typer.BadParameter("--confirm-policy-sha256 does not match the signed policy")
        if confirm_community != orchestrator.policy.community_id:
            raise typer.BadParameter("--confirm-community does not match the signed policy")
        if confirm_operations != len(orchestrator.policy.operations):
            raise typer.BadParameter("--confirm-operations does not match the signed policy")
    lock_path = settings.data_dir / "locks" / f"vk-delete-{orchestrator.policy.community_id}.lock"
    try:
        if execute:
            with local_vk_write_lock(
                lock_path,
                account=resolved_account,
                community_id=orchestrator.policy.community_id,
                operation="durable-video-delete-orchestrator",
            ):
                summary = orchestrator.run_forever(
                    run_id,
                    execute=True,
                    continuous=True,
                    idle_poll_seconds=idle_poll_seconds,
                    max_cycles=max_cycles,
                )
        else:
            summary = orchestrator.run_forever(
                run_id,
                execute=False,
                continuous=watch_read_only,
                idle_poll_seconds=idle_poll_seconds,
                max_cycles=max_cycles if watch_read_only else 1,
            )
    except Exception as exc:
        console.print(f"[red]VK delete orchestrator stopped safely:[/red] {exc}")
        _print_summary(orchestrator.ledger.summary(run_id))
        raise typer.Exit(code=2) from exc
    _print_summary(summary)


@app.command("status")
def status(
    policy: Annotated[Path, typer.Option("--policy", exists=True, dir_okay=False)],
    ledger: Annotated[Path, typer.Option("--ledger")] = Path("data/vk/delete-orchestrator.db"),
) -> None:
    """Print durable state without loading evidence or calling VK."""

    policy_model = DeletePolicy.from_file(policy)
    durable_ledger = DeleteLedger(ledger)
    run_id = durable_ledger.initialize_run(policy_model, policy_path=policy)
    _print_summary(durable_ledger.summary(run_id))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
