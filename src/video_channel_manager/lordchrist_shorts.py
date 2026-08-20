from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from video_channel_manager.editorial.youtube_surface_classification import classify_youtube_surface
from video_channel_manager.exchange.audit_package import AuditPackage
from video_channel_manager.telegram_channel_profile import TelegramChannelProfile, load_channel_profile
from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue
from video_channel_manager.telegram_multichannel_video import render_video_payload

PROJECT_KEY = "lord-god-strength"
YOUTUBE_CHANNEL_ID = "UCeSJsC6go2c9pdJCuUI1BYA"
YOUTUBE_OAUTH_ALIAS = "fedor-milovanov"
TELEGRAM_CHANNEL_USERNAME = "@lordchrist"
TELEGRAM_PROFILE_PATH = "content/telegram/channels/lordchrist.json"
MAX_TELEGRAM_VIDEO_BYTES = 50_000_000
TRANSPORT_BUDGET_BYTES = 46_000_000
MAX_SHORT_DURATION_SECONDS = 180.0
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_SLOT_LOCAL_TIME = "18:17"
AUDIO_BITRATE_BPS = 128_000
MIN_VIDEO_BITRATE_BPS = 600_000
MAX_VIDEO_BITRATE_BPS = 4_000_000
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
_TRAILING_SHORTS_TAGS_RE = re.compile(
    r"(?:\s+#(?:shorts?|youtube(?:shorts?)?|ютубшортс)\b)+\s*$",
    flags=re.IGNORECASE,
)

ProbeRunner = Callable[[Path], dict[str, Any]]
TranscodeRunner = Callable[[list[str]], None]
ModelT = TypeVar("ModelT", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LordChristShortsPolicy(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-policy"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    youtube_oauth_alias: Literal["fedor-milovanov"]
    telegram_channel_username: Literal["@lordchrist"]
    telegram_profile_path: Literal["content/telegram/channels/lordchrist.json"]
    owner_media_sources: tuple[Literal["google_takeout", "local_master"], ...]
    automated_youtube_download_allowed: Literal[False]
    telegram_provider_mutation_allowed: Literal[False]
    telegram_stories_enabled: Literal[False]
    timezone: Literal["Europe/Moscow"]
    slot_local_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    daily_short_limit: Literal[1]
    min_gap_from_editorial_hours: int = Field(ge=4, le=12)
    order: Literal["oldest_first"]
    max_video_bytes: Literal[50_000_000]
    max_duration_seconds: Literal[180]

    @model_validator(mode="after")
    def validate_policy(self) -> "LordChristShortsPolicy":
        if set(self.owner_media_sources) != {"google_takeout", "local_master"}:
            raise ValueError("owner_media_sources must contain exactly google_takeout and local_master")
        ZoneInfo(self.timezone)
        return self


class ShortsInventoryItem(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    publication_id: str = Field(min_length=20, max_length=96)
    title: str = Field(min_length=1, max_length=500)
    description: str
    published_at: datetime | None
    duration_seconds: int | None = Field(default=None, ge=0, le=3600)
    source_revision: str = Field(min_length=1)
    surface_status: Literal["short", "candidate"]
    classification_reason: str = Field(min_length=1)
    owner_confirmation_required: bool
    canonical_watch_url: str
    canonical_shorts_url: str

    @model_validator(mode="after")
    def validate_identity(self) -> "ShortsInventoryItem":
        if _YOUTUBE_ID_RE.fullmatch(self.youtube_video_id) is None:
            raise ValueError("invalid YouTube video id")
        if self.publication_id != publication_id_for(self.youtube_video_id):
            raise ValueError("publication_id must be derived from the exact YouTube video id")
        expected_watch = f"https://www.youtube.com/watch?v={self.youtube_video_id}"
        expected_shorts = f"https://www.youtube.com/shorts/{self.youtube_video_id}"
        if self.canonical_watch_url != expected_watch or self.canonical_shorts_url != expected_shorts:
            raise ValueError("YouTube URLs must be derived from the exact video id")
        if self.owner_confirmation_required != (self.surface_status == "candidate"):
            raise ValueError("candidate status and owner_confirmation_required disagree")
        return self


class LordChristShortsInventory(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-inventory"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    youtube_oauth_alias: Literal["fedor-milovanov"]
    source_snapshot_id: str = Field(min_length=1)
    generated_at: datetime
    items: tuple[ShortsInventoryItem, ...]
    excluded_longform_count: int = Field(ge=0)
    unresolved_non_candidate_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_inventory(self) -> "LordChristShortsInventory":
        video_ids = [item.youtube_video_id for item in self.items]
        publication_ids = [item.publication_id for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("inventory YouTube video ids must be unique")
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("inventory publication ids must be unique")
        return self


class OwnerMediaBinding(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    source_kind: Literal["google_takeout", "local_master"]
    source_path: str = Field(min_length=1)


class OwnerMediaBindingManifest(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-owner-media-bindings"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    items: tuple[OwnerMediaBinding, ...]

    @model_validator(mode="after")
    def validate_bindings(self) -> "OwnerMediaBindingManifest":
        video_ids = [item.youtube_video_id for item in self.items]
        paths = [str(Path(item.source_path).expanduser()) for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("owner media binding video ids must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("one owner file path cannot be bound to multiple YouTube video ids")
        return self


class MediaProbeSummary(FrozenModel):
    container: str = Field(min_length=1)
    video_codec: str = Field(min_length=1)
    pixel_format: str | None
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    rotation_degrees: int
    duration_seconds: float = Field(gt=0, le=MAX_SHORT_DURATION_SECONDS)
    audio_stream_count: int = Field(ge=0, le=1)
    audio_codec: str | None


class AcceptedShortMedia(FrozenModel):
    youtube_video_id: str = Field(min_length=6, max_length=32)
    publication_id: str = Field(min_length=20, max_length=96)
    source_kind: Literal["google_takeout", "local_master"]
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_byte_size: int = Field(gt=0)
    source_probe: MediaProbeSummary
    transport_path: str = Field(min_length=1)
    media_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    media_byte_size: int = Field(gt=0, le=MAX_TELEGRAM_VIDEO_BYTES)
    transport_probe: MediaProbeSummary
    transcoded: bool

    @model_validator(mode="after")
    def validate_accepted_media(self) -> "AcceptedShortMedia":
        if self.publication_id != publication_id_for(self.youtube_video_id):
            raise ValueError("accepted media publication_id mismatch")
        transport = self.transport_probe
        if "mp4" not in {part.strip().casefold() for part in transport.container.split(",")}:
            raise ValueError("accepted Telegram transport container must include mp4")
        if transport.video_codec.casefold() != "h264":
            raise ValueError("accepted Telegram transport must use H.264")
        if (transport.pixel_format or "").casefold() != "yuv420p":
            raise ValueError("accepted Telegram transport must use yuv420p")
        if transport.rotation_degrees != 0:
            raise ValueError("accepted Telegram transport must bake orientation instead of relying on rotation metadata")
        if transport.width > transport.height:
            raise ValueError("accepted Telegram Short media must be square or vertical")
        if transport.audio_stream_count == 1 and (transport.audio_codec or "").casefold() != "aac":
            raise ValueError("accepted Telegram transport audio must be AAC")
        if transport.audio_stream_count == 0 and transport.audio_codec is not None:
            raise ValueError("silent media cannot declare an audio codec")
        if not self.transcoded and self.source_sha256 != self.media_sha256:
            raise ValueError("non-transcoded transport must preserve exact owner bytes")
        return self


class LordChristShortsMediaAcceptance(FrozenModel):
    schema_name: Literal["video-channel-manager.lordchrist-shorts-media-acceptance"]
    schema_version: Literal[1]
    project_key: Literal["lord-god-strength"]
    youtube_channel_id: Literal["UCeSJsC6go2c9pdJCuUI1BYA"]
    inventory_snapshot_id: str = Field(min_length=1)
    provider_access_performed: Literal[False]
    provider_write_performed: Literal[False]
    ffmpeg_version: str | None
    ffprobe_version: str
    items: tuple[AcceptedShortMedia, ...]

    @model_validator(mode="after")
    def validate_acceptance(self) -> "LordChristShortsMediaAcceptance":
        video_ids = [item.youtube_video_id for item in self.items]
        publication_ids = [item.publication_id for item in self.items]
        digests = [item.media_sha256 for item in self.items]
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("accepted media YouTube video ids must be unique")
        if len(publication_ids) != len(set(publication_ids)):
            raise ValueError("accepted media publication ids must be unique")
        if len(digests) != len(set(digests)):
            raise ValueError("exact duplicate media bytes are forbidden across the Shorts feed")
        if any(item.transcoded for item in self.items) and not self.ffmpeg_version:
            raise ValueError("transcoded media acceptance requires an ffmpeg version record")
        return self


class EffectSnapshot(FrozenModel):
    publication_id: str
    state: str
    provider_effect: str


def publication_id_for(video_id: str) -> str:
    value = video_id.strip()
    if _YOUTUBE_ID_RE.fullmatch(value) is None:
        raise ValueError(f"invalid YouTube video id: {video_id!r}")
    return f"lordchrist-short-{value}"


def _read_model(path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid {model.__name__} file {path}: {exc}") from exc


def _write_model(path: Path, value: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_policy(path: Path) -> LordChristShortsPolicy:
    return _read_model(path, LordChristShortsPolicy)


def load_inventory(path: Path) -> LordChristShortsInventory:
    return _read_model(path, LordChristShortsInventory)


def load_bindings(path: Path) -> OwnerMediaBindingManifest:
    return _read_model(path, OwnerMediaBindingManifest)


def load_media_acceptance(path: Path) -> LordChristShortsMediaAcceptance:
    return _read_model(path, LordChristShortsMediaAcceptance)


def build_inventory(package: AuditPackage, *, include_candidates: bool = True) -> LordChristShortsInventory:
    if package.channel.ref.channel_id != YOUTUBE_CHANNEL_ID:
        raise ValueError(
            f"AuditPackage channel mismatch: expected {YOUTUBE_CHANNEL_ID}, got {package.channel.ref.channel_id}"
        )
    if package.channel.ref.platform.value != "youtube":
        raise ValueError("LordChrist Shorts intake requires a YouTube AuditPackage")

    items: list[ShortsInventoryItem] = []
    excluded_longform = 0
    unresolved_non_candidate = 0
    for video in package.videos:
        if video.ref.channel_id != YOUTUBE_CHANNEL_ID:
            raise ValueError(f"cross-channel video in AuditPackage: {video.ref.remote_id}")
        classification = classify_youtube_surface(video)
        if classification.status == "longform":
            excluded_longform += 1
            continue
        if classification.status == "unknown" and not classification.short_candidate:
            unresolved_non_candidate += 1
            continue
        if classification.status == "unknown" and not include_candidates:
            continue
        status: Literal["short", "candidate"] = "short" if classification.status == "short" else "candidate"
        video_id = video.ref.remote_id
        items.append(
            ShortsInventoryItem(
                youtube_video_id=video_id,
                publication_id=publication_id_for(video_id),
                title=video.title.strip(),
                description=video.description,
                published_at=video.published_at,
                duration_seconds=video.duration_seconds,
                source_revision=video.revision,
                surface_status=status,
                classification_reason=classification.reason,
                owner_confirmation_required=status == "candidate",
                canonical_watch_url=f"https://www.youtube.com/watch?v={video_id}",
                canonical_shorts_url=f"https://www.youtube.com/shorts/{video_id}",
            )
        )

    def sort_key(item: ShortsInventoryItem) -> tuple[float, str]:
        if item.published_at is None:
            return (float("inf"), item.youtube_video_id)
        return (item.published_at.timestamp(), item.youtube_video_id)

    items.sort(key=sort_key)
    return LordChristShortsInventory(
        schema_name="video-channel-manager.lordchrist-shorts-inventory",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        youtube_oauth_alias=YOUTUBE_OAUTH_ALIAS,
        source_snapshot_id=str(package.snapshot_id),
        generated_at=package.generated_at,
        items=tuple(items),
        excluded_longform_count=excluded_longform,
        unresolved_non_candidate_count=unresolved_non_candidate,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _tool_version(tool: str) -> str:
    try:
        completed = subprocess.run(
            [tool, "-version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"required tool unavailable: {tool}") from exc
    first_line = completed.stdout.splitlines()
    return first_line[0].strip() if first_line else tool


def ffprobe_media(path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"ffprobe failed for {path}: {exc}") from exc
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe returned invalid JSON for {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"ffprobe returned a non-object for {path}")
    return payload


def run_ffmpeg(argv: list[str]) -> None:
    try:
        subprocess.run(argv, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"ffmpeg conversion failed: {exc}") from exc


def _rotation_degrees(stream: dict[str, Any]) -> int:
    candidates: list[object] = []
    tags = stream.get("tags")
    if isinstance(tags, dict):
        candidates.append(tags.get("rotate"))
    side_data = stream.get("side_data_list")
    if isinstance(side_data, list):
        for item in side_data:
            if isinstance(item, dict):
                candidates.append(item.get("rotation"))
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            rotation = int(round(float(str(candidate))))
        except ValueError:
            continue
        return rotation % 360
    return 0


def _positive_float(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normalize_probe(probe: dict[str, Any]) -> MediaProbeSummary:
    streams_raw = probe.get("streams")
    streams = [item for item in streams_raw if isinstance(item, dict)] if isinstance(streams_raw, list) else []
    videos = [item for item in streams if item.get("codec_type") == "video"]
    audios = [item for item in streams if item.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise ValueError(f"expected exactly one video stream, found {len(videos)}")
    if len(audios) > 1:
        raise ValueError(f"at most one audio stream is supported, found {len(audios)}")
    video = videos[0]
    try:
        source_width = int(video["width"])
        source_height = int(video["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("missing valid video dimensions") from exc
    if source_width <= 0 or source_height <= 0:
        raise ValueError("video dimensions must be positive")
    rotation = _rotation_degrees(video)
    if rotation in {90, 270}:
        width, height = source_height, source_width
    elif rotation in {0, 180}:
        width, height = source_width, source_height
    else:
        raise ValueError(f"unsupported video rotation {rotation}")

    format_raw = probe.get("format")
    format_info = format_raw if isinstance(format_raw, dict) else {}
    duration = _positive_float(video.get("duration")) or _positive_float(format_info.get("duration"))
    if duration is None:
        raise ValueError("media duration is unavailable")
    if duration > MAX_SHORT_DURATION_SECONDS:
        raise ValueError("media exceeds the 180-second Shorts cap")
    if width > height:
        raise ValueError("Short media must be square or vertical after rotation")

    audio_codec: str | None = None
    if audios:
        audio_codec = str(audios[0].get("codec_name") or "") or None
        if audio_codec is None:
            raise ValueError("audio stream codec is unavailable")

    container = str(format_info.get("format_name") or "").strip()
    if not container:
        raise ValueError("media container is unavailable")
    video_codec = str(video.get("codec_name") or "").strip()
    if not video_codec:
        raise ValueError("video codec is unavailable")
    pixel_format = str(video.get("pix_fmt") or "").strip() or None
    return MediaProbeSummary(
        container=container,
        video_codec=video_codec,
        pixel_format=pixel_format,
        width=width,
        height=height,
        rotation_degrees=rotation,
        duration_seconds=duration,
        audio_stream_count=len(audios),
        audio_codec=audio_codec,
    )


def is_telegram_ready(source_path: Path, summary: MediaProbeSummary) -> bool:
    containers = {part.strip().casefold() for part in summary.container.split(",")}
    return (
        "mp4" in containers
        and source_path.stat().st_size <= MAX_TELEGRAM_VIDEO_BYTES
        and summary.video_codec.casefold() == "h264"
        and (summary.pixel_format or "").casefold() == "yuv420p"
        and summary.rotation_degrees == 0
        and summary.width % 2 == 0
        and summary.height % 2 == 0
        and (
            summary.audio_stream_count == 0
            or (summary.audio_stream_count == 1 and (summary.audio_codec or "").casefold() == "aac")
        )
    )


def conversion_argv(
    source: Path,
    output: Path,
    *,
    source_summary: MediaProbeSummary,
) -> list[str]:
    duration = source_summary.duration_seconds
    audio_bps = AUDIO_BITRATE_BPS if source_summary.audio_stream_count else 0
    budget_bps = int((TRANSPORT_BUDGET_BYTES * 8) / duration)
    video_bps = min(
        MAX_VIDEO_BITRATE_BPS,
        max(MIN_VIDEO_BITRATE_BPS, budget_bps - audio_bps - 100_000),
    )
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
    ]
    if source_summary.audio_stream_count:
        argv.extend(["-map", "0:a:0"])
    else:
        argv.append("-an")
    argv.extend(
        [
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-b:v",
            str(video_bps),
            "-maxrate",
            str(video_bps),
            "-bufsize",
            str(video_bps * 2),
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
        ]
    )
    if source_summary.audio_stream_count:
        argv.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"])
    argv.extend(["-movflags", "+faststart", str(output)])
    return argv


def _validate_transport(
    inventory_item: ShortsInventoryItem,
    path: Path,
    summary: MediaProbeSummary,
) -> None:
    containers = {part.strip().casefold() for part in summary.container.split(",")}
    if "mp4" not in containers:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport container is not MP4")
    if path.stat().st_size > MAX_TELEGRAM_VIDEO_BYTES:
        raise ValueError(
            f"{inventory_item.youtube_video_id}: transport exceeds {MAX_TELEGRAM_VIDEO_BYTES} bytes"
        )
    if summary.video_codec.casefold() != "h264":
        raise ValueError(f"{inventory_item.youtube_video_id}: transport video codec is not H.264")
    if (summary.pixel_format or "").casefold() != "yuv420p":
        raise ValueError(f"{inventory_item.youtube_video_id}: transport pixel format is not yuv420p")
    if summary.rotation_degrees != 0:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport retains rotation metadata")
    if summary.width > summary.height:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport is landscape")
    if summary.width % 2 or summary.height % 2:
        raise ValueError(f"{inventory_item.youtube_video_id}: transport dimensions must be even")
    if summary.audio_stream_count == 1 and (summary.audio_codec or "").casefold() != "aac":
        raise ValueError(f"{inventory_item.youtube_video_id}: transport audio codec is not AAC")
    if (
        inventory_item.duration_seconds is not None
        and abs(summary.duration_seconds - inventory_item.duration_seconds) > 3.0
    ):
        raise ValueError(
            f"{inventory_item.youtube_video_id}: transport duration differs from YouTube inventory by over 3 seconds"
        )


def prepare_owner_media(
    inventory: LordChristShortsInventory,
    bindings: OwnerMediaBindingManifest,
    *,
    output_dir: Path,
    probe_runner: ProbeRunner = ffprobe_media,
    transcode_runner: TranscodeRunner = run_ffmpeg,
    ffprobe_version: str | None = None,
    ffmpeg_version: str | None = None,
) -> LordChristShortsMediaAcceptance:
    inventory_by_id = {item.youtube_video_id: item for item in inventory.items}
    output_dir.mkdir(parents=True, exist_ok=True)
    accepted: list[AcceptedShortMedia] = []
    used_ffmpeg = False
    for binding in bindings.items:
        item = inventory_by_id.get(binding.youtube_video_id)
        if item is None:
            raise ValueError(
                f"owner media binding references video outside the exact Shorts inventory: {binding.youtube_video_id}"
            )
        source = Path(binding.source_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"owner media file does not exist: {source}")
        source_probe = normalize_probe(probe_runner(source))
        if (
            item.duration_seconds is not None
            and abs(source_probe.duration_seconds - item.duration_seconds) > 3.0
        ):
            raise ValueError(
                f"{item.youtube_video_id}: owner media duration differs from YouTube inventory by over 3 seconds"
            )

        output = output_dir / f"{item.publication_id}.mp4"
        if output.exists():
            raise ValueError(f"refusing to overwrite an existing prepared transport: {output}")
        transcoded = not is_telegram_ready(source, source_probe)
        if transcoded:
            used_ffmpeg = True
            transcode_runner(conversion_argv(source, output, source_summary=source_probe))
        else:
            shutil.copyfile(source, output)
        if not output.is_file():
            raise ValueError(f"prepared Telegram transport was not created: {output}")

        transport_probe = normalize_probe(probe_runner(output))
        _validate_transport(item, output, transport_probe)
        accepted.append(
            AcceptedShortMedia(
                youtube_video_id=item.youtube_video_id,
                publication_id=item.publication_id,
                source_kind=binding.source_kind,
                source_path=str(source),
                source_sha256=_sha256(source),
                source_byte_size=source.stat().st_size,
                source_probe=source_probe,
                transport_path=str(output.resolve()),
                media_sha256=_sha256(output),
                media_byte_size=output.stat().st_size,
                transport_probe=transport_probe,
                transcoded=transcoded,
            )
        )

    actual_ffprobe_version = ffprobe_version or _tool_version("ffprobe")
    actual_ffmpeg_version = ffmpeg_version
    if used_ffmpeg and actual_ffmpeg_version is None:
        actual_ffmpeg_version = _tool_version("ffmpeg")
    return LordChristShortsMediaAcceptance(
        schema_name="video-channel-manager.lordchrist-shorts-media-acceptance",
        schema_version=1,
        project_key=PROJECT_KEY,
        youtube_channel_id=YOUTUBE_CHANNEL_ID,
        inventory_snapshot_id=inventory.source_snapshot_id,
        provider_access_performed=False,
        provider_write_performed=False,
        ffmpeg_version=actual_ffmpeg_version,
        ffprobe_version=actual_ffprobe_version,
        items=tuple(accepted),
    )


def _clean_title(title: str) -> str:
    cleaned = _TRAILING_SHORTS_TAGS_RE.sub("", " ".join(title.split())).strip(" -—|")
    return cleaned or "Видео"


def render_short_caption(item: ShortsInventoryItem) -> str:
    link = item.canonical_shorts_url
    suffix = f"\n\n▶️ YouTube: {link}"
    available = 1024 - len(suffix)
    title = _clean_title(item.title)
    if len(title) > available:
        title = title[: max(1, available - 1)].rstrip() + "…"
    return title + suffix


def _load_effect_entries(path: Path) -> tuple[EffectSnapshot, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read LordChrist state ledger {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"LordChrist state ledger must be an object: {path}")
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise ValueError(f"LordChrist state ledger has no entries object: {path}")
    result: list[EffectSnapshot] = []
    for publication_id, raw in entries.items():
        if not isinstance(raw, dict):
            raise ValueError(f"invalid ledger entry {publication_id!r} in {path}")
        result.append(
            EffectSnapshot(
                publication_id=str(raw.get("publication_id") or publication_id),
                state=str(raw.get("state") or ""),
                provider_effect=str(raw.get("provider_effect") or ""),
            )
        )
    return tuple(result)


def require_existing_lordchrist_state_clear(paths: Sequence[Path]) -> set[str]:
    from video_channel_manager.lordchrist_cross_track_effect_guard import (
        require_no_unresolved_provider_effects_across_tracks,
    )

    tracks: dict[str, Iterable[EffectSnapshot]] = {}
    existing_publication_ids: set[str] = set()
    for index, path in enumerate(paths):
        entries = _load_effect_entries(path)
        tracks[f"ledger{index + 1}"] = entries
        existing_publication_ids.update(entry.publication_id for entry in entries)
    if tracks:
        require_no_unresolved_provider_effects_across_tracks(tracks=tracks)
    return existing_publication_ids


def build_provider_inert_release(
    inventory: LordChristShortsInventory,
    acceptance: LordChristShortsMediaAcceptance,
    *,
    profile: TelegramChannelProfile,
    policy: LordChristShortsPolicy,
    start_date: date,
    approved_candidate_ids: Iterable[str] = (),
    existing_publication_ids: Iterable[str] = (),
) -> GenericReleaseQueue:
    if profile.project_key != PROJECT_KEY or profile.channel_username.casefold() != TELEGRAM_CHANNEL_USERNAME.casefold():
        raise ValueError("Telegram profile is not the canonical LordChrist profile")
    if profile.provider_writes_authorized:
        raise ValueError("Issue #501 release builder requires a write-disabled LordChrist profile")
    if profile.timezone != policy.timezone or profile.daily_verified_limit != policy.daily_short_limit:
        raise ValueError("LordChrist profile and Shorts policy cadence disagree")
    if acceptance.inventory_snapshot_id != inventory.source_snapshot_id:
        raise ValueError("media acceptance belongs to a different YouTube inventory snapshot")

    media_by_id = {item.youtube_video_id: item for item in acceptance.items}
    approved = {value.strip() for value in approved_candidate_ids if value.strip()}
    candidates = {item.youtube_video_id for item in inventory.items if item.surface_status == "candidate"}
    unknown_approvals = approved - candidates
    if unknown_approvals:
        raise ValueError("candidate approvals do not match candidate inventory ids: " + ", ".join(sorted(unknown_approvals)))

    selected = [
        item
        for item in inventory.items
        if item.surface_status == "short" or item.youtube_video_id in approved
    ]
    missing_media = [item.youtube_video_id for item in selected if item.youtube_video_id not in media_by_id]
    if missing_media:
        raise ValueError("exact accepted owner media is missing for: " + ", ".join(missing_media))
    if not selected:
        raise ValueError("no exact Shorts are ready for a provider-inert release")

    existing = set(existing_publication_ids)
    collisions = sorted(item.publication_id for item in selected if item.publication_id in existing)
    if collisions:
        raise ValueError("publication ids already exist in LordChrist durable state: " + ", ".join(collisions))

    hour, minute = (int(part) for part in policy.slot_local_time.split(":", maxsplit=1))
    zone = ZoneInfo(policy.timezone)
    first_slot = datetime.combine(start_date, time(hour=hour, minute=minute), tzinfo=zone)
    release_items: list[GenericReleaseItem] = []
    for index, item in enumerate(selected):
        media = media_by_id[item.youtube_video_id]
        runtime_path = f".runtime/lordchrist-shorts/{item.publication_id}.mp4"
        payload = render_video_payload(
            profile,
            publication_id=item.publication_id,
            caption=render_short_caption(item),
            media_path=runtime_path,
            media_sha256=media.media_sha256,
            media_byte_size=media.media_byte_size,
            media_filename=f"{item.publication_id}.mp4",
        )
        release_items.append(
            GenericReleaseItem(
                sequence=index + 1,
                publication_id=item.publication_id,
                scheduled_at=first_slot + timedelta(days=index),
                source_sha256=media.media_sha256,
                payload=payload,
            )
        )

    return GenericReleaseQueue(
        schema_name="video-channel-manager.telegram-release-queue",
        schema_version=1,
        release_id=f"lordchrist-shorts-{start_date.isoformat()}",
        project_key=PROJECT_KEY,
        channel_username=TELEGRAM_CHANNEL_USERNAME,
        profile_sha256=profile.digest,
        timezone=policy.timezone,
        daily_verified_limit=policy.daily_short_limit,
        target_binding_sha256=None,
        chat_id=None,
        bot_id=None,
        bot_username=None,
        release_authorized=False,
        reviewed_candidate_sha256=None,
        reviewed_by=None,
        reviewed_at=None,
        items=tuple(release_items),
    )


def _load_audit(path: Path) -> AuditPackage:
    try:
        return AuditPackage.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid YouTube AuditPackage {path}: {exc}") from exc


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Provider-inert LordChrist YouTube Shorts intake, owner-media preparation, and release planning."
    )
    sub = root.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-policy")
    validate.add_argument("--policy", type=Path, default=Path("content/telegram/lordchrist/shorts-feed-policy.json"))

    inventory = sub.add_parser("inventory")
    inventory.add_argument("--audit", type=Path, required=True)
    inventory.add_argument("--output", type=Path, required=True)
    inventory.add_argument("--exclude-candidates", action="store_true")

    prepare = sub.add_parser("prepare-media")
    prepare.add_argument("--inventory", type=Path, required=True)
    prepare.add_argument("--bindings", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    release = sub.add_parser("build-release")
    release.add_argument("--inventory", type=Path, required=True)
    release.add_argument("--media", type=Path, required=True)
    release.add_argument("--profile", type=Path, default=Path(TELEGRAM_PROFILE_PATH))
    release.add_argument("--policy", type=Path, default=Path("content/telegram/lordchrist/shorts-feed-policy.json"))
    release.add_argument("--start-date", type=date.fromisoformat, required=True)
    release.add_argument("--approve-candidate", action="append", default=[])
    release.add_argument("--existing-ledger", type=Path, action="append", default=[])
    release.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "validate-policy":
            policy = load_policy(args.policy)
            print(policy.model_dump_json(indent=2))
            return 0
        if args.command == "inventory":
            result = build_inventory(_load_audit(args.audit), include_candidates=not args.exclude_candidates)
            _write_model(args.output, result)
            print(
                json.dumps(
                    {
                        "items": len(result.items),
                        "exact_shorts": sum(item.surface_status == "short" for item in result.items),
                        "candidates": sum(item.surface_status == "candidate" for item in result.items),
                        "excluded_longform": result.excluded_longform_count,
                        "unresolved_non_candidate": result.unresolved_non_candidate_count,
                        "output": str(args.output),
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "prepare-media":
            result = prepare_owner_media(
                load_inventory(args.inventory),
                load_bindings(args.bindings),
                output_dir=args.output_dir,
            )
            _write_model(args.output, result)
            print(
                json.dumps(
                    {
                        "accepted": len(result.items),
                        "transcoded": sum(item.transcoded for item in result.items),
                        "output": str(args.output),
                        "provider_access_performed": False,
                        "provider_write_performed": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "build-release":
            existing_ids = require_existing_lordchrist_state_clear(args.existing_ledger)
            result = build_provider_inert_release(
                load_inventory(args.inventory),
                load_media_acceptance(args.media),
                profile=load_channel_profile(args.profile),
                policy=load_policy(args.policy),
                start_date=args.start_date,
                approved_candidate_ids=args.approve_candidate,
                existing_publication_ids=existing_ids,
            )
            _write_model(args.output, result)
            print(
                json.dumps(
                    {
                        "release_id": result.release_id,
                        "items": len(result.items),
                        "release_authorized": result.release_authorized,
                        "provider_write_performed": False,
                        "output": str(args.output),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
