from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated, Any, Callable

import typer
from rich.console import Console

from video_channel_manager.resi_handoff import ResiHandoffSpec, default_handoff_path, render_powershell_handoff
from video_channel_manager.resi_watch import (
    create_audio_samples,
    default_sample_dir,
    keep_system_awake,
    watch_for_new_manifest,
)

console = Console()
resi_app = typer.Typer(no_args_is_help=True, help="Local-only Resi/DASH capture, preflight, download, and trim tools.")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _background_watch_command(
    *,
    page_url: str,
    known_manifest: str | None,
    compare_page: str | None,
    timeout_seconds: float,
    poll_seconds: float,
    probe_wait_seconds: float,
    max_consecutive_probe_errors: int,
    latest_txt: Path,
    capture_json: Path,
    state: Path,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "video_channel_manager.cli.resi",
        "watch",
        page_url,
        "--timeout-seconds",
        str(timeout_seconds),
        "--poll-seconds",
        str(poll_seconds),
        "--probe-wait-seconds",
        str(probe_wait_seconds),
        "--max-consecutive-probe-errors",
        str(max_consecutive_probe_errors),
        "--latest-txt",
        str(latest_txt),
        "--capture-json",
        str(capture_json),
        "--state",
        str(state),
    ]
    if known_manifest:
        command.extend(["--known-manifest", known_manifest])
    if compare_page:
        command.extend(["--compare-page", compare_page])
    return command


def _start_background_watch(
    command: list[str],
    *,
    repository_root: Path,
    log_path: Path,
    pid_path: Path,
    platform_name: str | None = None,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    startup_wait_seconds: float = 1.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    current_platform = os.name if platform_name is None else platform_name
    if current_platform != "nt":
        raise RuntimeError("--background is currently supported only on Windows")
    if startup_wait_seconds < 0:
        raise ValueError("startup_wait_seconds cannot be negative")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = int(getattr(subprocess, "DETACHED_PROCESS", 0)) | int(
        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    with log_path.open("ab") as log_handle:
        process = popen_factory(
            command,
            cwd=repository_root,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        sleeper(startup_wait_seconds)
        return_code = process.poll()
    if return_code is not None:
        pid_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"background watcher exited during startup with code {return_code}; inspect log: {log_path}"
        )
    pid_path.write_text(str(process.pid) + "\n", encoding="utf-8")
    return int(process.pid)


def _render_handoff(spec: ResiHandoffSpec, *, require_single_audio: bool) -> str:
    script = render_powershell_handoff(spec)
    if not require_single_audio:
        return script
    marker = '    Write-Host "Available DASH formats:"'
    if marker not in script:
        raise RuntimeError("Resi handoff renderer changed; single-audio gate insertion point is missing")
    gate = "\n".join(
        [
            '    Write-Host "Verifying source has exactly one audio stream..."',
            "    $SourceAudioProbeJson = (& ffprobe -v error -select_streams a -show_entries stream=index -of json $SourceUrl | Out-String)",
            '    if ($LASTEXITCODE -ne 0) { throw "ffprobe source audio preflight failed" }',
            "    $SourceAudioProbe = $SourceAudioProbeJson | ConvertFrom-Json",
            "    $SourceAudioStreams = @($SourceAudioProbe.streams)",
            '    if ($SourceAudioStreams.Count -ne 1) { throw "Language-confirmed FULL download requires exactly one source audio stream; explicit audio selection is required before download." }',
        ]
    )
    return script.replace(marker, gate + "\n" + marker, 1)


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
    max_consecutive_probe_errors: Annotated[
        int,
        typer.Option(
            "--max-consecutive-probe-errors",
            min=1,
            help="Transient target-page probe errors tolerated before fail-closed abort",
        ),
    ] = 10,
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
    background: Annotated[
        bool,
        typer.Option("--background", help="Windows: detach the supported watcher so the launching shell may close"),
    ] = False,
    background_log: Annotated[
        Path | None,
        typer.Option("--background-log", help="Background watcher stdout/stderr log path"),
    ] = None,
    background_pid: Annotated[
        Path | None,
        typer.Option("--background-pid", help="Advisory last-launched background watcher PID file"),
    ] = None,
) -> None:
    """Watch a live page for a new Resi manifest without starting a full download."""

    repository_root = _repository_root()
    operator_output = repository_root / "operator-output"
    latest_txt = latest_txt or operator_output / "latest-resi-manifest.txt"
    capture_json = capture_json or operator_output / "latest-resi-manifest.json"
    state = state or operator_output / "resi-watch-state.json"
    background_log = background_log or operator_output / "resi-watch-background.log"
    background_pid = background_pid or operator_output / "resi-watch-background.pid"

    if background:
        command = _background_watch_command(
            page_url=page_url,
            known_manifest=known_manifest,
            compare_page=compare_page,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            probe_wait_seconds=probe_wait_seconds,
            max_consecutive_probe_errors=max_consecutive_probe_errors,
            latest_txt=latest_txt,
            capture_json=capture_json,
            state=state,
        )
        try:
            pid = _start_background_watch(
                command,
                repository_root=repository_root,
                log_path=background_log,
                pid_path=background_pid,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            console.print(f"[red]Resi background watch failed to start:[/red] {exc}")
            raise typer.Exit(code=2) from exc
        console.print(f"[green]RESI BACKGROUND WATCH STARTED:[/green] PID {pid}")
        console.print(f"Log: {background_log.resolve()}")
        console.print(f"PID evidence: {background_pid.resolve()}")
        console.print(f"Capture evidence on success: {capture_json.resolve()}")
        console.print("The child survived the startup grace check; PID still does not prove later liveness or capture success.")
        console.print("Provider effect: impossible. Full download dispatched: false.")
        return

    console.print(f"RESI WATCH STARTED: {page_url}")
    console.print(f"State: {state.resolve()}")
    try:
        with keep_system_awake():
            payload = watch_for_new_manifest(
                page_url,
                known_manifest=known_manifest,
                compare_page=compare_page,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
                probe_wait_seconds=probe_wait_seconds,
                max_consecutive_probe_errors=max_consecutive_probe_errors,
                latest_txt=latest_txt,
                latest_json=capture_json,
                state_path=state,
            )
    except (ValueError, RuntimeError, OSError) as exc:
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
    console.print("Audio contract: exactly one source audio stream was verified at sample time.")
    console.print("Language claim remains UNVERIFIED until the operator listens to sermon speech samples.")
    console.print("For language-confirmed FULL download, generate handoff with --require-single-audio.")
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
    require_single_audio: Annotated[
        bool,
        typer.Option(
            "--require-single-audio",
            help="Fail closed before a new remote FULL download unless the source currently exposes exactly one audio stream",
        ),
    ] = False,
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
    try:
        script = _render_handoff(spec, require_single_audio=require_single_audio)
    except RuntimeError as exc:
        console.print(f"[red]Resi handoff generation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    output.write_text(script, encoding="utf-8-sig")

    console.print(f"[green]Resi/DASH handoff ready:[/green] {output.resolve()}")
    console.print(f"Source fingerprint: {spec.source_fingerprint}")
    console.print(f"Media title: {spec.safe_title}")
    console.print(f"Require single source audio before new FULL download: {str(require_single_audio).lower()}")
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
