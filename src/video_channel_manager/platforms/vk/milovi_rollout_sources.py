from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

YOUTUBE_CHANNEL_ID = "UCMDnxfGZiBqcDzgUV1zjFpw"
PREPARED_SCHEMA = "video-manager.milovi-issue-323-prepared-sources"
SOURCE_SNAPSHOT_ID = "milovi-cake-issue-323-reviewed-public106-final-d48-a8841ece-v1"
VK_CLIP_FORMAT_SELECTOR = (
    "bv[vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a][ext=m4a]/"
    "b[vcodec^=avc1][acodec^=mp4a][ext=mp4]"
)
VK_VIDEO_CODEC = "h264"
VK_AUDIO_CODEC = "aac"
VK_MEDIA_CACHE_DIR = "media-vk-h264-aac-v1"
ROLL_OUT_IDS = (
    "d48QLgOuiTs",
    "Oix9s6l9vNg",
    "uA8SbnXzJJc",
    "u-PuqjWuhKk",
    "L6XG2_zzrPU",
    "pCARxxaVjTw",
    "OWV-KGsLdA8",
    "o1WXIMupuws",
    "1_SuzeQD_1g",
    "5B9OuXbdGKc",
    "BAVKrQQ00XI",
    "R0KjJvbxS8s",
)


class MiloviSourceError(RuntimeError):
    pass


class MiloviSourceCodecError(MiloviSourceError):
    """A local source is intact but not encoded for the reviewed VK upload profile."""


@dataclass(frozen=True, slots=True)
class SourceAsset:
    source_id: str
    source_url: str
    title: str
    duration_seconds: int
    media_path: str
    media_sha256: str
    width: int
    height: int
    description: str
    wall_message: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _run_checked(args: list[str], *, timeout: int) -> str:
    completed = subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if completed.returncode != 0:
        safe = completed.stderr[-2000:].replace("\r", " ").replace("\n", " ")
        raise MiloviSourceError(f"Command failed ({completed.returncode}): {Path(args[0]).name}: {safe}")
    return completed.stdout.strip()


def _require_tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise MiloviSourceError(f"Required executable is missing from PATH: {name}")
    return resolved


def build_description(title: str, source_id: str) -> str:
    marker = f"Источник YouTube Shorts: https://www.youtube.com/shorts/{source_id}"
    normalized = title.strip()
    return f"{normalized}\n\n{marker}" if normalized else marker


def build_wall_message(title: str, source_id: str) -> str:
    normalized = title.strip() or "Milovi Cake"
    return f"{normalized}\n\n🌐 https://milovicake.ru/\nИсточник: https://www.youtube.com/shorts/{source_id}"


def _hydrate_source(yt_dlp: str, source_id: str) -> dict[str, Any]:
    source_url = f"https://www.youtube.com/shorts/{source_id}"
    raw = _run_checked(
        [yt_dlp, "--no-playlist", "--no-warnings", "--quiet", "--dump-single-json", source_url],
        timeout=180,
    )
    payload = cast(dict[str, Any], json.loads(raw))
    if str(payload.get("id") or "") != source_id:
        raise MiloviSourceError(f"YouTube identity mismatch for {source_id}")
    if str(payload.get("channel_id") or "") != YOUTUBE_CHANNEL_ID:
        raise MiloviSourceError(f"{source_id} belongs to {payload.get('channel_id')!r}, expected {YOUTUBE_CHANNEL_ID}")
    duration = float(payload.get("duration") or 0)
    if duration <= 0 or duration > 180.5:
        raise MiloviSourceError(f"{source_id} duration is outside the reviewed Clip bound: {duration}")
    if not str(payload.get("title") or "").strip():
        raise MiloviSourceError(f"YouTube title is blank for {source_id}")
    return payload


def _probe_media(ffprobe: str, media_path: Path) -> tuple[int, int, float]:
    raw = _run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height:format=duration",
            "-of",
            "json",
            str(media_path),
        ],
        timeout=120,
    )
    payload = json.loads(raw)
    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise MiloviSourceError(f"ffprobe streams missing for {media_path}")
    video_streams = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"]
    audio_streams = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"]
    if len(video_streams) != 1 or len(audio_streams) != 1:
        raise MiloviSourceError(
            f"Source must contain exactly one video and one audio stream: {media_path.name} "
            f"video={len(video_streams)} audio={len(audio_streams)}"
        )
    video_codec = str(video_streams[0].get("codec_name") or "").strip().casefold()
    audio_codec = str(audio_streams[0].get("codec_name") or "").strip().casefold()
    if video_codec != VK_VIDEO_CODEC or audio_codec != VK_AUDIO_CODEC:
        raise MiloviSourceCodecError(
            f"Source codecs are outside reviewed VK profile: {media_path.name} "
            f"video={video_codec or '<missing>'} audio={audio_codec or '<missing>'}; "
            f"expected {VK_VIDEO_CODEC}/{VK_AUDIO_CODEC}"
        )
    width = int(video_streams[0].get("width") or 0)
    height = int(video_streams[0].get("height") or 0)
    duration = float((payload.get("format") or {}).get("duration") or 0)
    if width <= 0 or height <= 0 or duration <= 0:
        raise MiloviSourceError(f"Invalid media geometry/duration for {media_path}")
    if height <= width:
        raise MiloviSourceError(f"Source is not vertical: {media_path.name} {width}x{height}")
    if duration > 180.5:
        raise MiloviSourceError(f"Source exceeds 3-minute Clip bound: {media_path.name} {duration}")
    return width, height, duration


def _download_source(yt_dlp: str, ffprobe: str, source_id: str, media_dir: Path) -> SourceAsset:
    metadata = _hydrate_source(yt_dlp, source_id)
    source_url = f"https://www.youtube.com/shorts/{source_id}"
    media_dir.mkdir(parents=True, exist_ok=True)
    template = media_dir / f"{source_id}.%(ext)s"
    stdout = _run_checked(
        [
            yt_dlp,
            "--no-playlist",
            "--no-warnings",
            "--quiet",
            "--force-overwrites",
            "--merge-output-format",
            "mp4",
            "-f",
            VK_CLIP_FORMAT_SELECTOR,
            "--print",
            "after_move:filepath",
            "-o",
            str(template),
            source_url,
        ],
        timeout=600,
    )
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise MiloviSourceError(f"yt-dlp did not return one exact output path for {source_id}: {lines!r}")
    media_path = Path(lines[0]).resolve()
    if not media_path.is_file() or not media_path.name.startswith(source_id + "."):
        raise MiloviSourceError(f"Unexpected downloaded path for {source_id}: {media_path}")
    width, height, probed_duration = _probe_media(ffprobe, media_path)
    observed_duration = float(metadata.get("duration") or 0)
    if abs(probed_duration - observed_duration) > 4.0:
        raise MiloviSourceError(
            f"Downloaded duration differs from YouTube metadata for {source_id}: {probed_duration} vs {observed_duration}"
        )
    title = str(metadata.get("title") or "").strip()
    return SourceAsset(
        source_id=source_id,
        source_url=source_url,
        title=title,
        duration_seconds=int(round(observed_duration)),
        media_path=str(media_path),
        media_sha256=sha256_file(media_path),
        width=width,
        height=height,
        description=build_description(title, source_id),
        wall_message=build_wall_message(title, source_id),
    )


def _validate_cached_assets(assets: list[SourceAsset], *, ffprobe: str) -> bool:
    """Return False only for the known legacy codec-cache case; all other drift is a hard failure."""
    for asset in assets:
        media_path = Path(asset.media_path)
        if not media_path.is_file() or sha256_file(media_path) != asset.media_sha256:
            raise MiloviSourceError(f"Prepared-source bytes are missing or changed for {asset.source_id}")
    try:
        for asset in assets:
            width, height, duration = _probe_media(ffprobe, Path(asset.media_path))
            if width != asset.width or height != asset.height:
                raise MiloviSourceError(f"Prepared-source geometry changed for {asset.source_id}")
            if abs(duration - float(asset.duration_seconds)) > 4.0:
                raise MiloviSourceError(f"Prepared-source duration changed for {asset.source_id}")
    except MiloviSourceCodecError:
        return False
    return True


def _write_prepared_manifest(path: Path, assets: list[SourceAsset]) -> None:
    write_json_atomic(
        path,
        {
            "schema_name": PREPARED_SCHEMA,
            "schema_version": 1,
            "source_snapshot_id": SOURCE_SNAPSHOT_ID,
            "media_profile": "vk-h264-aac-v1",
            "assets": [asdict(asset) for asset in assets],
        },
    )


def prepare_sources(work_dir: Path) -> list[SourceAsset]:
    prepared_path = work_dir / "prepared-sources.json"
    ffprobe: str | None = None
    if prepared_path.is_file():
        payload = json.loads(prepared_path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_name") != PREPARED_SCHEMA
            or int(payload.get("schema_version") or 0) != 1
            or payload.get("source_snapshot_id") != SOURCE_SNAPSHOT_ID
        ):
            raise MiloviSourceError("Prepared-source provenance differs from Issue #323")
        assets = [SourceAsset(**item) for item in payload.get("assets", []) if isinstance(item, dict)]
        if tuple(asset.source_id for asset in assets) != ROLL_OUT_IDS:
            raise MiloviSourceError("Prepared-source allowlist/order differs from Issue #323")
        ffprobe = _require_tool("ffprobe")
        if _validate_cached_assets(assets, ffprobe=ffprobe):
            return assets

    yt_dlp = _require_tool("yt-dlp")
    if ffprobe is None:
        ffprobe = _require_tool("ffprobe")
    media_dir = work_dir / VK_MEDIA_CACHE_DIR
    assets = [_download_source(yt_dlp, ffprobe, source_id, media_dir) for source_id in ROLL_OUT_IDS]
    _write_prepared_manifest(prepared_path, assets)
    return assets


__all__ = [
    "PREPARED_SCHEMA",
    "ROLL_OUT_IDS",
    "SOURCE_SNAPSHOT_ID",
    "VK_AUDIO_CODEC",
    "VK_CLIP_FORMAT_SELECTOR",
    "VK_MEDIA_CACHE_DIR",
    "VK_VIDEO_CODEC",
    "SourceAsset",
    "YOUTUBE_CHANNEL_ID",
    "MiloviSourceCodecError",
    "MiloviSourceError",
    "build_description",
    "build_wall_message",
    "prepare_sources",
    "sha256_file",
    "write_json_atomic",
]
