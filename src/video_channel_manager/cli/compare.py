from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from video_channel_manager.application.comparison_plans import (
    build_disabled_collection_plan,
    build_disabled_transfer_plan,
    render_detailed_comparison_markdown,
    summarize_placements,
)
from video_channel_manager.application.cross_platform import compare_audit_packages
from video_channel_manager.exchange.audit_package import AuditPackage

compare_app = typer.Typer(no_args_is_help=True, help="Read-only comparison of exported AuditPackage snapshots.")
console = Console()


def _read_audit(path: Path) -> AuditPackage:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return AuditPackage.model_validate(payload)


@compare_app.command("snapshots")
def compare_snapshots(
    source: Annotated[Path, typer.Argument(help="Source AuditPackage JSON")],
    target: Annotated[Path, typer.Argument(help="Target AuditPackage JSON")],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("data/reports"),
    basename: Annotated[str, typer.Option("--basename")] = "cross-platform-comparison",
    min_score: Annotated[float, typer.Option("--min-score")] = 0.65,
    max_duration_delta: Annotated[int, typer.Option("--max-duration-delta")] = 3,
) -> None:
    """Compare two snapshots without changing either platform."""

    try:
        source_audit = _read_audit(source)
        target_audit = _read_audit(target)
        comparison = compare_audit_packages(
            source_audit,
            target_audit,
            min_score=min_score,
            max_duration_delta_seconds=max_duration_delta,
        )
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        console.print(f"[red]Comparison failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"
    markdown_path = output_dir / f"{basename}.md"
    json_path.write_text(comparison.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_detailed_comparison_markdown(comparison), encoding="utf-8")

    placements = summarize_placements(comparison)
    table = Table(title="Cross-platform snapshot comparison")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Source videos", str(len(source_audit.videos)))
    table.add_row("Target videos", str(len(target_audit.videos)))
    table.add_row("Matched", str(len(comparison.matches)))
    table.add_row("Missing on target", str(len(comparison.missing_on_target)))
    table.add_row("Extra on target", str(len(comparison.extra_on_target)))
    table.add_row("Ambiguous matches", str(comparison.ambiguous_match_count))
    table.add_row("Missing target collections", str(comparison.missing_collection_count))
    table.add_row("Missing placements in existing collections", str(placements.existing_collection_placements))
    table.add_row("Placements after collection creation", str(placements.pending_collection_placements))
    table.add_row("Total required placements", str(placements.total_placements))
    console.print(table)
    console.print(f"[green]JSON report → {json_path}[/green]")
    console.print(f"[green]Markdown report → {markdown_path}[/green]")


@compare_app.command("plans")
def compare_plans(
    source: Annotated[Path, typer.Argument(help="Source AuditPackage JSON")],
    target: Annotated[Path, typer.Argument(help="Target AuditPackage JSON")],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("data/plans"),
    basename: Annotated[str, typer.Option("--basename")] = "cross-platform",
    min_score: Annotated[float, typer.Option("--min-score")] = 0.65,
    max_duration_delta: Annotated[int, typer.Option("--max-duration-delta")] = 3,
) -> None:
    """Generate disabled review plans; never execute remote writes."""

    try:
        source_audit = _read_audit(source)
        target_audit = _read_audit(target)
        comparison = compare_audit_packages(
            source_audit,
            target_audit,
            min_score=min_score,
            max_duration_delta_seconds=max_duration_delta,
        )
        transfer_plan = build_disabled_transfer_plan(source_audit, target_audit, comparison)
        collection_plan = build_disabled_collection_plan(target_audit, comparison)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError, KeyError) as exc:
        console.print(f"[red]Plan generation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    transfer_path = output_dir / f"{basename}-transfer-full-length.disabled.json"
    collection_path = output_dir / f"{basename}-organize-vk-albums.disabled.json"
    transfer_path.write_text(transfer_plan.model_dump_json(indent=2), encoding="utf-8")
    collection_path.write_text(collection_plan.model_dump_json(indent=2), encoding="utf-8")

    create_count = sum(item.operation == "create_collection" for item in collection_plan.operations)
    add_count = sum(item.operation == "add_to_collection" for item in collection_plan.operations)
    table = Table(title="Disabled cross-platform review plans")
    table.add_column("Plan")
    table.add_column("Operations", justify="right")
    table.add_column("Enabled", justify="right")
    table.add_row("Transfer public full-length videos", str(len(transfer_plan.operations)), "0")
    table.add_row(
        f"VK albums ({create_count} create + {add_count} placements)", str(len(collection_plan.operations)), "0"
    )
    console.print(table)
    console.print("[yellow]All generated operations are disabled. No remote write method was called.[/yellow]")
    console.print(f"[green]Transfer plan → {transfer_path}[/green]")
    console.print(f"[green]Collection plan → {collection_path}[/green]")
