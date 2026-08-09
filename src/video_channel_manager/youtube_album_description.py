from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from video_channel_manager.editorial._project_profiles import PROJECT_CHANNEL_IDS, PROJECT_KEYS

CHAPTER_MARKER = "[[CHAPTERS_FROM_EXACT_VERIFIED_TIMING]]"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class AlbumDescriptionError(RuntimeError):
    pass


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _package_digest(package: dict[str, Any]) -> str:
    unsigned = dict(package)
    unsigned.pop("package_sha256", None)
    return _canonical_sha256(unsigned)


def _timestamp_seconds(value: str) -> int:
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        if not minutes.isdigit() or not seconds.isdigit():
            raise AlbumDescriptionError(f"Invalid chapter timestamp: {value}")
        minute_value = int(minutes)
        second_value = int(seconds)
        if second_value >= 60:
            raise AlbumDescriptionError(f"Invalid chapter timestamp: {value}")
        return minute_value * 60 + second_value
    if len(parts) == 3:
        hours, minutes, seconds = parts
        if not hours.isdigit() or not minutes.isdigit() or not seconds.isdigit():
            raise AlbumDescriptionError(f"Invalid chapter timestamp: {value}")
        hour_value = int(hours)
        minute_value = int(minutes)
        second_value = int(seconds)
        if minute_value >= 60 or second_value >= 60:
            raise AlbumDescriptionError(f"Invalid chapter timestamp: {value}")
        return hour_value * 3600 + minute_value * 60 + second_value
    raise AlbumDescriptionError(f"Invalid chapter timestamp: {value}")


def validate_album_package(package: dict[str, Any], *, project_key: str) -> None:
    if package.get("schema_name") != "video-manager.album-package" or package.get("schema_version") != "1.0":
        raise AlbumDescriptionError("Unsupported album package schema; rebuild the package from current code.")
    if project_key not in PROJECT_KEYS:
        raise AlbumDescriptionError(f"Unknown project_key: {project_key}")
    if package.get("project_key") != project_key:
        raise AlbumDescriptionError("Album package belongs to a different project.")
    expected_channel = package.get("expected_channel_id")
    if expected_channel not in PROJECT_CHANNEL_IDS.get(project_key, frozenset()):
        raise AlbumDescriptionError("Album package channel does not belong to project_key.")
    if package.get("provider_write_authorized") is not False:
        raise AlbumDescriptionError("Album package must remain provider_write_authorized=false.")

    recorded_digest = package.get("package_sha256")
    if not isinstance(recorded_digest, str) or recorded_digest != _package_digest(package):
        raise AlbumDescriptionError("Album package SHA-256 does not match canonical content.")
    for field in ("final_media_sha256", "quality_master_sha256", "timing_sha256", "source_manifest_sha256"):
        value = package.get(field)
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise AlbumDescriptionError(f"Album package {field} is missing or invalid.")

    chapters = package.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise AlbumDescriptionError("Album package chapters are missing.")
    previous = -1
    for index, chapter in enumerate(chapters):
        if not isinstance(chapter, str) or " " not in chapter:
            raise AlbumDescriptionError(f"Album package chapter {index + 1} is invalid.")
        timestamp, title = chapter.split(" ", 1)
        if not title.strip():
            raise AlbumDescriptionError(f"Album package chapter {index + 1} has a blank title.")
        seconds = _timestamp_seconds(timestamp)
        if index == 0 and seconds != 0:
            raise AlbumDescriptionError("The first album chapter must start at 00:00.")
        if seconds <= previous:
            raise AlbumDescriptionError("Album chapter timestamps must increase strictly.")
        previous = seconds


def render_album_description(body: str, package: dict[str, Any], *, project_key: str) -> str:
    validate_album_package(package, project_key=project_key)
    marker_count = body.count(CHAPTER_MARKER)
    if marker_count != 1:
        raise AlbumDescriptionError(f"Description body must contain exactly one chapter marker; found {marker_count}.")
    chapters = package["chapters"]
    assert isinstance(chapters, list)
    rendered = body.replace(CHAPTER_MARKER, "\n".join(str(item) for item in chapters))
    if CHAPTER_MARKER in rendered:
        raise AlbumDescriptionError("Unresolved chapter marker remains after rendering.")
    return rendered


def render_evidence(*, body_path: Path, package_path: Path, rendered: str, package: dict[str, Any]) -> dict[str, Any]:
    body_bytes = body_path.read_bytes()
    return {
        "schema_name": "video-manager.youtube-album-description-render",
        "schema_version": "1.0",
        "project_key": package["project_key"],
        "source_body_path": str(body_path.resolve()),
        "source_body_sha256": "sha256:" + hashlib.sha256(body_bytes).hexdigest(),
        "album_package_path": str(package_path.resolve()),
        "album_package_sha256": package["package_sha256"],
        "final_media_sha256": package["final_media_sha256"],
        "quality_master_sha256": package["quality_master_sha256"],
        "timing_sha256": package["timing_sha256"],
        "rendered_description_sha256": "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "provider_write_authorized": False,
    }
