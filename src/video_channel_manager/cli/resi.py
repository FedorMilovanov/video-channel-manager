from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from video_channel_manager.resi_handoff import ResiHandoffSpec, default_handoff_path, render_powershell_handoff
from video_channel_manager.resi_watch import (
    ResiWatchAmbiguous,
    ResiWatchTimeout,
    create_audio_samples,
    default_sample_dir,
    keep_system_awake,
    watch_for_new_manifest,
)

console = Console()
resi_app = typer.Typer(no_args_is_help=True, help="Local-only Resi/DASH capture, preflight, download, and trim tools.")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


@resi_app.callback()
def _callback() -> None:
    """Local-only Resi/DASH capture, language preflight, and handoff commands."""


@resi_app.command("watch")
def watch(
    page_url: Annotated[str, typer.Argument(help="Exact live page to observe read-only")],
    known_manifest: Annotated[
        str | None,
        typer.Option("--known-manifest", help="Last known Resi manifest to ignore as the baseline"),
    ] = None,
    compare_page: Annotated[
        str | None,
        typer.Option("--compare-page", help="Optional comparison page, e.g. the contemporaneous English player"),
    ] = None,
    timeout_seconds: Annotated[
        float,
        typer.Option("--timeout-seconds", min=1, help="Finite overall watch timeout"),
    ] = 10800,
    poll_seconds: Annotated[
        float,
        typer.Option("--poll-seconds", min=1, help="Delay between bounded page probes"),
    ] = 30,
    probe_wait_seconds: Annotated[
        float,
        typer.Option("--probe-wait-seconds", min=1, help="Network observation time per page probe"),
    ] = 12,
    latest_txt: Annotated[
        Path | None,
        typer.Option("--latest-txt", help="Simple latest-manifest text output"),
    ] = None,
    capture_json: Annotated[
        Path | None,
        typer.Option("--capture-json", help="Detailed capture/player evidence JSON"),
    ] = None,
    state: Annotated[
        Path | None,
        typer.Option("--state", help="Durable watcher state path"),
    ] = None,
) -> None:
    """Watch a live page for a new Resi manifest without starting a full download."""

    repository_root = _repository_root()
    operator_output = repository_root / "operator-output"
    latest_txt = latest_txt or operator_output / "latest-resi-manifest.txt"
    capture_json = capture_json or operator_output / "latest-resi-manifest.json"
    state = state or operator_output / "resi-watch-state.json"

    try:
        with keep_system_awake():
            payload = watch_for_new_manifest(
                page_url,
                known_manifest=known_manifest,
                compare_page=compare_page,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
                probe_wait_seconds=probe_wait_seconds,
                latest_txt=latest_txt,
                latest_json=capture_json,
                state_path=state,
            )
    except (ValueError, RuntimeError, OSError, ResiWatchTimeout, ResiWatchAmbiguous) as exc:
        console.print(f"[red]Resi watch failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except KeyboardInterrupt as exc:
        console.print("[yellow]Resi watch stopped by operator.[/yellow]")
        raise typer.Exit(code=130) from exc

    target = payload["target"]
    console.print(f"[green]NEW RESI MANIFEST CAPTURED:[/green] {target['manifest_url']}")
    if target.get("player_id"):
        console.print(f"Resi player id: {target['player_id']}")
    console.print(f"Capture evidence: {capture_json.resolve()}")
    console.print(f"Latest manifest: {latest_txt.resolve()}")
    console.print("Language claim: UNVERIFIED. Run `video-manager resi sample` before any multi-GB FULL download.")
    console.print("Provider effect: impossible. Full download dispatched: false.")


@resi_app.command("sample")
def sample(
    source_url: Annotated[str, typer.Argument(help="Captured DASH .mpd manifest URL")],
    at: Annotated[
        list[str] | None,
        typer.Option("--at", help="Sample point; repeat for multiple MM:SS/HH:MM:SS positions"),
    ] = None,
    duration_seconds: Annotated[
        int,
        typer.Option("--duration-seconds", min=1, max=300, help="Duration of each audio-only sample"),
    ] = 45,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Sample directory; defaults under operator-output"),
    ] = None,
) -> None:
    """Create bounded audio-only samples for operator language verification before FULL download."""

    points = at or ["30:00", "50:00", "70:00", "90:00"]
    repository_root = _repository_root()
    output_dir = output_dir or default_sample_dir(repository_root, source_url)
    try:
        outputs = create_audio_samples(
            source_url,
            points=points,
            duration_seconds=duration_seconds,
            output_dir=output_dir,
        )
    except (ValueError, RuntimeError) as exc:
        console.print(f"[red]Resi sample failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(f"[green]Language preflight samples ready:[/green] {output_dir.resolve()}")
    for output in outputs:
        console.print(str(output.resolve()))
    console.print("Language claim remains UNVERIFIED until the operator listens to sermon speech samples.")
    console.print("No FULL master was downloaded by this command.")


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
        repository_root = _repository_root()
        output = repository_root / default_handoff_path(spec.safe_title)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_powershell_handoff(spec), encoding="utf-8-sig")

    console.print(f"[green]Resi/DASH handoff ready:[/green] {output.resolve()}")
    console.print(f"Source fingerprint: {spec.source_fingerprint}")
    console.print(f"Media title: {spec.safe_title}")
    console.print("Provider effect: impossible (local-only script generation).")
    console.print(
        "The generated script keeps and hashes the full master, writes source/result receipts, and performs QC."
    )
    if spec.start is not None and spec.end is not None:
        console.print(
            f"Exact trim: {spec.normalized_start} -> {spec.normalized_end} "
            f"({spec.trim_duration_ffmpeg}, encoder={spec.encoder})."
        )


def run() -> None:
    resi_app()


if __name__ == "__main__":
    run()
