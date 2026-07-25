from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class MediaQualityError(RuntimeError):
    """Raised when a transfer file cannot be proved to contain usable audio and video."""


@dataclass(frozen=True, slots=True)
class MediaQualityReport:
    path: str
    size_bytes: int
    sha256: str
    duration_seconds: float
    format_names: tuple[str, ...]
    video_stream_count: int
    audio_stream_count: int
    video_codec: str | None
    audio_codec: str | None
    width: int | None
    height: int | None
    sample_rate_hz: int | None
    audio_channels: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _positive_float(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _first_stream(streams: list[dict[str, Any]], codec_type: str) -> dict[str, Any] | None:
    return next((stream for stream in streams if stream.get("codec_type") == codec_type), None)


def probe_media(
    path: Path,
    *,
    ffprobe: str = "ffprobe",
    timeout_seconds: float = 120.0,
    calculate_sha256: bool = True,
) -> MediaQualityReport:
    """Probe a local transfer file with ffprobe and enforce basic A/V invariants."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if not path.is_file():
        raise MediaQualityError(f"Media file does not exist: {path}")
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise MediaQualityError(f"Media file is empty: {path}")

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration,size:stream=index,codec_type,codec_name,width,height,sample_rate,channels,duration",
        "-of",
        "json",
        str(path),
    ]
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
        raise MediaQualityError(f"Required ffprobe executable was not found: {ffprobe}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaQualityError(f"ffprobe timed out after {timeout_seconds:g}s for {path}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip()[-2000:] or "unknown ffprobe error"
        raise MediaQualityError(f"ffprobe failed for {path}: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MediaQualityError(f"ffprobe returned invalid JSON for {path}") from exc
    if not isinstance(payload, dict):
        raise MediaQualityError(f"ffprobe returned a non-object result for {path}")

    raw_streams = payload.get("streams")
    streams = [stream for stream in raw_streams if isinstance(stream, dict)] if isinstance(raw_streams, list) else []
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not video_streams:
        raise MediaQualityError(f"Media file has no video stream: {path}")
    if not audio_streams:
        raise MediaQualityError(f"Media file has no audio stream: {path}")

    raw_format = payload.get("format")
    format_payload = raw_format if isinstance(raw_format, dict) else {}
    duration = _positive_float(format_payload.get("duration"))
    if duration is None:
        duration = max(
            (_positive_float(stream.get("duration")) or 0.0 for stream in streams),
            default=0.0,
        )
    if duration <= 0:
        raise MediaQualityError(f"Media file has no positive duration: {path}")

    video = _first_stream(streams, "video") or {}
    audio = _first_stream(streams, "audio") or {}
    format_names = tuple(
        item.strip() for item in str(format_payload.get("format_name") or "").split(",") if item.strip()
    )
    return MediaQualityReport(
        path=str(path.resolve()),
        size_bytes=size_bytes,
        sha256=sha256_file(path) if calculate_sha256 else "not-calculated",
        duration_seconds=round(duration, 6),
        format_names=format_names,
        video_stream_count=len(video_streams),
        audio_stream_count=len(audio_streams),
        video_codec=str(video.get("codec_name") or "").strip() or None,
        audio_codec=str(audio.get("codec_name") or "").strip() or None,
        width=_positive_int(video.get("width")),
        height=_positive_int(video.get("height")),
        sample_rate_hz=_positive_int(audio.get("sample_rate")),
        audio_channels=_positive_int(audio.get("channels")),
    )


__all__ = ["MediaQualityError", "MediaQualityReport", "probe_media", "sha256_file"]
