"""Operator-only cross-platform source handoff; never a provider writer."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from video_channel_manager.milovi_crosspost_handoff import (
    FROZEN_INDEX_SHA256,
    HandoffError,
    build_handoff,
)

milovi_app = typer.Typer(no_args_is_help=True, help="Milovi Cake exact-source operator workflows.")


@milovi_app.command("crosspost-plan")
def crosspost_plan(
    index: Annotated[Path, typer.Option("--index", help="Frozen owner-local Instagram v5 index.")],
    start: Annotated[str, typer.Option("--start", help="Moscow start date YYYY-MM-DD.")],
    end: Annotated[str, typer.Option("--end", help="Moscow end date YYYY-MM-DD.")],
    output: Annotated[Path, typer.Option("--output", help="Provider-inert JSON handoff.")],
    expected_sha256: Annotated[str, typer.Option("--index-sha256")] = FROZEN_INDEX_SHA256,
) -> None:
    """Prove six-platform media bindings; never upload, post or schedule."""
    try:
        handoff = build_handoff(
            index,
            start_date=date.fromisoformat(start),
            end_date=date.fromisoformat(end),
            expected_index_sha256=expected_sha256,
        )
    except (OSError, ValueError, KeyError, HandoffError) as exc:
        raise typer.BadParameter(f"Crosspost handoff refused: {exc}") from exc
    payload = json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output.exists():
        if output.read_text(encoding="utf-8") != payload:
            raise typer.BadParameter("Output exists with different bytes; no overwrite")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        scratch = output.with_name(output.name + ".tmp")
        if scratch.exists():
            raise typer.BadParameter("Incomplete temporary output exists; no overwrite")
        scratch.write_text(payload, encoding="utf-8")
        scratch.replace(output)
    typer.echo(
        f"MILOVI CROSSPOST HANDOFF: {handoff['source_count']} sources, "
        f"{handoff['destination_count']} platform routes; "
        "PROVIDER WRITES 0; NEW SCHEDULES 0."
    )
