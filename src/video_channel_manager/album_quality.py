from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager import _album_core as core
from video_channel_manager.local_media import AudioBatchError, probe_audio_file, sha256_file

_AUDIO_EXTENSIONS = frozenset({".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm"})


class QualityMasterEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=1)
    source_identity_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    master_path: str
    master_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    duration_seconds: float = Field(gt=0)
    probe: dict[str, Any]

    @model_validator(mode="after")
    def exact_master_path_is_absolute(self) -> "QualityMasterEntry":
        if not Path(self.master_path).is_absolute():
            raise ValueError("quality master path must be absolute")
        return self


class QualityMasterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["video-manager.album-quality-masters"] = "video-manager.album-quality-masters"
    schema_version: Literal["1.0"] = "1.0"
    project_key: str
    album_key: str
    expected_channel_id: str
    entries: tuple[QualityMasterEntry, ...] = ()
    updated_at: datetime
    quality_master_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def entries_are_unique_and_ordered(self) -> "QualityMasterManifest":
        ordinals = [entry.ordinal for entry in self.entries]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("quality master ordinals must be unique")
        if ordinals != sorted(ordinals):
            raise ValueError("quality master entries must be ordered by ordinal")
        return self


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _manifest_payload_without_digest(manifest: QualityMasterManifest) -> dict[str, Any]:
    payload = manifest.model_dump(mode="json")
    payload.pop("quality_master_sha256", None)
    return payload


def _with_digest(manifest: QualityMasterManifest) -> QualityMasterManifest:
    return manifest.model_copy(update={"quality_master_sha256": _canonical_sha256(_manifest_payload_without_digest(manifest))})


def _verify_manifest_digest(manifest: QualityMasterManifest) -> None:
    expected = _canonical_sha256(_manifest_payload_without_digest(manifest))
    if manifest.quality_master_sha256 != expected:
        raise core.AlbumError("Quality master manifest SHA-256 does not match its canonical content")


def _require_album_identity(manifest: core.AlbumManifest, quality: QualityMasterManifest) -> None:
    if (
        quality.project_key != manifest.project_key
        or quality.album_key != manifest.album_key
        or quality.expected_channel_id != manifest.expected_channel_id
    ):
        raise core.AlbumError("Quality master manifest belongs to a different album/project/channel")


def quality_master_path_from_manifest_path(manifest_path: Path) -> Path:
    return manifest_path.expanduser().resolve().with_name("quality-masters.json")


def quality_master_path(data_dir: Path, album_key: str) -> Path:
    return core.album_root(data_dir, album_key) / "quality-masters.json"


def create_quality_master_manifest(manifest: core.AlbumManifest) -> QualityMasterManifest:
    now = datetime.now(tz=UTC)
    return _with_digest(
        QualityMasterManifest(
            project_key=manifest.project_key,
            album_key=manifest.album_key,
            expected_channel_id=manifest.expected_channel_id,
            updated_at=now,
            quality_master_sha256="sha256:" + "0" * 64,
        )
    )


def load_quality_master_manifest(path: Path, manifest: core.AlbumManifest) -> QualityMasterManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        quality = QualityMasterManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise core.AlbumError(f"Cannot read quality master manifest {path}: {exc}") from exc
    _verify_manifest_digest(quality)
    _require_album_identity(manifest, quality)
    return quality


def load_or_initialize_quality_master_manifest(path: Path, manifest: core.AlbumManifest) -> QualityMasterManifest:
    if path.is_file():
        return load_quality_master_manifest(path, manifest)
    return create_quality_master_manifest(manifest)


def save_quality_master_manifest(path: Path, quality: QualityMasterManifest) -> QualityMasterManifest:
    updated = quality.model_copy(update={"updated_at": datetime.now(tz=UTC)})
    updated = _with_digest(updated)
    validated = QualityMasterManifest.model_validate(updated.model_dump(mode="json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return validated


def _track_source_identity(track: core.AlbumTrack) -> str:
    if track.source_kind is None or track.status != "probed" or track.sha256 is None:
        raise core.AlbumError(f"Track {track.ordinal} must be probed before a quality master can be bound")
    payload = {
        "ordinal": track.ordinal,
        "source_kind": track.source_kind,
        "youtube_video_id": track.youtube_video_id,
        "expected_channel_id": track.expected_channel_id,
        "source_url": track.source_url,
        "local_path": track.local_path,
        "source_sha256": track.sha256,
    }
    return _canonical_sha256(payload)


def bind_quality_master(
    manifest: core.AlbumManifest,
    quality: QualityMasterManifest,
    *,
    ordinal: int,
    path: Path,
    ffprobe: str = "ffprobe",
) -> QualityMasterManifest:
    _verify_manifest_digest(quality)
    _require_album_identity(manifest, quality)
    if not 1 <= ordinal <= manifest.total_tracks:
        raise core.AlbumError(f"Track {ordinal} is outside 1..{manifest.total_tracks}")
    track = manifest.tracks[ordinal - 1]
    source_identity = _track_source_identity(track)
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise core.AlbumError(f"Quality master does not exist: {resolved}")
    try:
        report = probe_audio_file(resolved, ffprobe=ffprobe, allowed_extensions=_AUDIO_EXTENSIONS)
    except AudioBatchError as exc:
        raise core.AlbumError(f"Track {ordinal} quality master probe failed: {exc}") from exc
    if track.sha256 is None:
        raise core.AlbumError(f"Track {ordinal} has no probed source SHA-256")
    replacement = QualityMasterEntry(
        ordinal=ordinal,
        source_identity_sha256=source_identity,
        source_sha256=track.sha256,
        master_path=str(resolved),
        master_sha256=report.sha256,
        duration_seconds=report.duration_seconds,
        probe=report.to_dict(),
    )
    entries = [entry for entry in quality.entries if entry.ordinal != ordinal]
    entries.append(replacement)
    entries.sort(key=lambda entry: entry.ordinal)
    return _with_digest(quality.model_copy(update={"entries": tuple(entries), "updated_at": datetime.now(tz=UTC)}))


def verify_quality_master_entry(
    manifest: core.AlbumManifest,
    entry: QualityMasterEntry,
    *,
    verify_bytes: bool,
) -> Path:
    if not 1 <= entry.ordinal <= manifest.total_tracks:
        raise core.AlbumError(f"Quality master references unknown track {entry.ordinal}")
    track = manifest.tracks[entry.ordinal - 1]
    source_identity = _track_source_identity(track)
    if track.sha256 != entry.source_sha256 or source_identity != entry.source_identity_sha256:
        raise core.AlbumError(f"Track {entry.ordinal} quality master belongs to stale source evidence")
    path = Path(entry.master_path).expanduser().resolve()
    if not path.is_file():
        raise core.AlbumError(f"Track {entry.ordinal} quality master is missing: {path}")
    if verify_bytes and sha256_file(path) != entry.master_sha256:
        raise core.AlbumError(f"Track {entry.ordinal} quality master bytes differ from bound SHA-256")
    return path


def require_complete_quality_masters(
    manifest: core.AlbumManifest,
    quality: QualityMasterManifest,
    *,
    verify_bytes: bool = True,
) -> dict[int, QualityMasterEntry]:
    _verify_manifest_digest(quality)
    _require_album_identity(manifest, quality)
    by_ordinal = {entry.ordinal: entry for entry in quality.entries}
    missing = [track.ordinal for track in manifest.tracks if track.ordinal not in by_ordinal]
    if missing:
        raise core.AlbumError(f"Final timing/render requires a bound quality master for every track; missing: {missing}")
    for track in manifest.tracks:
        verify_quality_master_entry(manifest, by_ordinal[track.ordinal], verify_bytes=verify_bytes)
    return by_ordinal


def manifest_with_quality_master_inputs(
    manifest: core.AlbumManifest,
    quality: QualityMasterManifest,
) -> core.AlbumManifest:
    by_ordinal = require_complete_quality_masters(manifest, quality, verify_bytes=True)
    tracks: list[core.AlbumTrack] = []
    for track in manifest.tracks:
        entry = by_ordinal[track.ordinal]
        updates: dict[str, Any] = {
            "status": "probed",
            "duration_seconds": entry.duration_seconds,
        }
        if track.source_kind == "youtube_exact_source":
            updates["acquired_path"] = entry.master_path
        elif track.source_kind == "local_controlled_master":
            updates["local_path"] = entry.master_path
        else:
            raise core.AlbumError(f"Track {track.ordinal} has no source identity")
        tracks.append(track.model_copy(update=updates))
    return manifest.model_copy(update={"tracks": tracks})


__all__ = [
    "QualityMasterEntry",
    "QualityMasterManifest",
    "bind_quality_master",
    "create_quality_master_manifest",
    "load_or_initialize_quality_master_manifest",
    "load_quality_master_manifest",
    "manifest_with_quality_master_inputs",
    "quality_master_path",
    "quality_master_path_from_manifest_path",
    "require_complete_quality_masters",
    "save_quality_master_manifest",
    "verify_quality_master_entry",
]
