from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, cast

import typer

from video_channel_manager.cli._content_io import (
    console,
    load_records,
    print_failures,
    read_json,
    write_json,
)
from video_channel_manager.cli._content_plan_cli_common import (
    optional_string,
    required_string,
)
from video_channel_manager.editorial._content_plan_common import ContentAction
from video_channel_manager.editorial.content_plan import (
    build_content_plan,
    make_content_operation,
    validate_content_plan,
)
from video_channel_manager.editorial.preview import renderer_for


def plan_build_command(
    input_path: Annotated[
        Path,
        typer.Option("--input", "-i", help="Canonical JSON file or directory"),
    ],
    targets_path: Annotated[
        Path,
        typer.Option(
            "--targets",
            help=(
                "Reviewed target manifest with immutable source snapshot "
                "metadata and strictly typed operations containing "
                "content_id/action/target_id/exact-before guards"
            ),
        ),
    ],
    platform: Annotated[str, typer.Option("--platform", "-p")],
    surface: Annotated[str | None, typer.Option("--surface")] = None,
    output: Annotated[
        Path,
        typer.Option("--output", "-o"),
    ] = Path("editorial-content-plan.json"),
) -> None:
    """Build a signed plan from an explicitly typed target manifest."""

    records, errors = load_records(input_path)
    if errors:
        print_failures(errors)
        raise typer.Exit(code=2)
    by_id = {record.content_id: record for record in records}
    try:
        manifest = read_json(targets_path)
        renderer = renderer_for(platform, surface)
        source_snapshot = required_string(
            manifest,
            "source_snapshot",
            context="manifest",
        )
        source_snapshot_sha256 = required_string(
            manifest,
            "source_snapshot_sha256",
            context="manifest",
        )
        source_snapshot_generated_at = required_string(
            manifest,
            "source_snapshot_generated_at",
            context="manifest",
        )
    except ValueError as exc:
        console.print(f"[red]Cannot build plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    raw_operations = manifest.get("operations")
    if not isinstance(raw_operations, list):
        console.print("[red]Target manifest operations must be a list.[/red]")
        raise typer.Exit(code=2)

    operations: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, raw in enumerate(raw_operations):
        context = f"operations[{index}]"
        if not isinstance(raw, dict):
            failures.append(f"{context} must be an object")
            continue
        try:
            content_id = required_string(
                raw,
                "content_id",
                context=context,
            )
            action_value = required_string(
                raw,
                "action",
                context=context,
            )
            if action_value not in {"create", "update"}:
                raise ValueError(f"{context}.action must be create or update")
            target_id = required_string(
                raw,
                "target_id",
                context=context,
            )
            expected_before_text = optional_string(
                raw,
                "expected_before_text",
                context=context,
            )
            expected_revision = optional_string(
                raw,
                "expected_revision",
                context=context,
            )
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
        print_failures(failures)
        raise typer.Exit(code=2)

    try:
        plan = build_content_plan(
            source_snapshot=source_snapshot,
            source_snapshot_sha256=source_snapshot_sha256,
            source_snapshot_generated_at=source_snapshot_generated_at,
            operations=operations,
        )
    except ValueError as exc:
        console.print(f"[red]Cannot seal plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    plan_errors = validate_content_plan(plan)
    if plan_errors:
        print_failures(plan_errors)
        raise typer.Exit(code=2)
    write_json(output, plan)
    console.print(f"[green]Built signed content plan with {len(operations)} operation(s) → {output}[/green]")
    console.print(f"Plan SHA-256: {plan['plan_sha256']}")


__all__ = ["plan_build_command"]
