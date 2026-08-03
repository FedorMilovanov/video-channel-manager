from __future__ import annotations

from collections import Counter
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
from video_channel_manager.editorial._project_profiles import PROJECT_KEYS
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
                "Reviewed target manifest with exact project_key, immutable source snapshot "
                "metadata, and one strictly typed operation per content record"
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
    """Build one project-bound signed plan with exact content coverage."""

    try:
        manifest = read_json(targets_path)
        project_key = required_string(
            manifest,
            "project_key",
            context="manifest",
        )
        if project_key not in PROJECT_KEYS:
            raise ValueError(f"manifest.project_key must be one registered project: {project_key}")
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

    records, errors = load_records(input_path, expected_project_key=project_key)
    if errors:
        print_failures(errors)
        raise typer.Exit(code=2)
    if not records:
        console.print("[red]Cannot build plan:[/red] input contains no valid content records")
        raise typer.Exit(code=2)
    by_id = {record.content_id: record for record in records}

    raw_operations = manifest.get("operations")
    if not isinstance(raw_operations, list):
        console.print("[red]Target manifest operations must be a list.[/red]")
        raise typer.Exit(code=2)

    operations: list[dict[str, Any]] = []
    failures: list[str] = []
    requested_content_ids: list[str] = []
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
            requested_content_ids.append(content_id)
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

    duplicate_content_ids = sorted(
        content_id for content_id, count in Counter(requested_content_ids).items() if content_id and count > 1
    )
    if duplicate_content_ids:
        failures.append(f"target manifest repeats content_id: {', '.join(duplicate_content_ids)}")
    requested_set = set(requested_content_ids)
    loaded_set = set(by_id)
    missing = sorted(loaded_set - requested_set)
    foreign = sorted(requested_set - loaded_set)
    if missing:
        failures.append(f"target manifest is missing content_id operations: {', '.join(missing)}")
    if foreign:
        failures.append(f"target manifest contains foreign content_id operations: {', '.join(foreign)}")
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
    if plan.get("project_key") != project_key:
        console.print(
            f"[red]Cannot seal plan:[/red] operation project {plan.get('project_key')} "
            f"does not match manifest project {project_key}"
        )
        raise typer.Exit(code=2)
    plan_errors = validate_content_plan(plan)
    if plan_errors:
        print_failures(plan_errors)
        raise typer.Exit(code=2)
    write_json(output, plan)
    console.print(
        f"[green]Built project-bound signed content plan with {len(operations)} operation(s) → {output}[/green]"
    )
    console.print(f"Project: {project_key}")
    console.print(f"Plan SHA-256: {plan['plan_sha256']}")


__all__ = ["plan_build_command"]
