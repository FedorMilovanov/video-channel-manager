from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from video_channel_manager.cli._content_io import console, write_json
from video_channel_manager.config import get_settings
from video_channel_manager.editorial.instagram_launch_preview import build_instagram_launch_preview
from video_channel_manager.exchange.instagram_content import InstagramLaunchPack


def launch_preview_command(
    pack_path: Annotated[Path, typer.Argument(help="Exact Instagram launch-pack JSON")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict/--no-strict", help="Fail on warnings as well as blocking renderer errors"),
    ] = False,
) -> None:
    """Render an exact launch pack into a provider-impossible preview artifact."""

    try:
        raw = pack_path.read_bytes()
        pack = InstagramLaunchPack.model_validate_json(raw)
        result = build_instagram_launch_preview(
            pack,
            source_pack_sha256=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        )
    except (OSError, ValidationError, ValueError) as exc:
        console.print(f"[red]Instagram launch preview failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if output is None:
        settings = get_settings()
        output = settings.data_dir / "reports" / f"instagram-{pack.project_key}-launch-preview.json"
    write_json(output, result.model_dump(mode="json"))

    counts = result.counts
    console.print(
        f"[green]Built provider-inert Instagram launch preview → {output}[/green]\n"
        f"Project: {pack.project_key} | Total: {counts.total} | Valid: {counts.valid} | "
        f"Blocking renderer errors: {counts.errors} | Warnings: {counts.warnings}"
    )
    if counts.errors or (strict and counts.warnings):
        raise typer.Exit(code=2)


__all__ = ["launch_preview_command"]
