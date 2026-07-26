from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.table import Table

from video_channel_manager.cli import _content_legacy as legacy
from video_channel_manager.editorial._content_plan_common import ContentAction, target_state_key
from video_channel_manager.editorial.content_plan import (
    build_content_plan,
    make_content_operation,
    operation_state,
    validate_content_plan,
    validate_preflight_state,
)
from video_channel_manager.editorial.preview import renderer_for


def _required_string(payload: dict[str, Any], key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a nonblank string")
    return value.strip()


def _optional_string(payload: dict[str, Any], key: str, *, context: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context}.{key} must be a string or null")
    return value


def _operation_key(raw: dict[str, Any]) -> str:
    return target_state_key(
        platform=cast(str, raw["platform"]),
        surface=cast(str, raw["surface"]),
        target_id=cast(str, raw["target_id"]),
    )


def plan_build_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Canonical JSON file or directory")],
    targets_path: Annotated[
        Path,
        typer.Option(
            "--targets",
            help=(
                "Reviewed target manifest with immutable source snapshot metadata and strictly typed operations "
                "containing content_id/action/target_id/exact-before guards"
            ),
        ),
    ],
    platform: Annotated[str, typer.Option("--platform", "-p")],
    surface: Annotated[str | None, typer.Option("--surface")] = None,
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("editorial-content-plan.json"),
) -> None:
    """Build a signed plan from an explicitly typed reviewed target manifest."""

    records, errors = legacy._load_records(input_path)
    if errors:
        legacy._print_failures(errors)
        raise typer.Exit(code=2)
    by_id = {record.content_id: record for record in records}
    try:
        manifest = legacy._read_json(targets_path)
        renderer = renderer_for(platform, surface)
        source_snapshot = _required_string(manifest, "source_snapshot", context="manifest")
        source_snapshot_sha256 = _required_string(manifest, "source_snapshot_sha256", context="manifest")
        source_snapshot_generated_at = _required_string(
            manifest,
            "source_snapshot_generated_at",
            context="manifest",
        )
    except ValueError as exc:
        legacy.console.print(f"[red]Cannot build plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    raw_operations = manifest.get("operations")
    if not isinstance(raw_operations, list):
        legacy.console.print("[red]Target manifest operations must be a list.[/red]")
        raise typer.Exit(code=2)

    operations: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, raw in enumerate(raw_operations):
        context = f"operations[{index}]"
        if not isinstance(raw, dict):
            failures.append(f"{context} must be an object")
            continue
        try:
            content_id = _required_string(raw, "content_id", context=context)
            action_value = _required_string(raw, "action", context=context)
            if action_value not in {"create", "update"}:
                raise ValueError(f"{context}.action must be create or update")
            target_id = _required_string(raw, "target_id", context=context)
            expected_before_text = _optional_string(raw, "expected_before_text", context=context)
            expected_revision = _optional_string(raw, "expected_revision", context=context)
            record = by_id.get(content_id)
            if record is None:
                raise ValueError(f"{context} references unknown content_id: {content_id}")
            operation = make_content_operation(
                record=record,
                rendered=renderer.render(record),
                target_id=target_id,
                action=cast(ContentAction, action_value),
                expected_before_text=expected_before_text,
                expected_revision=expected_revision,
            )
        except ValueError as exc:
            failures.append(str(exc))
            continue
        operations.append(operation)
    if failures:
        legacy._print_failures(failures)
        raise typer.Exit(code=2)

    try:
        plan = build_content_plan(
            source_snapshot=source_snapshot,
            source_snapshot_sha256=source_snapshot_sha256,
            source_snapshot_generated_at=source_snapshot_generated_at,
            operations=operations,
        )
    except ValueError as exc:
        legacy.console.print(f"[red]Cannot seal plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    plan_errors = validate_content_plan(plan)
    if plan_errors:
        legacy._print_failures(plan_errors)
        raise typer.Exit(code=2)
    legacy._write_json(output, plan)
    legacy.console.print(f"[green]Built signed content plan with {len(operations)} operation(s) → {output}[/green]")
    legacy.console.print(f"Plan SHA-256: {plan['plan_sha256']}")


def plan_preflight_command(
    plan_path: Annotated[Path, typer.Argument(help="Signed editorial content plan")],
    state_path: Annotated[
        Path,
        typer.Option(
            "--state",
            help=(
                "Fresh read-only state bound to the same snapshot ID, SHA-256, and generation timestamp; "
                "every planned target must have an explicit exists=true/false observation"
            ),
        ),
    ],
    json_output: Annotated[
        Path | None,
        typer.Option("--json-output", help="Optional machine-readable preflight report"),
    ] = None,
) -> None:
    """Fail-closed classification using the exact signed snapshot envelope."""

    try:
        plan = legacy._read_json(plan_path)
        state_payload = legacy._read_json(state_path)
    except ValueError as exc:
        legacy.console.print(f"[red]Preflight input error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    plan_errors = validate_content_plan(plan)
    if plan_errors:
        legacy._print_failures(plan_errors)
        raise typer.Exit(code=2)

    source_snapshot = cast(str, plan["source_snapshot"])
    source_snapshot_sha256 = cast(str, plan["source_snapshot_sha256"])
    source_snapshot_generated_at = cast(str, plan["source_snapshot_generated_at"])
    state_by_key, state_errors = validate_preflight_state(
        state_payload,
        expected_source_snapshot=source_snapshot,
        expected_source_snapshot_sha256=source_snapshot_sha256,
        expected_source_snapshot_generated_at=source_snapshot_generated_at,
    )
    operations = plan.get("operations")
    assert isinstance(operations, list)
    planned_keys = {_operation_key(raw) for raw in operations if isinstance(raw, dict)}
    missing_keys = sorted(planned_keys.difference(state_by_key))
    if missing_keys:
        state_errors.append("state snapshot is incomplete for planned targets: " + ", ".join(missing_keys))
    if state_errors:
        legacy._print_failures(state_errors)
        raise typer.Exit(code=2)

    counts: Counter[str] = Counter()
    report_operations: list[dict[str, Any]] = []
    table = Table(title="Editorial content plan preflight")
    table.add_column("Operation")
    table.add_column("Target")
    table.add_column("State")
    for raw_value in operations:
        assert isinstance(raw_value, dict)
        key = _operation_key(raw_value)
        current = state_by_key[key]
        state = operation_state(
            raw_value,
            target_exists=cast(bool, current["exists"]),
            current_text=cast(str | None, current.get("current_text")),
            current_revision=cast(str | None, current.get("current_revision")),
        )
        counts[state] += 1
        style = "green" if state in {"ready", "already_applied"} else "red"
        table.add_row(cast(str, raw_value["operation_id"]), key, f"[{style}]{state}[/{style}]")
        report_operations.append(
            {
                "operation_id": raw_value["operation_id"],
                "target": key,
                "state": state,
            }
        )
    legacy.console.print(table)
    legacy.console.print(" · ".join(f"{key}={value}" for key, value in sorted(counts.items())))

    if json_output is not None:
        legacy._write_json(
            json_output,
            {
                "plan_sha256": plan["plan_sha256"],
                "source_snapshot": source_snapshot,
                "source_snapshot_sha256": source_snapshot_sha256,
                "source_snapshot_generated_at": source_snapshot_generated_at,
                "counts": dict(sorted(counts.items())),
                "operations": report_operations,
            },
        )
        legacy.console.print(f"[green]Preflight report written to {json_output}[/green]")
    if counts["conflict"]:
        raise typer.Exit(code=2)


__all__ = ["plan_build_command", "plan_preflight_command"]
