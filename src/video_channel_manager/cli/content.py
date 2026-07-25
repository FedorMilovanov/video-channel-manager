from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.editorial.content import (
    EditorialContentRecord,
    parse_content_record,
    validate_content_collection,
    validate_content_record,
)
from video_channel_manager.editorial.content_plan import (
    build_content_plan,
    make_content_operation,
    operation_state,
    validate_content_plan,
)
from video_channel_manager.editorial.preview import preview_records, renderer_for
from video_channel_manager.platforms.vk.editorial_plan import apply_editorial_records_to_vk_catalog_plan

console = Console()
content_app = typer.Typer(
    no_args_is_help=True,
    help="Canonical editorial records, platform previews, and signed plans.",
)
content_plan_app = typer.Typer(no_args_is_help=True, help="Build and preflight signed editorial content plans.")
content_app.add_typer(content_plan_app, name="plan")


def _json_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("*.json"))
    raise ValueError(f"Input path does not exist: {input_path}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_records(input_path: Path) -> tuple[list[EditorialContentRecord], list[str]]:
    records: list[EditorialContentRecord] = []
    errors: list[str] = []
    for path in _json_paths(input_path):
        try:
            records.append(parse_content_record(_read_json(path)))
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
    errors.extend(validate_content_collection(records))
    return records, errors


@content_app.command("validate")
def validate_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Canonical JSON file or directory")],
) -> None:
    """Validate canonical/legacy-v2 records, evidence mapping, and collection uniqueness."""

    paths = _json_paths(input_path)
    failures: list[str] = []
    records: list[EditorialContentRecord] = []
    for path in paths:
        try:
            payload = _read_json(path)
        except ValueError as exc:
            failures.append(str(exc))
            continue
        errors = validate_content_record(payload)
        failures.extend(f"{path}: {error}" for error in errors)
        if not errors:
            records.append(parse_content_record(payload))
    failures.extend(validate_content_collection(records))
    if failures:
        for failure in failures:
            console.print(f"[red]ERROR:[/red] {failure}")
        raise typer.Exit(code=2)
    console.print(f"[green]Validated {len(records)} editorial content record(s).[/green]")


@content_app.command("preview")
def preview_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Canonical JSON file or directory")],
    platform: Annotated[str, typer.Option("--platform", "-p", help="youtube or vk")],
    surface: Annotated[
        str | None, typer.Option("--surface", help="comment, description, video_description, post")
    ] = None,
    json_output: Annotated[
        Path | None, typer.Option("--json-output", help="Optional machine-readable preview report")
    ] = None,
    strict: Annotated[
        bool, typer.Option("--strict/--no-strict", help="Fail on renderer warnings as well as errors")
    ] = False,
) -> None:
    """Render one record or a batch without any remote mutation."""

    records, errors = _load_records(input_path)
    if errors:
        for error in errors:
            console.print(f"[red]ERROR:[/red] {error}")
        raise typer.Exit(code=2)
    try:
        batch = preview_records(records, platform=platform, surface=surface)
    except ValueError as exc:
        console.print(f"[red]Invalid platform preview:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    report_items: list[dict[str, Any]] = []
    for item in batch.items:
        title = f"{item.record.content_id} · {item.rendered.platform}.{item.rendered.surface}"
        console.rule(title)
        console.print(item.rendered.text)
        console.print(
            f"[dim]{item.rendered.character_count} characters · {item.rendered.link_count} links · "
            f"variation={item.record.variation_key}[/dim]"
        )
        for issue in item.rendered.issues:
            style = "red" if issue.severity == "error" else "yellow"
            location = f" line {issue.line_number}" if issue.line_number is not None else ""
            console.print(f"[{style}]{issue.severity.upper()} {issue.code}{location}:[/{style}] {issue.message}")
        report_items.append(
            {
                "content_id": item.record.content_id,
                "variation_key": item.record.variation_key,
                "platform": item.rendered.platform,
                "surface": item.rendered.surface,
                "text": item.rendered.text,
                "character_count": item.rendered.character_count,
                "link_count": item.rendered.link_count,
                "issues": [
                    {
                        "code": issue.code,
                        "severity": issue.severity,
                        "message": issue.message,
                        "line_number": issue.line_number,
                    }
                    for issue in item.rendered.issues
                ],
            }
        )

    for error in batch.errors:
        console.print(f"[red]BATCH ERROR:[/red] {error}")
    if json_output is not None:
        _write_json(
            json_output,
            {
                "platform": platform,
                "surface": surface,
                "items": report_items,
                "batch_errors": list(batch.errors),
            },
        )
        console.print(f"[green]Preview report written to {json_output}[/green]")

    warning_count = sum(1 for item in batch.items for issue in item.rendered.issues if issue.severity == "warning")
    error_count = sum(1 for item in batch.items for issue in item.rendered.issues if issue.severity == "error")
    if batch.errors or error_count or (strict and warning_count):
        raise typer.Exit(code=2)


@content_plan_app.command("build")
def plan_build_command(
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Canonical JSON file or directory")],
    targets_path: Annotated[
        Path,
        typer.Option(
            "--targets",
            help=(
                "Reviewed target manifest with source_snapshot, source_snapshot_generated_at, and operations "
                "containing content_id/action/target_id/exact-before guards"
            ),
        ),
    ],
    platform: Annotated[str, typer.Option("--platform", "-p")],
    surface: Annotated[str | None, typer.Option("--surface")] = None,
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("editorial-content-plan.json"),
) -> None:
    """Build a signed dry-run-first plan from reviewed content and an exact target manifest."""

    records, errors = _load_records(input_path)
    if errors:
        for error in errors:
            console.print(f"[red]ERROR:[/red] {error}")
        raise typer.Exit(code=2)
    by_id = {record.content_id: record for record in records}
    try:
        manifest = _read_json(targets_path)
        renderer = renderer_for(platform, surface)
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
        if not isinstance(raw, dict):
            failures.append(f"operations[{index}] must be an object")
            continue
        content_id = str(raw.get("content_id") or "").strip()
        record = by_id.get(content_id)
        if record is None:
            failures.append(f"operations[{index}] references unknown content_id: {content_id}")
            continue
        rendered = renderer.render(record)
        try:
            operation = make_content_operation(
                record=record,
                rendered=rendered,
                target_id=str(raw.get("target_id") or ""),
                action=str(raw.get("action") or "create"),  # type: ignore[arg-type]
                expected_before_text=(
                    str(raw["expected_before_text"]) if raw.get("expected_before_text") is not None else None
                ),
                expected_revision=str(raw.get("expected_revision") or "").strip() or None,
            )
        except ValueError as exc:
            failures.append(f"operations[{index}]: {exc}")
            continue
        operations.append(operation)
    if failures:
        for failure in failures:
            console.print(f"[red]ERROR:[/red] {failure}")
        raise typer.Exit(code=2)

    try:
        plan = build_content_plan(
            source_snapshot=str(manifest.get("source_snapshot") or ""),
            source_snapshot_generated_at=str(manifest.get("source_snapshot_generated_at") or ""),
            operations=operations,
        )
    except ValueError as exc:
        console.print(f"[red]Cannot seal plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    plan_errors = validate_content_plan(plan)
    if plan_errors:
        for error in plan_errors:
            console.print(f"[red]ERROR:[/red] {error}")
        raise typer.Exit(code=2)
    _write_json(output, plan)
    console.print(f"[green]Built signed content plan with {len(operations)} operation(s) → {output}[/green]")
    console.print(f"Plan SHA-256: {plan['plan_sha256']}")


@content_plan_app.command("validate")
def plan_validate_command(
    plan_path: Annotated[Path, typer.Argument(help="Signed editorial content plan")],
) -> None:
    """Validate plan signatures, exact-before guards, target uniqueness, and rendered deduplication."""

    try:
        payload = _read_json(plan_path)
    except ValueError as exc:
        console.print(f"[red]Invalid plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    errors = validate_content_plan(payload)
    if errors:
        for error in errors:
            console.print(f"[red]ERROR:[/red] {error}")
        raise typer.Exit(code=2)
    console.print(f"[green]Valid signed content plan:[/green] {payload['plan_sha256']}")


@content_plan_app.command("preflight")
def plan_preflight_command(
    plan_path: Annotated[Path, typer.Argument(help="Signed editorial content plan")],
    state_path: Annotated[
        Path,
        typer.Option(
            "--state",
            help="Fresh read-only target state with targets: platform/surface/target_id/current_text/current_revision",
        ),
    ],
) -> None:
    """Classify every operation as ready, already-applied, or conflict without writing."""

    try:
        plan = _read_json(plan_path)
        state_payload = _read_json(state_path)
    except ValueError as exc:
        console.print(f"[red]Preflight input error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    plan_errors = validate_content_plan(plan)
    if plan_errors:
        for error in plan_errors:
            console.print(f"[red]ERROR:[/red] {error}")
        raise typer.Exit(code=2)
    raw_targets = state_payload.get("targets")
    if not isinstance(raw_targets, list):
        console.print("[red]State targets must be a list.[/red]")
        raise typer.Exit(code=2)
    state_by_key: dict[str, dict[str, Any]] = {}
    for raw in raw_targets:
        if not isinstance(raw, dict):
            continue
        key = f"{raw.get('platform')}:{raw.get('surface')}:{raw.get('target_id')}"
        state_by_key[key] = raw

    counts: Counter[str] = Counter()
    table = Table(title="Editorial content plan preflight")
    table.add_column("Operation")
    table.add_column("Target")
    table.add_column("State")
    operations = plan.get("operations")
    assert isinstance(operations, list)
    for raw in operations:
        assert isinstance(raw, dict)
        key = f"{raw.get('platform')}:{raw.get('surface')}:{raw.get('target_id')}"
        current = state_by_key.get(key)
        state = operation_state(
            raw,
            current_text=(
                str(current.get("current_text")) if current and current.get("current_text") is not None else None
            ),
            current_revision=(
                str(current.get("current_revision"))
                if current and current.get("current_revision") is not None
                else None
            ),
        )
        counts[state] += 1
        style = "green" if state in {"ready", "already_applied"} else "red"
        table.add_row(str(raw.get("operation_id")), key, f"[{style}]{state}[/{style}]")
    console.print(table)
    console.print(" · ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    if counts["conflict"]:
        raise typer.Exit(code=2)


@content_plan_app.command("adapt-vk-catalog")
def plan_adapt_vk_catalog_command(
    plan_path: Annotated[Path, typer.Argument(help="Existing signed VK catalog plan")],
    input_path: Annotated[Path, typer.Option("--input", "-i", help="Canonical editorial JSON file or directory")],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("vk-catalog-editorial-plan.json"),
    require_all: Annotated[
        bool,
        typer.Option("--require-all/--allow-unmatched", help="Require a canonical record for every VK text operation"),
    ] = False,
) -> None:
    """Adapt an existing guarded VK catalog plan with canonical VK descriptions and re-sign it."""

    records, errors = _load_records(input_path)
    if errors:
        for error in errors:
            console.print(f"[red]ERROR:[/red] {error}")
        raise typer.Exit(code=2)
    try:
        plan = _read_json(plan_path)
        adapted = apply_editorial_records_to_vk_catalog_plan(
            plan,
            records,
            require_all_text_operations=require_all,
        )
    except ValueError as exc:
        console.print(f"[red]Cannot adapt VK catalog plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    _write_json(output, adapted)
    summary = adapted.get("summary")
    adapted_count = summary.get("editorial_texts_adapted", 0) if isinstance(summary, dict) else 0
    console.print(f"[green]Adapted {adapted_count} VK description operation(s) → {output}[/green]")
    console.print(f"Plan SHA-256: {adapted['plan_sha256']}")


__all__ = ["content_app"]
