from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from video_channel_manager.cli._content_io import (
    console,
    load_records,
    print_failures,
    write_json,
)
from video_channel_manager.editorial.preview import preview_records


def validate_command(
    input_path: Annotated[
        Path,
        typer.Option("--input", "-i", help="Canonical JSON file or directory"),
    ],
) -> None:
    """Validate content records, project identity, evidence, and collection uniqueness."""

    records, failures = load_records(input_path)
    if failures:
        print_failures(failures)
        raise typer.Exit(code=2)
    console.print(f"[green]Validated {len(records)} editorial content record(s).[/green]")


def preview_command(
    input_path: Annotated[
        Path,
        typer.Option("--input", "-i", help="Canonical JSON file or directory"),
    ],
    platform: Annotated[
        str,
        typer.Option("--platform", "-p", help="youtube or vk"),
    ],
    surface: Annotated[
        str | None,
        typer.Option(
            "--surface",
            help="comment, description, video_description, post",
        ),
    ] = None,
    json_output: Annotated[
        Path | None,
        typer.Option(
            "--json-output",
            help="Optional machine-readable preview report",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict/--no-strict",
            help="Fail on renderer warnings as well as errors",
        ),
    ] = False,
) -> None:
    """Render one exact-project record or batch without any remote mutation."""

    records, errors = load_records(input_path)
    if errors:
        print_failures(errors)
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
            f"[dim]{item.rendered.character_count} characters · "
            f"{item.rendered.link_count} links · "
            f"variation={item.record.variation_key}[/dim]"
        )
        for issue in item.rendered.issues:
            style = "red" if issue.severity == "error" else "yellow"
            location = f" line {issue.line_number}" if issue.line_number is not None else ""
            console.print(f"[{style}]{issue.severity.upper()} {issue.code}{location}:[/{style}] {issue.message}")
        report_items.append(
            {
                "content_id": item.record.content_id,
                "project_key": item.record.project_key,
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
        project_keys = sorted({item.record.project_key for item in batch.items})
        write_json(
            json_output,
            {
                "project_key": project_keys[0] if len(project_keys) == 1 else None,
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


__all__ = ["preview_command", "validate_command"]
