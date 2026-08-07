from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.album import (
    AlbumError,
    AlbumManifest,
    acquire_youtube_tracks,
    album_root,
    artwork_plan_path,
    build_album_package,
    build_album_timing,
    build_artwork_plan,
    configure_local_track,
    configure_youtube_track,
    create_album_manifest,
    load_album_manifest,
    load_album_timing,
    manifest_path,
    probe_album_tracks,
    render_album,
    render_path,
    save_album_manifest,
    save_album_timing,
    save_json,
    timing_path,
    verify_album_render,
)
from video_channel_manager.config import get_settings

console = Console()
album_app = typer.Typer(
    no_args_is_help=True, help="Build deterministic local audio/video albums without provider writes."
)


def _paths(album: str) -> tuple[Path, Path]:
    settings = get_settings()
    settings.ensure_runtime_directories()
    root = album_root(settings.data_dir, album)
    return root, manifest_path(settings.data_dir, album)


def _load(album: str) -> tuple[Path, Path, AlbumManifest]:
    root, path = _paths(album)
    if not path.is_file():
        raise AlbumError(f"Album '{album}' does not exist. Run: video-manager album init ...")
    return root, path, load_album_manifest(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AlbumError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AlbumError(f"Expected a JSON object in {path}")
    return payload


@album_app.command("init")
def init_album(
    project: Annotated[str, typer.Option("--project", help="Exact registered project_key")],
    album: Annotated[str, typer.Option("--album", help="Stable album key, e.g. black-man")],
    tracks: Annotated[int, typer.Option("--tracks", min=1, max=99)],
    title: Annotated[str | None, typer.Option("--title", help="Viewer-facing album title")] = None,
) -> None:
    """Create a new local-only album manifest."""

    try:
        root, path = _paths(album)
        if path.exists():
            raise AlbumError(f"Album already exists: {path}")
        manifest = create_album_manifest(
            project_key=project,
            album_key=album,
            total_tracks=tracks,
            display_title=title,
        )
        root.mkdir(parents=True, exist_ok=True)
        (root / "artwork").mkdir(exist_ok=True)
        (root / "cache").mkdir(exist_ok=True)
        (root / "build").mkdir(exist_ok=True)
        manifest = save_album_manifest(path, manifest)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Album init failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(
        f"[green]Album initialized.[/green] {manifest.album_key} | project={manifest.project_key} | "
        f"tracks={manifest.total_tracks} | channel={manifest.expected_channel_id}\n{path}"
    )


@album_app.command("add-youtube")
def add_youtube(
    album: Annotated[str, typer.Option("--album")],
    track: Annotated[int, typer.Option("--track", min=1)],
    video_id: Annotated[str, typer.Option("--video-id", help="Exact 11-character YouTube video ID")],
    title: Annotated[str | None, typer.Option("--title", help="Exact viewer-facing track title")] = None,
) -> None:
    """Bind one album track to one exact YouTube source ID; no network call is made."""

    try:
        _, path, manifest = _load(album)
        updated = configure_youtube_track(manifest, ordinal=track, video_id=video_id, title=title)
        updated = save_album_manifest(path, updated)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Cannot configure YouTube track:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(
        f"[green]Track {track:02d} configured.[/green] video={video_id} | channel={updated.expected_channel_id}"
    )


@album_app.command("add-local")
def add_local(
    album: Annotated[str, typer.Option("--album")],
    track: Annotated[int, typer.Option("--track", min=1)],
    path: Annotated[Path, typer.Option("--path", help="Explicit local master path")],
    title: Annotated[str | None, typer.Option("--title", help="Exact viewer-facing track title")] = None,
) -> None:
    """Bind one track to a local controlled master, including a not-yet-created pending path."""

    try:
        _, manifest_file, manifest = _load(album)
        updated = configure_local_track(manifest, ordinal=track, path=path, title=title)
        updated = save_album_manifest(manifest_file, updated)
        configured = updated.tracks[track - 1]
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Cannot configure local track:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    status = configured.status
    console.print(
        f"[green]Track {track:02d} configured as local master.[/green] status={status}\n{configured.local_path}"
    )
    if status == "pending_local_master":
        console.print("[yellow]The file does not exist yet; this is valid for a planned bonus track.[/yellow]")


@album_app.command("status")
def status(album: Annotated[str, typer.Option("--album")]) -> None:
    """Show the current mixed-source album state."""

    try:
        root, path, manifest = _load(album)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Cannot read album:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    table = Table(title=f"Album {manifest.album_key}")
    table.add_column("#", justify="right")
    table.add_column("Title")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Identity / path")
    for item in manifest.tracks:
        if item.source_kind == "youtube_exact_source":
            identity = item.youtube_video_id or "missing"
        elif item.source_kind == "local_controlled_master":
            identity = item.local_path or "missing"
        else:
            identity = "—"
        duration = f"{item.duration_seconds:.3f}s" if item.duration_seconds is not None else "—"
        table.add_row(
            str(item.ordinal),
            item.title,
            item.source_kind or "empty",
            item.status,
            duration,
            identity,
        )
    console.print(table)
    pending = [item.ordinal for item in manifest.tracks if item.status == "pending_local_master"]
    console.print(f"pending_local_master: {pending}")
    console.print(f"Manifest: {path}")
    console.print(f"Album root: {root}")
    console.print(f"SHA-256: {manifest.manifest_sha256}")


@album_app.command("acquire")
def acquire(
    album: Annotated[str, typer.Option("--album")],
    track: Annotated[
        int | None, typer.Option("--track", min=1, help="Acquire only one configured YouTube track")
    ] = None,
    yt_dlp: Annotated[str, typer.Option("--yt-dlp", help="yt-dlp executable")] = "yt-dlp",
) -> None:
    """Download exact configured YouTube audio sources into the controlled album cache."""

    try:
        root, path, manifest = _load(album)
        updated = acquire_youtube_tracks(manifest, root=root, track_ordinal=track, yt_dlp=yt_dlp)
        updated = save_album_manifest(path, updated)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Album acquisition failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    acquired = [item.ordinal for item in updated.tracks if item.status in {"acquired", "probed"}]
    console.print(f"[green]Acquisition complete.[/green] acquired/probed tracks: {acquired}")


@album_app.command("probe")
def probe(
    album: Annotated[str, typer.Option("--album")],
    track: Annotated[int | None, typer.Option("--track", min=1, help="Probe only one track")] = None,
    ffprobe: Annotated[str, typer.Option("--ffprobe", help="ffprobe executable")] = "ffprobe",
) -> None:
    """Hash and ffprobe every available album audio master without modifying it."""

    try:
        _, path, manifest = _load(album)
        updated = probe_album_tracks(manifest, track_ordinal=track, ffprobe=ffprobe)
        updated = save_album_manifest(path, updated)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Album probe failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    probed = [item.ordinal for item in updated.tracks if item.status == "probed"]
    pending = [item.ordinal for item in updated.tracks if item.status == "pending_local_master"]
    console.print(f"[green]Probe complete.[/green] probed={probed} | pending_local_master={pending}")


@album_app.command("timing")
def timing(
    album: Annotated[str, typer.Option("--album")],
    grid: Annotated[int, typer.Option("--grid", min=1, max=60, help="Align next track to this many seconds")] = 5,
    minimum_gap: Annotated[
        float,
        typer.Option("--minimum-gap", min=0.0, help="Minimum neutral transition gap before advancing the grid"),
    ] = 1.0,
) -> None:
    """Create exact cumulative chapters from probed durations; requires all final masters."""

    try:
        _, _, manifest = _load(album)
        generated = build_album_timing(manifest, grid_seconds=grid, minimum_gap_seconds=minimum_gap)
        path = timing_path(get_settings().data_dir, album)
        save_album_timing(path, generated)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Cannot build album timing:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    table = Table(title="Album timing")
    table.add_column("#")
    table.add_column("Start")
    table.add_column("Duration")
    table.add_column("Gap")
    table.add_column("Title")
    for item in generated.tracks:
        table.add_row(
            str(item.ordinal),
            item.chapter_timestamp,
            f"{item.duration_seconds:.3f}s",
            f"{item.gap_after_seconds:.3f}s",
            item.title,
        )
    console.print(table)
    console.print(f"[green]Timing written:[/green] {path}")


@album_app.command("artwork-plan")
def artwork_plan(
    album: Annotated[str, typer.Option("--album")],
    width: Annotated[int, typer.Option("--width", min=16)] = 1920,
    height: Annotated[int, typer.Option("--height", min=16)] = 1080,
) -> None:
    """Reserve one neutral cover plus one exact active-track artwork state per track."""

    try:
        root, _, manifest = _load(album)
        payload = build_artwork_plan(manifest, width=width, height=height)
        path = artwork_plan_path(get_settings().data_dir, album)
        save_json(path, payload)
        artwork_dir = root / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Cannot build artwork plan:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(
        f"[green]Artwork plan written.[/green] states={len(payload['states'])} "
        f"({manifest.total_tracks} active + neutral)\n{path}\nPlace exact PNG assets in: {artwork_dir}"
    )


@album_app.command("render")
def render(
    album: Annotated[str, typer.Option("--album")],
    ffmpeg: Annotated[str, typer.Option("--ffmpeg", help="ffmpeg executable")] = "ffmpeg",
) -> None:
    """Render a local 16:9 album MP4 from frozen timing, audio masters and artwork states."""

    try:
        root, _, manifest = _load(album)
        timing_manifest = load_album_timing(timing_path(get_settings().data_dir, album), manifest=manifest)
        final = render_album(manifest, timing_manifest, root=root, ffmpeg=ffmpeg)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Album render failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]Album rendered locally.[/green]\n{final}")
    console.print("No YouTube/VK provider write was performed.")


@album_app.command("verify")
def verify(
    album: Annotated[str, typer.Option("--album")],
    ffprobe: Annotated[str, typer.Option("--ffprobe", help="ffprobe executable")] = "ffprobe",
    tolerance: Annotated[float, typer.Option("--tolerance", min=0.0)] = 2.0,
) -> None:
    """Verify final A/V streams, SHA-256 and duration against the timing manifest."""

    try:
        root, _, manifest = _load(album)
        timing_manifest = load_album_timing(timing_path(get_settings().data_dir, album), manifest=manifest)
        final = render_path(get_settings().data_dir, album)
        verification = verify_album_render(
            manifest,
            timing_manifest,
            final_path=final,
            ffprobe=ffprobe,
            duration_tolerance_seconds=tolerance,
        )
        output = root / "build" / "verification.json"
        save_json(output, verification)
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Album verification failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]Album render verified.[/green]\n{output}")


@album_app.command("package")
def package(album: Annotated[str, typer.Option("--album")]) -> None:
    """Create immutable local upload-package artifacts; provider writes remain disabled."""

    try:
        root, _, manifest = _load(album)
        timing_manifest = load_album_timing(timing_path(get_settings().data_dir, album), manifest=manifest)
        verification_path = root / "build" / "verification.json"
        verification = _read_json(verification_path)
        final = render_path(get_settings().data_dir, album)
        payload = build_album_package(manifest, timing_manifest, verification, final_path=final)
        package_dir = root / "package"
        package_json = package_dir / "album-package.json"
        chapters_txt = package_dir / "chapters.txt"
        upload_metadata = package_dir / "upload-metadata.json"
        save_json(package_json, payload)
        chapters = payload.get("chapters")
        if not isinstance(chapters, list) or not all(isinstance(item, str) for item in chapters):
            raise AlbumError("Generated package has invalid chapters")
        _write_text(chapters_txt, "\n".join(chapters) + "\n")
        save_json(
            upload_metadata,
            {
                "schema_name": "video-manager.youtube-album-upload-metadata",
                "schema_version": "1.0",
                "project_key": manifest.project_key,
                "expected_channel_id": manifest.expected_channel_id,
                "title": manifest.display_title,
                "chapters": chapters,
                "final_media_path": payload["final_media_path"],
                "final_media_sha256": payload["final_media_sha256"],
                "provider_write_authorized": False,
            },
        )
    except (AlbumError, ValueError) as exc:
        console.print(f"[red]Album package failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(
        f"[green]Local album package is ready.[/green]\n{package_json}\n{chapters_txt}\n{upload_metadata}\n"
        "Provider upload/playlist execution is intentionally not authorized by this command."
    )


__all__ = ["album_app"]
