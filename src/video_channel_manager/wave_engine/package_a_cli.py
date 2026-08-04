from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.wave_engine.package_a import (
    PACKAGE_A_SCHEMA_MODELS,
    PackageAError,
    execute_package_a,
    load_package_a_request,
    verify_package_a_outputs,
)


app = typer.Typer(
    no_args_is_help=True,
    help="Run and verify the provider-read-only Package A reconciliation control plane.",
)
console = Console()


def _parse_evaluated_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    normalized = value.strip()
    if normalized != value or not normalized:
        raise typer.BadParameter("--evaluated-at must be a normalized ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise typer.BadParameter("--evaluated-at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise typer.BadParameter("--evaluated-at must include a timezone")
    return parsed.astimezone(UTC)


@app.command("run")
def run_package_a(
    request_path: Annotated[Path, typer.Argument(help="Exact Package A request JSON")],
    input_root: Annotated[Path, typer.Option("--input-root")] = Path("."),
    output_directory: Annotated[Path, typer.Option("--output-directory", "-o")] = Path(
        "data/operator/package-a"
    ),
    evaluated_at: Annotated[str | None, typer.Option("--evaluated-at")] = None,
) -> None:
    """Build immutable reconciliation, recovery decisions, and a static read-only operator board."""

    try:
        request = load_package_a_request(request_path)
        summary = execute_package_a(
            request,
            input_root=input_root,
            output_directory=output_directory,
            evaluated_at=_parse_evaluated_at(evaluated_at),
        )
    except PackageAError as exc:
        console.print(f"[red]Package A rejected:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    table = Table(title="Package A read-only result")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Project", summary.project.project_key)
    table.add_row("Request digest", summary.request_digest)
    table.add_row("Reconciliation digest", summary.reconciliation_digest)
    table.add_row("Recovery digest", summary.recovery_digest)
    table.add_row("Board digest", summary.board_digest)
    table.add_row("Provider queries", "0")
    table.add_row("Provider writes", "0")
    table.add_row("Write plans", "0")
    console.print(table)
    console.print(f"[green]Package A outputs:[/green] {output_directory.resolve()}")


@app.command("verify")
def verify_package_a(
    directory: Annotated[Path, typer.Argument(help="Package A output directory")],
) -> None:
    """Verify immutable Package A output identities and file SHA-256 values."""

    root = directory.resolve()
    try:
        summary = verify_package_a_outputs(
            evidence_path=root / "reconciliation-evidence.json",
            recovery_path=root / "recovery-decisions.json",
            board_path=root / "operator-board.json",
            summary_path=root / "run-summary.json",
        )
    except PackageAError as exc:
        console.print(f"[red]Package A verification failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]Verified Package A run:[/green] {summary.self_digest}")


@app.command("schema")
def export_schema(
    output_directory: Annotated[Path, typer.Option("--output-directory", "-o")] = Path(
        "schemas/generated/package-a"
    ),
) -> None:
    """Export the immutable Package A request, decision, board, and summary schemas."""

    output_directory.mkdir(parents=True, exist_ok=True)
    for model in PACKAGE_A_SCHEMA_MODELS:
        schema_name = str(model.model_fields["schema_name"].default)
        path = output_directory / f"{schema_name}-v1.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    console.print(f"[green]Exported {len(PACKAGE_A_SCHEMA_MODELS)} Package A schemas.[/green]")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
