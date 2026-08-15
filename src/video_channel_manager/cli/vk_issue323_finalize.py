from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def milovi_323_finalize(
    execute: Annotated[str, typer.Option("--execute", help="Exact guarded Issue #323 finalizer confirmation")],
    output: Annotated[
        Path,
        typer.Option("--output", help="Finalizer result JSON path"),
    ] = Path("operator-output/milovi-cake-issue-323-finalizer.json"),
    rollout_output: Annotated[
        Path,
        typer.Option("--rollout-output", help="Durable rollout result JSON path"),
    ] = Path("operator-output/milovi-cake-issue-323-token-daily-rollout.json"),
    journal: Annotated[
        Path,
        typer.Option("--journal", help="Existing durable Issue #323 rollout journal path"),
    ] = Path("data/vk/milovi-cake/issue-323-token-daily-rollout-journal.json"),
    finalizer_journal: Annotated[
        Path,
        typer.Option("--finalizer-journal", help="Durable Issue #323 finalizer journal path"),
    ] = Path("data/vk/milovi-cake/issue-323-finalizer-journal.json"),
    schedule: Annotated[
        Path,
        typer.Option("--schedule", help="Existing frozen Issue #323 wall schedule path"),
    ] = Path("data/vk/milovi-cake/issue-323-daily-wall-schedule.json"),
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", help="Reviewed Issue #323 prepared-source work directory"),
    ] = Path("operator-output/milovi-cake-issue-323-work"),
    verify_timeout: Annotated[
        int,
        typer.Option("--verify-timeout", min=60, max=7200, help="Seconds to reconcile each exact native Clip"),
    ] = 7200,
) -> None:
    """Resume exact Issue #323 state, finish scheduled walls, and apply guarded promotion copy."""

    from video_channel_manager.platforms.vk import milovi_issue323_finalize as finalizer

    try:
        result = finalizer.run_issue_323_finalizer(
            confirmation=execute,
            output_path=output,
            rollout_output_path=rollout_output,
            journal_path=journal,
            finalizer_journal_path=finalizer_journal,
            schedule_path=schedule,
            work_dir=work_dir,
            verify_timeout_seconds=verify_timeout,
        )
    except Exception as exc:
        console.print(f"[red]STOP: {type(exc).__name__}: {exc}[/red]")
        console.print(f"[yellow]Structured evidence: {output}[/yellow]")
        raise typer.Exit(code=3) from exc

    console.print(
        f"[green]Milovi #323 finalizer: {result['status']}[/green] | "
        f"browser={result['browser_used']} | result={output}"
    )


def register_issue323_finalize_cli(vk_app: typer.Typer) -> None:
    """Register the guarded Issue #323 mutation route on the canonical VK CLI."""

    vk_app.command("milovi-323-finalize")(milovi_323_finalize)


__all__ = ["milovi_323_finalize", "register_issue323_finalize_cli"]
