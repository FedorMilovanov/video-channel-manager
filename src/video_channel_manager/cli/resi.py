from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from video_channel_manager.resi_handoff import ResiHandoffSpec, default_handoff_path, render_powershell_handoff

console = Console()
resi_app = typer.Typer(no_args_is_help=True, help="Generate local-only Resi/DASH download and trim handoffs.")


@resi_app.callback()
def _callback() -> None:
    """Local-only Resi/DASH handoff commands."""


@resi_app.command("handoff")
def handoff(
    source_url: Annotated[str, typer.Argument(help="Absolute DASH .mpd manifest URL")],
    title: Annotated[
        str | None,
        typer.Option("--title", help="Optional media title; defaults to a deterministic source-derived name"),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option("--start", help="Exact trim start, MM:SS[.mmm] or HH:MM:SS[.mmm]"),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option("--end", help="Exact trim end, MM:SS[.mmm] or HH:MM:SS[.mmm]"),
    ] = None,
    encoder: Annotated[
        str,
        typer.Option("--encoder", help="Exact-trim encoder: auto, nvenc, or cpu"),
    ] = "auto",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Generated UTF-8-BOM PowerShell handoff path"),
    ] = None,
) -> None:
    """Write one self-contained PowerShell script for DASH download, optional exact trim, and QC."""

    try:
        spec = ResiHandoffSpec(
            source_url=source_url,
            title=title,
            start=start,
            end=end,
            encoder=encoder.strip().lower(),
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output is None:
        repository_root = Path(__file__).resolve().parents[3]
        output = repository_root / default_handoff_path(spec.safe_title)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_powershell_handoff(spec), encoding="utf-8-sig")

    console.print(f"[green]Resi/DASH handoff ready:[/green] {output.resolve()}")
    console.print(f"Source fingerprint: {spec.source_fingerprint}")
    console.print(f"Media title: {spec.safe_title}")
    console.print("Provider effect: impossible (local-only script generation).")
    console.print("The generated script keeps and hashes the full master, writes source/result receipts, and performs QC.")
    if spec.start is not None and spec.end is not None:
        console.print(
            f"Exact trim: {spec.normalized_start} -> {spec.normalized_end} "
            f"({spec.trim_duration_ffmpeg}, encoder={spec.encoder})."
        )


def run() -> None:
    resi_app()


if __name__ == "__main__":
    run()
