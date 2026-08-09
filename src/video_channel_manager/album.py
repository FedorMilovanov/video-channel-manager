from __future__ import annotations

from pathlib import Path
from typing import Any

from video_channel_manager import album_legacy as _legacy
from video_channel_manager.album_quality import (
    QualityMasterEntry,
    QualityMasterManifest,
    bind_quality_master,
    create_quality_master_manifest,
    load_or_initialize_quality_master_manifest,
    load_quality_master_manifest,
    manifest_with_quality_master_inputs,
    quality_master_path,
    quality_master_path_from_manifest_path,
    require_complete_quality_masters,
    save_quality_master_manifest,
    verify_quality_master_entry,
)

AlbumError = _legacy.AlbumError
AlbumManifest = _legacy.AlbumManifest
AlbumTimingManifest = _legacy.AlbumTimingManifest
AlbumTimingTrack = _legacy.AlbumTimingTrack
AlbumTrack = _legacy.AlbumTrack

acquire_youtube_tracks = _legacy.acquire_youtube_tracks
album_root = _legacy.album_root
artwork_plan_path = _legacy.artwork_plan_path
build_artwork_plan = _legacy.build_artwork_plan
create_album_manifest = _legacy.create_album_manifest
manifest_path = _legacy.manifest_path
probe_album_tracks = _legacy.probe_album_tracks
render_path = _legacy.render_path
save_album_timing = _legacy.save_album_timing
save_json = _legacy.save_json
timing_path = _legacy.timing_path
verify_album_render = _legacy.verify_album_render


def _retitle(track: AlbumTrack, title: str) -> AlbumTrack:
    payload = track.model_dump(mode="python")
    payload["title"] = title
    return AlbumTrack.model_validate(payload)


def configure_youtube_track(
    manifest: AlbumManifest,
    *,
    ordinal: int,
    video_id: str,
    title: str | None = None,
) -> AlbumManifest:
    normalized_id = video_id.strip()
    if not 1 <= ordinal <= manifest.total_tracks:
        raise AlbumError(f"Track {ordinal} is outside 1..{manifest.total_tracks}")
    current = manifest.tracks[ordinal - 1]
    expected_url = f"https://www.youtube.com/watch?v={normalized_id}"
    same_source = (
        current.source_kind == "youtube_exact_source"
        and current.youtube_video_id == normalized_id
        and current.expected_channel_id == manifest.expected_channel_id
        and current.source_url == expected_url
    )
    if not same_source:
        return _legacy.configure_youtube_track(manifest, ordinal=ordinal, video_id=video_id, title=title)
    replacement = _retitle(current, (title or current.title).strip())
    tracks = [replacement if track.ordinal == ordinal else track for track in manifest.tracks]
    return manifest.model_copy(update={"tracks": tracks})


def configure_local_track(
    manifest: AlbumManifest,
    *,
    ordinal: int,
    path: Path,
    title: str | None = None,
) -> AlbumManifest:
    if not 1 <= ordinal <= manifest.total_tracks:
        raise AlbumError(f"Track {ordinal} is outside 1..{manifest.total_tracks}")
    current = manifest.tracks[ordinal - 1]
    resolved = path.expanduser().resolve()
    same_source = current.source_kind == "local_controlled_master" and current.local_path == str(resolved)
    if not same_source:
        return _legacy.configure_local_track(manifest, ordinal=ordinal, path=path, title=title)
    replacement = _retitle(current, (title or current.title).strip())
    tracks = [replacement if track.ordinal == ordinal else track for track in manifest.tracks]
    return manifest.model_copy(update={"tracks": tracks})


def _attach_manifest_path(manifest: AlbumManifest, path: Path) -> AlbumManifest:
    object.__setattr__(manifest, "_manifest_path", str(path.expanduser().resolve()))
    return manifest


def load_album_manifest(path: Path) -> AlbumManifest:
    return _attach_manifest_path(_legacy.load_album_manifest(path), path)


def save_album_manifest(path: Path, manifest: AlbumManifest) -> AlbumManifest:
    return _attach_manifest_path(_legacy.save_album_manifest(path, manifest), path)


def _quality_for_manifest(
    manifest: AlbumManifest,
    quality_masters: QualityMasterManifest | None,
) -> QualityMasterManifest:
    if quality_masters is not None:
        return quality_masters
    raw_manifest_path = getattr(manifest, "_manifest_path", None)
    if not isinstance(raw_manifest_path, str) or not raw_manifest_path:
        raise AlbumError(
            "Quality master provenance is required; pass quality_masters explicitly or load the manifest from disk"
        )
    quality_path = quality_master_path_from_manifest_path(Path(raw_manifest_path))
    if not quality_path.is_file():
        raise AlbumError(
            f"Final timing/render requires an explicit quality master manifest; missing: {quality_path}"
        )
    return load_quality_master_manifest(quality_path, manifest)


def build_album_timing(
    manifest: AlbumManifest,
    *,
    grid_seconds: int,
    minimum_gap_seconds: float = 1.0,
    quality_masters: QualityMasterManifest | None = None,
) -> AlbumTimingManifest:
    quality = _quality_for_manifest(manifest, quality_masters)
    mastered = manifest_with_quality_master_inputs(manifest, quality)
    timing = _legacy.build_album_timing(
        mastered,
        grid_seconds=grid_seconds,
        minimum_gap_seconds=minimum_gap_seconds,
    )
    return timing.model_copy(update={"source_manifest_sha256": manifest.manifest_sha256})


def load_album_timing(path: Path, *, manifest: AlbumManifest) -> AlbumTimingManifest:
    return _legacy.load_album_timing(path, manifest=manifest)


def render_album(
    manifest: AlbumManifest,
    timing: AlbumTimingManifest,
    *,
    root: Path,
    ffmpeg: str = "ffmpeg",
    quality_masters: QualityMasterManifest | None = None,
) -> Path:
    quality = _quality_for_manifest(manifest, quality_masters)
    mastered = manifest_with_quality_master_inputs(manifest, quality)
    return _legacy.render_album(mastered, timing, root=root, ffmpeg=ffmpeg)


def build_album_package(
    manifest: AlbumManifest,
    timing: AlbumTimingManifest,
    verification: dict[str, Any],
    *,
    final_path: Path,
    quality_masters: QualityMasterManifest | None = None,
) -> dict[str, Any]:
    quality = _quality_for_manifest(manifest, quality_masters)
    require_complete_quality_masters(manifest, quality, verify_bytes=True)
    payload = _legacy.build_album_package(manifest, timing, verification, final_path=final_path)
    payload["quality_master_sha256"] = quality.quality_master_sha256
    payload.pop("package_sha256", None)
    payload["package_sha256"] = _legacy._canonical_sha256(payload)
    return payload


__all__ = [
    "AlbumError",
    "AlbumManifest",
    "AlbumTimingManifest",
    "AlbumTimingTrack",
    "AlbumTrack",
    "QualityMasterEntry",
    "QualityMasterManifest",
    "acquire_youtube_tracks",
    "album_root",
    "artwork_plan_path",
    "bind_quality_master",
    "build_album_package",
    "build_album_timing",
    "build_artwork_plan",
    "configure_local_track",
    "configure_youtube_track",
    "create_album_manifest",
    "create_quality_master_manifest",
    "load_album_manifest",
    "load_album_timing",
    "load_or_initialize_quality_master_manifest",
    "load_quality_master_manifest",
    "manifest_path",
    "probe_album_tracks",
    "quality_master_path",
    "quality_master_path_from_manifest_path",
    "render_album",
    "render_path",
    "require_complete_quality_masters",
    "save_album_manifest",
    "save_album_timing",
    "save_json",
    "save_quality_master_manifest",
    "timing_path",
    "verify_album_render",
    "verify_quality_master_entry",
]
