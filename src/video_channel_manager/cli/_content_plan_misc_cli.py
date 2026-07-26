from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from video_channel_manager.cli._content_io import (
    console,
    load_records,
    print_failures,
    read_json,
    write_json,
)
from video_channel_manager.editorial.content_plan import validate_content_plan
from video_channel_manager.platforms.vk.editorial_plan import (
    apply_editorial_records_to_vk_catalog_plan,
)


def plan_validate_command(
    plan_path: Annotated[
        Path,
        typer.Argument(help="Signed editorial content plan"),
    ],
) -> None:
    """Validate signatures, exact-before guards, and plan uniqueness."""

    try:
        payload = read_json(plan_path)
    except ValueError as exc:
        console.print(f"[red]Invalid plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    errors = validate_content_plan(payload)
    if errors:
        print_failures(errors)
        raise typer.Exit(code=2)
    console.print(
        f"[green]Valid signed content plan:[/green] "
        f"{payload['plan_sha256']}"
    )


def plan_adapt_vk_catalog_command(
    plan_path: Annotated[
        Path,
        typer.Argument(help="Existing signed VK catalog plan"),
    ],
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Canonical editorial JSON file or directory",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o"),
    ] = Path("vk-catalog-editorial-plan.json"),
    require_all: Annotated[
        bool,
        typer.Option(
            "--require-all/--allow-unmatched",
            help="Require a canonical record for every VK text operation",
        ),
    ] = False,
) -> None:
    """Adapt a guarded VK catalog plan and re-sign it."""

    records, errors = load_records(input_path)
    if errors:
        print_failures(errors)
        raise typer.Exit(code=2)
    try:
        plan = read_json(plan_path)
        adapted = apply_editorial_records_to_vk_catalog_plan(
            plan,
            records,
            require_all_text_operations=require_all,
        )
    except ValueError as exc:
        console.print(f"[red]Cannot adapt VK catalog plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    write_json(output, adapted)
    summary = adapted.get("summary")
    adapted_count = (
        summary.get("editorial_texts_adapted", 0)
        if isinstance(summary, dict)
        else 0
    )
    console.print(
        f"[green]Adapted {adapted_count} VK description operation(s) "
        f"→ {output}[/green]"
    )
    console.print(f"Plan SHA-256: {adapted['plan_sha256']}")


__all__ = ["plan_adapt_vk_catalog_command", "plan_validate_command"]
