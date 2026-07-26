from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.table import Table

from video_channel_manager.cli._content_io import (
    console,
    print_failures,
    read_json,
    write_json,
)
from video_channel_manager.cli._content_plan_cli_common import operation_key
from video_channel_manager.editorial.content_plan import (
    operation_state,
    validate_content_plan,
    validate_preflight_state,
)


def plan_preflight_command(
    plan_path: Annotated[
        Path,
        typer.Argument(help="Signed editorial content plan"),
    ],
    state_path: Annotated[
        Path,
        typer.Option(
            "--state",
            help=(
                "Fresh read-only state bound to the same snapshot ID, "
                "SHA-256, and generation timestamp; every planned target "
                "must have an explicit exists=true/false observation"
            ),
        ),
    ],
    json_output: Annotated[
        Path | None,
        typer.Option(
            "--json-output",
            help="Optional machine-readable preflight report",
        ),
    ] = None,
) -> None:
    """Classify operations against the exact signed snapshot envelope."""

    try:
        plan = read_json(plan_path)
        state_payload = read_json(state_path)
    except ValueError as exc:
        console.print(f"[red]Preflight input error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    plan_errors = validate_content_plan(plan)
    if plan_errors:
        print_failures(plan_errors)
        raise typer.Exit(code=2)

    source_snapshot = cast(str, plan["source_snapshot"])
    source_snapshot_sha256 = cast(str, plan["source_snapshot_sha256"])
    source_snapshot_generated_at = cast(
        str,
        plan["source_snapshot_generated_at"],
    )
    state_by_key, state_errors = validate_preflight_state(
        state_payload,
        expected_source_snapshot=source_snapshot,
        expected_source_snapshot_sha256=source_snapshot_sha256,
        expected_source_snapshot_generated_at=(source_snapshot_generated_at),
    )
    operations = plan.get("operations")
    assert isinstance(operations, list)
    planned_keys = {operation_key(raw) for raw in operations if isinstance(raw, dict)}
    missing_keys = sorted(planned_keys.difference(state_by_key))
    if missing_keys:
        state_errors.append("state snapshot is incomplete for planned targets: " + ", ".join(missing_keys))
    if state_errors:
        print_failures(state_errors)
        raise typer.Exit(code=2)

    counts: Counter[str] = Counter()
    report_operations: list[dict[str, Any]] = []
    table = Table(title="Editorial content plan preflight")
    table.add_column("Operation")
    table.add_column("Target")
    table.add_column("State")
    for raw_value in operations:
        assert isinstance(raw_value, dict)
        key = operation_key(raw_value)
        current = state_by_key[key]
        state = operation_state(
            raw_value,
            target_exists=cast(bool, current["exists"]),
            current_text=cast(
                str | None,
                current.get("current_text"),
            ),
            current_revision=cast(
                str | None,
                current.get("current_revision"),
            ),
        )
        counts[state] += 1
        style = "green" if state in {"ready", "already_applied"} else "red"
        table.add_row(
            cast(str, raw_value["operation_id"]),
            key,
            f"[{style}]{state}[/{style}]",
        )
        report_operations.append(
            {
                "operation_id": raw_value["operation_id"],
                "target": key,
                "state": state,
            }
        )
    console.print(table)
    console.print(" · ".join(f"{key}={value}" for key, value in sorted(counts.items())))

    if json_output is not None:
        write_json(
            json_output,
            {
                "plan_sha256": plan["plan_sha256"],
                "source_snapshot": source_snapshot,
                "source_snapshot_sha256": source_snapshot_sha256,
                "source_snapshot_generated_at": (source_snapshot_generated_at),
                "counts": dict(sorted(counts.items())),
                "operations": report_operations,
            },
        )
        console.print(f"[green]Preflight report written to {json_output}[/green]")
    if counts["conflict"]:
        raise typer.Exit(code=2)


__all__ = ["plan_preflight_command"]
