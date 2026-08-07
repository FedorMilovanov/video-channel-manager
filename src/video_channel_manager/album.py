from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS, PROJECT_KEYS
from video_channel_manager.local_media import AudioBatchError, probe_audio_file, probe_media, sha256_file

AlbumSourceKind = Literal["youtube_exact_source", "local_controlled_master"]
AlbumTrackStatus = Literal["empty", "configured", "pending_local_master", "acquired", "probed"]

_ALBUM_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_AUDIO_EXTENSIONS = frozenset({".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm"})


class AlbumError(RuntimeError):
    """Raised when local album state is incomplete, ambiguous, or unsafe."""


class AlbumTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int = Field(ge=1)
    title: str
    source_kind: AlbumSourceKind | None = None
    status: AlbumTrackStatus = "empty"
    youtube_video_id: str | None = None
    expected_channel_id: str | None = None
    source_url: str | None = None
    local_path: str | None = None
    acquired_path: str | None = None
    sha256: str | None = None
    duration_seconds: float | None = Field(default=None, gt=0)
    probe: dict[str, Any] | None = None
    acquisition: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("track title cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_source_contract(self) -> AlbumTrack:
        if self.source_kind is None:
            if self.status != "empty":
                raise ValueError("source-less tracks must remain empty")
            return self
        if self.source_kind == "youtube_exact_source":
            if self.youtube_video_id is None or self.expected_channel_id is None or self.source_url is None:
                raise ValueError("youtube tracks require exact video, channel and source URL")
            if self.local_path is not None:
                raise ValueError("youtube tracks cannot claim a local controlled-master path")
        else:
            if self.local_path is None:
                raise ValueError("local controlled masters require an explicit path")
            if self.youtube_video_id is not None or self.source_url is not None:
                raise ValueError("local controlled masters cannot fabricate a remote YouTube identity")
        return self


class AlbumManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["video-manager.album-manifest"] = "video-manager.album-manifest"
    schema_version: Literal["1.0"] = "1.0"
    project_key: str
    album_key: str
    display_title: str
    expected_channel_id: str
    total_tracks: int = Field(ge=1, le=99)
    tracks: list[AlbumTrack]
    created_at: datetime
    updated_at: datetime
    manifest_sha256: str

    @model_validator(mode="after")
    def validate_album_identity(self) -> AlbumManifest:
        if self.project_key not in PROJECT_KEYS:
            raise ValueError("project_key is not registered")
        expected_channels = PROJECT_CHANNEL_IDS.get(self.project_key, frozenset())
        if self.expected_channel_id not in expected_channels:
            raise ValueError("expected channel does not belong to project_key")
        validate_album_key(self.album_key)
        if len(self.tracks) != self.total_tracks:
            raise ValueError("track count does not match total_tracks")
        ordinals = [track.ordinal for track in self.tracks]
        if ordinals != list(range(1, self.total_tracks + 1)):
            raise ValueError("tracks must be ordered contiguously from 1")
        return self


class AlbumTimingTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    title: str
    start_seconds: float
    duration_seconds: float
    end_seconds: float
    gap_after_seconds: float
    chapter_timestamp: str


class AlbumTimingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["video-manager.album-timing"] = "video-manager.album-timing"
    schema_version: Literal["1.0"] = "1.0"
    album_key: str
    source_manifest_sha256: str
    grid_seconds: int
    minimum_gap_seconds: float
    tracks: list[AlbumTimingTrack]
    total_duration_seconds: float
    timing_sha256: str


def validate_album_key(value: str) -> str:
    normalized = value.strip().lower()
    if not _ALBUM_KEY_RE.fullmatch(normalized):
        raise ValueError("album key must match [a-z0-9][a-z0-9-]{0,63}")
    return normalized


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _manifest_payload_without_digest(manifest: AlbumManifest) -> dict[str, Any]:
    payload = manifest.model_dump(mode="json")
    payload.pop("manifest_sha256", None)
    return payload


def _timing_payload_without_digest(timing: AlbumTimingManifest) -> dict[str, Any]:
    payload = timing.model_dump(mode="json")
    payload.pop("timing_sha256", None)
    return payload


def album_root(data_dir: Path, album_key: str) -> Path:
    return data_dir.expanduser().resolve() / "albums" / validate_album_key(album_key)


def manifest_path(data_dir: Path, album_key: str) -> Path:
    return album_root(data_dir, album_key) / "album.json"


def timing_path(data_dir: Path, album_key: str) -> Path:
    return album_root(data_dir, album_key) / "timing.json"


def artwork_plan_path(data_dir: Path, album_key: str) -> Path:
    return album_root(data_dir, album_key) / "artwork-plan.json"


def render_path(data_dir: Path, album_key: str) -> Path:
    return album_root(data_dir, album_key) / "build" / f"{validate_album_key(album_key)}-album.mp4"


def create_album_manifest(
    *,
    project_key: str,
    album_key: str,
    total_tracks: int,
    display_title: str | None = None,
) -> AlbumManifest:
    normalized_project = project_key.strip()
    if normalized_project not in PROJECT_KEYS:
        raise AlbumError(f"Unknown project_key: {normalized_project}")
    channels = sorted(PROJECT_CHANNEL_IDS[normalized_project])
    if len(channels) != 1:
        raise AlbumError("Album initialization requires exactly one registered YouTube channel")
    normalized_album = validate_album_key(album_key)
    if not 1 <= total_tracks <= 99:
        raise AlbumError("total_tracks must be between 1 and 99")
    now = datetime.now(UTC)
    tracks = [AlbumTrack(ordinal=index, title=f"Track {index:02d}") for index in range(1, total_tracks + 1)]
    manifest = AlbumManifest(
        project_key=normalized_project,
        album_key=normalized_album,
        display_title=(display_title or normalized_album).strip(),
        expected_channel_id=channels[0],
        total_tracks=total_tracks,
        tracks=tracks,
        created_at=now,
        updated_at=now,
        manifest_sha256="sha256:" + "0" * 64,
    )
    return _with_manifest_digest(manifest)


def _with_manifest_digest(manifest: AlbumManifest) -> AlbumManifest:
    digest = _canonical_sha256(_manifest_payload_without_digest(manifest))
    return manifest.model_copy(update={"manifest_sha256": digest})


def save_album_manifest(path: Path, manifest: AlbumManifest) -> AlbumManifest:
    updated = manifest.model_copy(update={"updated_at": datetime.now(UTC)})
    updated = _with_manifest_digest(updated)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(updated.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return updated


def load_album_manifest(path: Path) -> AlbumManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = AlbumManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise AlbumError(f"Cannot read album manifest {path}: {exc}") from exc
    expected = _canonical_sha256(_manifest_payload_without_digest(manifest))
    if manifest.manifest_sha256 != expected:
        raise AlbumError("Album manifest SHA-256 does not match its canonical content")
    return manifest


def _replace_track(manifest: AlbumManifest, replacement: AlbumTrack) -> AlbumManifest:
    tracks = [replacement if item.ordinal == replacement.ordinal else item for item in manifest.tracks]
    return manifest.model_copy(update={"tracks": tracks})


def _track_at(manifest: AlbumManifest, ordinal: int) -> AlbumTrack:
    if not 1 <= ordinal <= manifest.total_tracks:
        raise AlbumError(f"Track {ordinal} is outside 1..{manifest.total_tracks}")
    return manifest.tracks[ordinal - 1]


def configure_youtube_track(
    manifest: AlbumManifest,
    *,
    ordinal: int,
    video_id: str,
    title: str | None = None,
) -> AlbumManifest:
    normalized_id = video_id.strip()
    if not _YOUTUBE_VIDEO_ID_RE.fullmatch(normalized_id):
        raise AlbumError("YouTube video ID must contain exactly 11 URL-safe characters")
    current = _track_at(manifest, ordinal)
    replacement = AlbumTrack(
        ordinal=ordinal,
        title=(title or current.title).strip(),
        source_kind="youtube_exact_source",
        status="configured",
        youtube_video_id=normalized_id,
        expected_channel_id=manifest.expected_channel_id,
        source_url=f"https://www.youtube.com/watch?v={normalized_id}",
    )
    return _replace_track(manifest, replacement)


def configure_local_track(
    manifest: AlbumManifest,
    *,
    ordinal: int,
    path: Path,
    title: str | None = None,
) -> AlbumManifest:
    current = _track_at(manifest, ordinal)
    resolved = path.expanduser().resolve()
    status: AlbumTrackStatus = "configured" if resolved.is_file() else "pending_local_master"
    replacement = AlbumTrack(
        ordinal=ordinal,
        title=(title or current.title).strip(),
        source_kind="local_controlled_master",
        status=status,
        expected_channel_id=manifest.expected_channel_id,
        local_path=str(resolved),
    )
    return _replace_track(manifest, replacement)


def _run(command: list[str], *, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise AlbumError(f"Required executable was not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AlbumError(f"{command[0]} timed out after {timeout_seconds:g}s") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-3000:] or "unknown command failure"
        raise AlbumError(f"{command[0]} failed: {detail}")
    return completed


def acquire_youtube_tracks(
    manifest: AlbumManifest,
    *,
    root: Path,
    track_ordinal: int | None = None,
    yt_dlp: str = "yt-dlp",
) -> AlbumManifest:
    if shutil.which(yt_dlp) is None:
        raise AlbumError(f"Required yt-dlp executable was not found: {yt_dlp}")
    cache = root / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    updated = manifest
    candidates = [
        track
        for track in manifest.tracks
        if track.source_kind == "youtube_exact_source" and (track_ordinal is None or track.ordinal == track_ordinal)
    ]
    if track_ordinal is not None and not candidates:
        raise AlbumError(f"Track {track_ordinal} is not configured as a YouTube source")
    if not candidates:
        raise AlbumError("Album has no configured YouTube tracks to acquire")

    for track in candidates:
        if track.source_url is None or track.youtube_video_id is None or track.expected_channel_id is None:
            raise AlbumError(f"Track {track.ordinal} has incomplete YouTube identity")
        info_completed = _run(
            [yt_dlp, "--no-playlist", "--skip-download", "--dump-single-json", track.source_url],
            timeout_seconds=120.0,
        )
        try:
            info = json.loads(info_completed.stdout)
        except json.JSONDecodeError as exc:
            raise AlbumError(f"yt-dlp returned invalid metadata JSON for track {track.ordinal}") from exc
        if not isinstance(info, dict):
            raise AlbumError(f"yt-dlp metadata for track {track.ordinal} is not an object")
        if str(info.get("id") or "") != track.youtube_video_id:
            raise AlbumError(f"Track {track.ordinal} resolved to a different YouTube video ID")
        if str(info.get("channel_id") or "") != track.expected_channel_id:
            raise AlbumError(f"Track {track.ordinal} resolved outside expected channel {track.expected_channel_id}")

        output_template = cache / f"track-{track.ordinal:02d}-%(id)s.%(ext)s"
        completed = _run(
            [
                yt_dlp,
                "--no-playlist",
                "--no-progress",
                "-f",
                "bestaudio/best",
                "--print",
                "after_move:filepath",
                "-o",
                str(output_template),
                track.source_url,
            ],
            timeout_seconds=1800.0,
        )
        output_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if not output_lines:
            raise AlbumError(f"yt-dlp did not report an authoritative final path for track {track.ordinal}")
        acquired = Path(output_lines[-1]).expanduser().resolve()
        if not acquired.is_file():
            raise AlbumError(f"yt-dlp reported a missing final path for track {track.ordinal}: {acquired}")
        try:
            acquired.relative_to(cache.resolve())
        except ValueError as exc:
            raise AlbumError(f"yt-dlp final path escaped the album cache: {acquired}") from exc
        replacement = track.model_copy(
            update={
                "status": "acquired",
                "acquired_path": str(acquired),
                "sha256": None,
                "duration_seconds": None,
                "probe": None,
                "acquisition": {
                    "method": "yt_dlp",
                    "video_id": track.youtube_video_id,
                    "channel_id": track.expected_channel_id,
                    "authoritative_final_path": str(acquired),
                },
            }
        )
        updated = _replace_track(updated, replacement)
    return updated


def probe_album_tracks(
    manifest: AlbumManifest,
    *,
    track_ordinal: int | None = None,
    ffprobe: str = "ffprobe",
) -> AlbumManifest:
    updated = manifest
    candidates = [track for track in manifest.tracks if track_ordinal is None or track.ordinal == track_ordinal]
    if track_ordinal is not None and not candidates:
        raise AlbumError(f"Unknown track {track_ordinal}")

    for track in candidates:
        if track.source_kind is None:
            continue
        raw_path = track.acquired_path if track.source_kind == "youtube_exact_source" else track.local_path
        if raw_path is None:
            if track.source_kind == "local_controlled_master":
                continue
            raise AlbumError(f"Track {track.ordinal} must be acquired before probing")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            if track.source_kind == "local_controlled_master":
                replacement = track.model_copy(update={"status": "pending_local_master"})
                updated = _replace_track(updated, replacement)
                continue
            raise AlbumError(f"Track {track.ordinal} acquired file is missing: {path}")
        try:
            report = probe_audio_file(path, ffprobe=ffprobe, allowed_extensions=_AUDIO_EXTENSIONS)
        except AudioBatchError as exc:
            raise AlbumError(f"Track {track.ordinal} audio probe failed: {exc}") from exc
        replacement = track.model_copy(
            update={
                "status": "probed",
                "sha256": report.sha256,
                "duration_seconds": report.duration_seconds,
                "probe": report.to_dict(),
            }
        )
        updated = _replace_track(updated, replacement)
    return updated


def _chapter_timestamp(seconds: float) -> str:
    rounded = int(math.floor(seconds + 1e-9))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_album_timing(
    manifest: AlbumManifest,
    *,
    grid_seconds: int,
    minimum_gap_seconds: float = 1.0,
) -> AlbumTimingManifest:
    if grid_seconds < 1 or grid_seconds > 60:
        raise AlbumError("grid_seconds must be between 1 and 60")
    if minimum_gap_seconds < 0 or minimum_gap_seconds >= grid_seconds:
        raise AlbumError("minimum_gap_seconds must be >= 0 and smaller than grid_seconds")
    incomplete = [track.ordinal for track in manifest.tracks if track.duration_seconds is None or track.status != "probed"]
    if incomplete:
        joined = ", ".join(str(item) for item in incomplete)
        raise AlbumError(f"Cannot build final timing until every track is probed; incomplete: {joined}")

    cursor = 0.0
    rows: list[AlbumTimingTrack] = []
    for index, track in enumerate(manifest.tracks):
        duration = track.duration_seconds
        if duration is None:
            raise AlbumError(f"Track {track.ordinal} has no duration")
        start = round(cursor, 6)
        end = round(start + duration, 6)
        gap = 0.0
        if index < len(manifest.tracks) - 1:
            next_grid = math.ceil(end / grid_seconds) * grid_seconds
            if next_grid - end < minimum_gap_seconds:
                next_grid += grid_seconds
            gap = round(next_grid - end, 6)
            cursor = round(next_grid, 6)
        else:
            cursor = end
        rows.append(
            AlbumTimingTrack(
                ordinal=track.ordinal,
                title=track.title,
                start_seconds=start,
                duration_seconds=duration,
                end_seconds=end,
                gap_after_seconds=gap,
                chapter_timestamp=_chapter_timestamp(start),
            )
        )

    timing = AlbumTimingManifest(
        album_key=manifest.album_key,
        source_manifest_sha256=manifest.manifest_sha256,
        grid_seconds=grid_seconds,
        minimum_gap_seconds=minimum_gap_seconds,
        tracks=rows,
        total_duration_seconds=round(cursor, 6),
        timing_sha256="sha256:" + "0" * 64,
    )
    digest = _canonical_sha256(_timing_payload_without_digest(timing))
    return timing.model_copy(update={"timing_sha256": digest})


def save_album_timing(path: Path, timing: AlbumTimingManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(timing.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_album_timing(path: Path, *, manifest: AlbumManifest) -> AlbumTimingManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        timing = AlbumTimingManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise AlbumError(f"Cannot read album timing {path}: {exc}") from exc
    expected = _canonical_sha256(_timing_payload_without_digest(timing))
    if timing.timing_sha256 != expected:
        raise AlbumError("Album timing SHA-256 does not match its canonical content")
    if timing.source_manifest_sha256 != manifest.manifest_sha256:
        raise AlbumError("Timing was built from a different album manifest; rebuild timing")
    return timing


def build_artwork_plan(manifest: AlbumManifest, *, width: int = 1920, height: int = 1080) -> dict[str, Any]:
    if width < 16 or height < 16:
        raise AlbumError("artwork dimensions are too small")
    states: list[dict[str, Any]] = [
        {
            "state": "neutral",
            "active_track": None,
            "filename": "cover-neutral.png",
        }
    ]
    states.extend(
        {
            "state": f"track-{track.ordinal:02d}",
            "active_track": track.ordinal,
            "filename": f"track-{track.ordinal:02d}.png",
        }
        for track in manifest.tracks
    )
    payload: dict[str, Any] = {
        "schema_name": "video-manager.album-artwork-plan",
        "schema_version": "1.0",
        "album_key": manifest.album_key,
        "source_manifest_sha256": manifest.manifest_sha256,
        "width": width,
        "height": height,
        "states": states,
        "tracks": [{"ordinal": track.ordinal, "title": track.title} for track in manifest.tracks],
    }
    payload["artwork_plan_sha256"] = _canonical_sha256(payload)
    return payload


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _ffmpeg_run(command: list[str]) -> None:
    _run(command, timeout_seconds=3600.0)


def render_album(
    manifest: AlbumManifest,
    timing: AlbumTimingManifest,
    *,
    root: Path,
    ffmpeg: str = "ffmpeg",
) -> Path:
    if shutil.which(ffmpeg) is None:
        raise AlbumError(f"Required ffmpeg executable was not found: {ffmpeg}")
    artwork_dir = root / "artwork"
    neutral = artwork_dir / "cover-neutral.png"
    if not neutral.is_file():
        raise AlbumError(f"Missing neutral artwork: {neutral}")
    build_dir = root / "build"
    segments_dir = build_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    concat_entries: list[Path] = []

    timing_by_ordinal = {item.ordinal: item for item in timing.tracks}
    for track in manifest.tracks:
        timing_track = timing_by_ordinal[track.ordinal]
        artwork = artwork_dir / f"track-{track.ordinal:02d}.png"
        if not artwork.is_file():
            raise AlbumError(f"Missing active-track artwork: {artwork}")
        raw_audio = track.acquired_path if track.source_kind == "youtube_exact_source" else track.local_path
        if raw_audio is None:
            raise AlbumError(f"Track {track.ordinal} has no local audio source")
        audio = Path(raw_audio).expanduser().resolve()
        if not audio.is_file():
            raise AlbumError(f"Track {track.ordinal} audio file is missing: {audio}")
        segment = segments_dir / f"track-{track.ordinal:02d}.mp4"
        _ffmpeg_run(
            [
                ffmpeg,
                "-y",
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                str(artwork),
                "-i",
                str(audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-t",
                f"{timing_track.duration_seconds:.6f}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-tune",
                "stillimage",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-c:a",
                "aac",
                "-b:a",
                "320k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(segment),
            ]
        )
        concat_entries.append(segment)

        if timing_track.gap_after_seconds > 0:
            gap = segments_dir / f"gap-{track.ordinal:02d}.mp4"
            _ffmpeg_run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-framerate",
                    "30",
                    "-i",
                    str(neutral),
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=48000:cl=stereo",
                    "-t",
                    f"{timing_track.gap_after_seconds:.6f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-tune",
                    "stillimage",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "30",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "320k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    str(gap),
                ]
            )
            concat_entries.append(gap)

    concat_file = build_dir / "concat.txt"
    concat_file.parent.mkdir(parents=True, exist_ok=True)
    concat_file.write_text(
        "".join(f"file '{str(path.resolve()).replace(chr(39), chr(39) + '\\\\' + chr(39))}'\n" for path in concat_entries),
        encoding="utf-8",
    )
    final_path = render_path(root.parent.parent, manifest.album_key)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg_run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(final_path),
        ]
    )
    if not final_path.is_file():
        raise AlbumError("ffmpeg completed without producing the final album file")
    return final_path


def verify_album_render(
    manifest: AlbumManifest,
    timing: AlbumTimingManifest,
    *,
    final_path: Path,
    ffprobe: str = "ffprobe",
    duration_tolerance_seconds: float = 2.0,
) -> dict[str, Any]:
    if duration_tolerance_seconds < 0:
        raise AlbumError("duration_tolerance_seconds cannot be negative")
    report = probe_media(final_path, ffprobe=ffprobe)
    delta = abs(report.duration_seconds - timing.total_duration_seconds)
    if delta > duration_tolerance_seconds:
        raise AlbumError(
            f"Final duration differs from timing plan by {delta:.3f}s, above tolerance {duration_tolerance_seconds:.3f}s"
        )
    return {
        "schema_name": "video-manager.album-render-verification",
        "schema_version": "1.0",
        "album_key": manifest.album_key,
        "source_manifest_sha256": manifest.manifest_sha256,
        "timing_sha256": timing.timing_sha256,
        "verified": True,
        "duration_delta_seconds": round(delta, 6),
        "media": report.to_dict(),
    }


def build_album_package(
    manifest: AlbumManifest,
    timing: AlbumTimingManifest,
    verification: dict[str, Any],
    *,
    final_path: Path,
) -> dict[str, Any]:
    if verification.get("verified") is not True:
        raise AlbumError("Album package requires a successful render verification")
    chapters = [f"{item.chapter_timestamp} {item.title}" for item in timing.tracks]
    payload: dict[str, Any] = {
        "schema_name": "video-manager.album-package",
        "schema_version": "1.0",
        "project_key": manifest.project_key,
        "album_key": manifest.album_key,
        "display_title": manifest.display_title,
        "expected_channel_id": manifest.expected_channel_id,
        "source_manifest_sha256": manifest.manifest_sha256,
        "timing_sha256": timing.timing_sha256,
        "final_media_path": str(final_path.resolve()),
        "final_media_sha256": sha256_file(final_path),
        "chapters": chapters,
        "provider_write_authorized": False,
    }
    payload["package_sha256"] = _canonical_sha256(payload)
    return payload


__all__ = [
    "AlbumError",
    "AlbumManifest",
    "AlbumTimingManifest",
    "AlbumTrack",
    "acquire_youtube_tracks",
    "album_root",
    "artwork_plan_path",
    "build_album_package",
    "build_album_timing",
    "build_artwork_plan",
    "configure_local_track",
    "configure_youtube_track",
    "create_album_manifest",
    "load_album_manifest",
    "load_album_timing",
    "manifest_path",
    "probe_album_tracks",
    "render_album",
    "render_path",
    "save_album_manifest",
    "save_album_timing",
    "save_json",
    "timing_path",
    "verify_album_render",
]
