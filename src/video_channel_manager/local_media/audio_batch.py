from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from video_channel_manager.local_media.quality import sha256_file


class AudioBatchError(RuntimeError):
    """Raised when a local audio artifact cannot be proved safe for planning."""


ArtistPosition = Literal["explicit_only", "first", "last"]
MetadataStatus = Literal["ready", "requires_review"]
AudioItemStatus = Literal["ready", "requires_review", "duplicate_input"]

_BRACKETED_SOURCE_ID = re.compile(r"\s*\[([^\[\]]+)\]\s*$")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class AudioMetadataPolicy:
    """Conservative parsing policy; no filename convention is assumed implicitly."""

    artist_position: ArtistPosition = "explicit_only"
    separators: tuple[str, ...] = (" — ", " – ", " - ")
    minimum_segments: int = 2
    strip_trailing_bracketed_source_id: bool = True

    def __post_init__(self) -> None:
        if self.minimum_segments < 2:
            raise ValueError("minimum_segments must be at least 2")
        if not self.separators or any(not separator for separator in self.separators):
            raise ValueError("separators must contain non-empty values")


@dataclass(frozen=True, slots=True)
class AudioMetadataDecision:
    raw_title: str
    normalized_title: str
    artist: str | None
    title: str | None
    source_id_hint: str | None
    status: MetadataStatus
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AudioProbeReport:
    path: str
    size_bytes: int
    sha256: str
    duration_seconds: float
    format_names: tuple[str, ...]
    audio_stream_count: int
    attached_picture_stream_count: int
    audio_codec: str | None
    bit_rate_bps: int | None
    sample_rate_hz: int | None
    channels: int | None
    tags: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AudioBatchCandidate:
    path: Path
    raw_title: str | None = None
    source_id: str | None = None
    explicit_artist: str | None = None
    explicit_title: str | None = None


@dataclass(frozen=True, slots=True)
class AudioBatchItem:
    operation_id: str
    ordinal: int
    path: str
    source_id: str | None
    artist: str | None
    title: str | None
    size_bytes: int
    sha256: str
    duration_seconds: float
    status: AudioItemStatus
    reason: str
    duplicate_of: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AudioBatchPlan:
    schema_name: str
    schema_version: str
    project_key: str
    transport: Literal["local_only"]
    items: tuple[AudioBatchItem, ...]
    manifest_sha256: str

    @property
    def ready_count(self) -> int:
        return sum(item.status == "ready" for item in self.items)

    @property
    def review_count(self) -> int:
        return sum(item.status == "requires_review" for item in self.items)

    @property
    def duplicate_count(self) -> int:
        return sum(item.status == "duplicate_input" for item in self.items)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "project_key": self.project_key,
            "transport": self.transport,
            "items": [item.to_dict() for item in self.items],
            "counts": {
                "total": len(self.items),
                "ready": self.ready_count,
                "requires_review": self.review_count,
                "duplicate_input": self.duplicate_count,
            },
            "manifest_sha256": self.manifest_sha256,
        }


ProbeAudio = Callable[[Path], AudioProbeReport]


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _WHITESPACE.sub(" ", value.strip())
    return cleaned or None


def _title_and_source_hint(raw_title: str, *, strip_hint: bool) -> tuple[str, str | None]:
    normalized = _WHITESPACE.sub(" ", raw_title.strip())
    if normalized.casefold().endswith(".mp3"):
        normalized = normalized[:-4].rstrip()
    if not strip_hint:
        return normalized, None
    match = _BRACKETED_SOURCE_ID.search(normalized)
    if match is None:
        return normalized, None
    source_id = _clean_text(match.group(1))
    return normalized[: match.start()].rstrip(), source_id


def derive_audio_metadata(
    raw_title: str,
    *,
    explicit_artist: str | None = None,
    explicit_title: str | None = None,
    policy: AudioMetadataPolicy | None = None,
) -> AudioMetadataDecision:
    """Derive exact artist/title fields without guessing an undeclared filename convention."""

    policy = policy or AudioMetadataPolicy()
    artist = _clean_text(explicit_artist)
    title = _clean_text(explicit_title)
    normalized, source_id_hint = _title_and_source_hint(
        raw_title,
        strip_hint=policy.strip_trailing_bracketed_source_id,
    )

    if artist is not None or title is not None:
        if artist is None or title is None:
            return AudioMetadataDecision(
                raw_title=raw_title,
                normalized_title=normalized,
                artist=artist,
                title=title,
                source_id_hint=source_id_hint,
                status="requires_review",
                reason="explicit_artist_and_title_must_be_supplied_together",
            )
        return AudioMetadataDecision(
            raw_title=raw_title,
            normalized_title=normalized,
            artist=artist,
            title=title,
            source_id_hint=source_id_hint,
            status="ready",
            reason="explicit_exact_fields",
        )

    if policy.artist_position == "explicit_only":
        return AudioMetadataDecision(
            raw_title=raw_title,
            normalized_title=normalized,
            artist=None,
            title=None,
            source_id_hint=source_id_hint,
            status="requires_review",
            reason="filename_convention_not_declared",
        )

    present = [separator for separator in policy.separators if separator in normalized]
    if len(present) != 1:
        return AudioMetadataDecision(
            raw_title=raw_title,
            normalized_title=normalized,
            artist=None,
            title=None,
            source_id_hint=source_id_hint,
            status="requires_review",
            reason="missing_or_mixed_metadata_separator",
        )

    separator = present[0]
    segments = [_clean_text(part) for part in normalized.split(separator)]
    if len(segments) < policy.minimum_segments or any(segment is None for segment in segments):
        return AudioMetadataDecision(
            raw_title=raw_title,
            normalized_title=normalized,
            artist=None,
            title=None,
            source_id_hint=source_id_hint,
            status="requires_review",
            reason="filename_does_not_match_declared_metadata_policy",
        )
    exact_segments = [segment for segment in segments if segment is not None]

    if policy.artist_position == "last":
        artist = exact_segments[-1]
        title = separator.join(exact_segments[:-1])
    else:
        artist = exact_segments[0]
        title = separator.join(exact_segments[1:])

    if artist.casefold() == title.casefold():
        return AudioMetadataDecision(
            raw_title=raw_title,
            normalized_title=normalized,
            artist=artist,
            title=title,
            source_id_hint=source_id_hint,
            status="requires_review",
            reason="artist_and_title_are_not_distinct",
        )

    return AudioMetadataDecision(
        raw_title=raw_title,
        normalized_title=normalized,
        artist=artist,
        title=title,
        source_id_hint=source_id_hint,
        status="ready",
        reason=f"declared_{policy.artist_position}_segment_policy",
    )


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


def _normalized_tags(payload: object) -> dict[str, str]:
    if not isinstance(payload, Mapping):
        return {}
    tags: dict[str, str] = {}
    for key, value in payload.items():
        cleaned_key = _clean_text(str(key))
        cleaned_value = _clean_text(str(value))
        if cleaned_key is not None and cleaned_value is not None:
            tags[cleaned_key.casefold()] = cleaned_value
    return dict(sorted(tags.items()))


def probe_audio_file(
    path: Path,
    *,
    ffprobe: str = "ffprobe",
    timeout_seconds: float = 120.0,
    calculate_sha256: bool = True,
    allowed_extensions: frozenset[str] = frozenset({".mp3"}),
) -> AudioProbeReport:
    """Read-only ffprobe inspection for local audio intake; the file is never modified."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise AudioBatchError(f"Audio file does not exist: {resolved}")
    if resolved.suffix.casefold() not in allowed_extensions:
        raise AudioBatchError(f"Audio extension is not allowed: {resolved.suffix or '<none>'}")
    size_bytes = resolved.stat().st_size
    if size_bytes <= 0:
        raise AudioBatchError(f"Audio file is empty: {resolved}")

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration,size,bit_rate:format_tags=artist,title,album,track,date,genre,comment:"
        "stream=index,codec_type,codec_name,sample_rate,channels,bit_rate,duration:stream_disposition=attached_pic",
        "-of",
        "json",
        str(resolved),
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
        raise AudioBatchError(f"Required ffprobe executable was not found: {ffprobe}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioBatchError(f"ffprobe timed out after {timeout_seconds:g}s for {resolved}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip()[-2000:] or "unknown ffprobe error"
        raise AudioBatchError(f"ffprobe failed for {resolved}: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AudioBatchError(f"ffprobe returned invalid JSON for {resolved}") from exc
    if not isinstance(payload, dict):
        raise AudioBatchError(f"ffprobe returned a non-object result for {resolved}")

    raw_streams = payload.get("streams")
    streams = [stream for stream in raw_streams if isinstance(stream, dict)] if isinstance(raw_streams, list) else []
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not audio_streams:
        raise AudioBatchError(f"Audio file has no audio stream: {resolved}")

    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    attached_pictures = [
        stream
        for stream in video_streams
        if isinstance(stream.get("disposition"), dict) and stream["disposition"].get("attached_pic") == 1
    ]
    if len(video_streams) != len(attached_pictures):
        raise AudioBatchError(f"Audio intake found a non-cover video stream: {resolved}")

    raw_format = payload.get("format")
    format_payload = raw_format if isinstance(raw_format, dict) else {}
    duration = _positive_float(format_payload.get("duration"))
    if duration is None:
        duration = max(
            (_positive_float(stream.get("duration")) or 0.0 for stream in audio_streams),
            default=0.0,
        )
    if duration <= 0:
        raise AudioBatchError(f"Audio file has no positive duration: {resolved}")

    audio = audio_streams[0]
    bit_rate = _positive_int(audio.get("bit_rate")) or _positive_int(format_payload.get("bit_rate"))
    format_names = tuple(
        item.strip() for item in str(format_payload.get("format_name") or "").split(",") if item.strip()
    )
    return AudioProbeReport(
        path=str(resolved),
        size_bytes=size_bytes,
        sha256=sha256_file(resolved) if calculate_sha256 else "not-calculated",
        duration_seconds=round(duration, 6),
        format_names=format_names,
        audio_stream_count=len(audio_streams),
        attached_picture_stream_count=len(attached_pictures),
        audio_codec=_clean_text(str(audio.get("codec_name") or "")),
        bit_rate_bps=bit_rate,
        sample_rate_hz=_positive_int(audio.get("sample_rate")),
        channels=_positive_int(audio.get("channels")),
        tags=_normalized_tags(format_payload.get("tags")),
    )


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _operation_id(project_key: str, source_id: str | None, report: AudioProbeReport) -> str:
    identity = source_id or report.sha256
    digest = hashlib.sha256(f"{project_key}\0{identity}\0{report.sha256}".encode()).hexdigest()
    return f"audio-{digest[:20]}"


def build_audio_batch_plan(
    candidates: Iterable[AudioBatchCandidate],
    *,
    project_key: str,
    metadata_policy: AudioMetadataPolicy | None = None,
    probe: ProbeAudio = probe_audio_file,
) -> AudioBatchPlan:
    """Build a deterministic, local-only MP3 plan with exact duplicate and review states."""

    normalized_project_key = _clean_text(project_key)
    if normalized_project_key is None:
        raise ValueError("project_key must be non-empty")
    policy = metadata_policy or AudioMetadataPolicy()
    ordered_candidates = sorted(candidates, key=lambda candidate: str(candidate.path.expanduser().resolve()).casefold())
    if not ordered_candidates:
        raise ValueError("at least one audio candidate is required")

    seen_sha: dict[str, str] = {}
    seen_source: dict[str, str] = {}
    items: list[AudioBatchItem] = []
    for ordinal, candidate in enumerate(ordered_candidates, start=1):
        report = probe(candidate.path)
        raw_title = candidate.raw_title or candidate.path.stem
        metadata = derive_audio_metadata(
            raw_title,
            explicit_artist=candidate.explicit_artist,
            explicit_title=candidate.explicit_title,
            policy=policy,
        )
        source_id = _clean_text(candidate.source_id) or metadata.source_id_hint
        operation_id = _operation_id(normalized_project_key, source_id, report)

        duplicate_of = seen_sha.get(report.sha256)
        duplicate_reason = "duplicate_sha256" if duplicate_of is not None else None
        if source_id is not None and source_id in seen_source:
            duplicate_of = seen_source[source_id]
            duplicate_reason = "duplicate_source_id"

        if duplicate_of is not None:
            status: AudioItemStatus = "duplicate_input"
            reason = duplicate_reason or "duplicate_input"
        elif metadata.status == "requires_review":
            status = "requires_review"
            reason = metadata.reason
        else:
            status = "ready"
            reason = metadata.reason

        item = AudioBatchItem(
            operation_id=operation_id,
            ordinal=ordinal,
            path=report.path,
            source_id=source_id,
            artist=metadata.artist,
            title=metadata.title,
            size_bytes=report.size_bytes,
            sha256=report.sha256,
            duration_seconds=report.duration_seconds,
            status=status,
            reason=reason,
            duplicate_of=duplicate_of,
        )
        items.append(item)
        if duplicate_of is None:
            seen_sha[report.sha256] = operation_id
            if source_id is not None:
                seen_source[source_id] = operation_id

    body = {
        "schema_name": "video-manager.audio-batch-plan",
        "schema_version": "1.0",
        "project_key": normalized_project_key,
        "transport": "local_only",
        "items": [item.to_dict() for item in items],
    }
    manifest_sha256 = f"sha256:{hashlib.sha256(_canonical_json(body)).hexdigest()}"
    return AudioBatchPlan(
        schema_name="video-manager.audio-batch-plan",
        schema_version="1.0",
        project_key=normalized_project_key,
        transport="local_only",
        items=tuple(items),
        manifest_sha256=manifest_sha256,
    )


def chunk_ready_audio_items(
    plan: AudioBatchPlan,
    *,
    max_items: int = 1,
    max_total_bytes: int | None = None,
) -> tuple[tuple[AudioBatchItem, ...], ...]:
    """Split only ready items; default one-at-a-time matches single-writer browser safety."""

    if max_items <= 0:
        raise ValueError("max_items must be positive")
    if max_total_bytes is not None and max_total_bytes <= 0:
        raise ValueError("max_total_bytes must be positive")

    chunks: list[tuple[AudioBatchItem, ...]] = []
    current: list[AudioBatchItem] = []
    current_bytes = 0
    for item in (candidate for candidate in plan.items if candidate.status == "ready"):
        size_would_exceed = (
            max_total_bytes is not None and current and current_bytes + item.size_bytes > max_total_bytes
        )
        if len(current) >= max_items or size_would_exceed:
            chunks.append(tuple(current))
            current = []
            current_bytes = 0
        if max_total_bytes is not None and item.size_bytes > max_total_bytes:
            raise AudioBatchError(f"Ready item exceeds max_total_bytes: {item.operation_id}")
        current.append(item)
        current_bytes += item.size_bytes
    if current:
        chunks.append(tuple(current))
    return tuple(chunks)


__all__ = [
    "AudioBatchCandidate",
    "AudioBatchError",
    "AudioBatchItem",
    "AudioBatchPlan",
    "AudioMetadataDecision",
    "AudioMetadataPolicy",
    "AudioProbeReport",
    "build_audio_batch_plan",
    "chunk_ready_audio_items",
    "derive_audio_metadata",
    "probe_audio_file",
]
