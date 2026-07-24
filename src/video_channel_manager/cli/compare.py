from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from video_channel_manager.application.cross_platform import compare_audit_packages, render_comparison_markdown
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
    markdown_path.write_text(render_comparison_markdown(comparison), encoding="utf-8")

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
    table.add_row("Missing collection placements", str(comparison.missing_placement_count))
    console.print(table)
    console.print(f"[green]JSON report → {json_path}[/green]")
    console.print(f"[green]Markdown report → {markdown_path}[/green]")
