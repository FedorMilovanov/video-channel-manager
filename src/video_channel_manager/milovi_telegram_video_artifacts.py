from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

SOURCE_MANIFEST = Path("content/telegram/milovi-cake/video-source-readiness-2026-08.json")
CONVERSION_CONTRACT = Path("content/telegram/milovi-cake/video-conversion-contract-2026-08.json")
DEFAULT_OUTPUT_DIR = Path("artifacts/milovi-telegram/video")
DEFAULT_EVIDENCE = Path("content/telegram/milovi-cake/video-conversion-evidence-2026-08.json")
EXPECTED_PROJECT = "milovi-cake"
EXPECTED_VIDEO_COUNT = 16
EXPECTED_MEDIA_IDS = tuple(f"v{index:02d}" for index in range(1, EXPECTED_VIDEO_COUNT + 1))
TELEGRAM_HARD_MAX_BYTES = 52_428_800
EXPECTED_SOURCE_AUDIO_CODEC = "opus"
EXPECTED_OUTPUT_AUDIO_CODEC = "aac"
EXPECTED_AUDIO_SAMPLE_RATE_HZ = 48_000
EXPECTED_AUDIO_CHANNELS = 2
EXPECTED_AUDIO_BITRATE = "128k"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _run(argv: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_blob_sha1(path: Path) -> str:
    return _run(["git", "hash-object", "--no-filters", str(path)])


def _tool_version(tool: str) -> str:
    return _run([tool, "-version"])


def _executable_sha256(tool: str) -> str:
    resolved = shutil.which(tool)
    if not resolved:
        raise ValueError(f"required tool not found: {tool}")
    return _sha256_file(Path(resolved))


def _environment_record(ffmpeg_version: str, ffprobe_version: str) -> dict[str, Any]:
    os_release_path = Path("/etc/os-release")
    os_release = os_release_path.read_text(encoding="utf-8") if os_release_path.exists() else ""
    record: dict[str, Any] = {
        "runner_os": os.environ.get("RUNNER_OS"),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
        "runner_image_os": os.environ.get("ImageOS"),
        "platform": platform.platform(),
        "python": sys.version,
        "os_release": os_release,
        "ffmpeg_version": ffmpeg_version,
        "ffprobe_version": ffprobe_version,
        "ffmpeg_executable_sha256": _executable_sha256("ffmpeg"),
        "ffprobe_executable_sha256": _executable_sha256("ffprobe"),
    }
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    record["execution_environment_digest"] = _sha256_bytes(canonical)
    return record


def _probe(path: Path) -> dict[str, Any]:
    raw = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"ffprobe returned non-object for {path}")
    return value


def _stream_list(probe: dict[str, Any], codec_type: str) -> list[dict[str, Any]]:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise ValueError("ffprobe streams are missing")
    return [item for item in streams if isinstance(item, dict) and item.get("codec_type") == codec_type]


def _duration(probe: dict[str, Any], video: dict[str, Any]) -> float:
    format_obj = probe.get("format")
    format_duration = format_obj.get("duration") if isinstance(format_obj, dict) else None
    for candidate in (video.get("duration"), format_duration):
        if candidate not in (None, "N/A"):
            value = float(str(candidate))
            if value > 0:
                return value
    raise ValueError("positive media duration is required")


def _rate(value: Any) -> str:
    text = str(value or "")
    if not text or text == "0/0":
        raise ValueError("positive average frame rate is required")
    rate = Fraction(text)
    if rate <= 0:
        raise ValueError("positive average frame rate is required")
    return text


def _positive_int(value: Any, field: str) -> int:
    parsed = int(value or 0)
    if parsed <= 0:
        raise ValueError(f"positive {field} is required")
    return parsed


def _normalized_probe(probe: dict[str, Any]) -> dict[str, Any]:
    videos = _stream_list(probe, "video")
    audios = _stream_list(probe, "audio")
    if len(videos) != 1:
        raise ValueError(f"exactly one video stream is required, found {len(videos)}")
    if len(audios) > 1:
        raise ValueError(f"at most one audio stream is allowed, found {len(audios)}")
    video = videos[0]
    width = _positive_int(video.get("width"), "source width")
    height = _positive_int(video.get("height"), "source height")
    format_obj = probe.get("format")
    if not isinstance(format_obj, dict):
        raise ValueError("ffprobe format object is missing")

    audio = audios[0] if audios else None
    return {
        "container": str(format_obj.get("format_name") or ""),
        "video_codec": str(video.get("codec_name") or ""),
        "pixel_format": str(video.get("pix_fmt") or ""),
        "width": width,
        "height": height,
        "avg_frame_rate": _rate(video.get("avg_frame_rate")),
        "duration_seconds": _duration(probe, video),
        "audio_stream_count": len(audios),
        "audio_present": bool(audios),
        "audio_codec": str(audio.get("codec_name") or "") if audio else None,
        "audio_sample_rate_hz": _positive_int(audio.get("sample_rate"), "audio sample rate") if audio else None,
        "audio_channels": _positive_int(audio.get("channels"), "audio channel count") if audio else None,
    }


def conversion_argv(source: Path, output: Path, *, source_has_audio: bool) -> list[str]:
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(source),
        "-map",
        "0:v:0",
    ]
    if source_has_audio:
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
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-fps_mode",
            "passthrough",
        ]
    )
    if source_has_audio:
        argv.extend(
            [
                "-c:a",
                EXPECTED_OUTPUT_AUDIO_CODEC,
                "-b:a",
                EXPECTED_AUDIO_BITRATE,
                "-ar",
                str(EXPECTED_AUDIO_SAMPLE_RATE_HZ),
                "-ac",
                str(EXPECTED_AUDIO_CHANNELS),
            ]
        )
    argv.extend(
        [
            "-threads",
            "1",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return argv


def _validate_reviewed_source_audio(media_id: str, source: dict[str, Any]) -> None:
    if source["audio_stream_count"] != 1:
        raise ValueError(f"{media_id} must contain exactly one reviewed source audio stream")
    if source["audio_codec"] != EXPECTED_SOURCE_AUDIO_CODEC:
        raise ValueError(f"{media_id} source audio codec differs from reviewed Opus contract")
    if source["audio_sample_rate_hz"] != EXPECTED_AUDIO_SAMPLE_RATE_HZ:
        raise ValueError(f"{media_id} source audio sample rate differs from reviewed 48 kHz contract")
    if source["audio_channels"] != EXPECTED_AUDIO_CHANNELS:
        raise ValueError(f"{media_id} source audio channel count differs from reviewed stereo contract")


def _validate_output(source: dict[str, Any], output: dict[str, Any], output_path: Path) -> None:
    if "mp4" not in output["container"].split(","):
        raise ValueError("output container is not MP4")
    if output["video_codec"] != "h264":
        raise ValueError("output video codec is not H.264")
    if output["pixel_format"] != "yuv420p":
        raise ValueError("output pixel format is not yuv420p")
    if output["width"] % 2 or output["height"] % 2:
        raise ValueError("output dimensions must be even")
    if output["width"] > source["width"] or output["height"] > source["height"]:
        raise ValueError("output geometry must never upscale")
    source_ratio = source["width"] / source["height"]
    output_ratio = output["width"] / output["height"]
    if abs(output_ratio - source_ratio) / source_ratio > 0.01:
        raise ValueError("output aspect ratio materially diverges from source")
    source_fps = float(Fraction(str(source["avg_frame_rate"])))
    output_fps = float(Fraction(str(output["avg_frame_rate"])))
    if abs(output_fps - source_fps) / source_fps > 0.01:
        raise ValueError("output average frame rate materially diverges from source")
    duration_tolerance = max(0.1, 2.0 / source_fps)
    if abs(output["duration_seconds"] - source["duration_seconds"]) > duration_tolerance:
        raise ValueError("output duration materially diverges from source")

    if source["audio_present"]:
        if output["audio_stream_count"] != 1 or not output["audio_present"]:
            raise ValueError("reviewed source audio must remain exactly one output stream")
        if output["audio_codec"] != EXPECTED_OUTPUT_AUDIO_CODEC:
            raise ValueError("output audio codec is not AAC")
        if output["audio_sample_rate_hz"] != source["audio_sample_rate_hz"]:
            raise ValueError("output audio sample rate does not preserve source shape")
        if output["audio_channels"] != source["audio_channels"]:
            raise ValueError("output audio channel count does not preserve source shape")
    elif output["audio_present"] or output["audio_stream_count"] != 0:
        raise ValueError("silent-source acceptance must not introduce audio")

    size = output_path.stat().st_size
    if size <= 0 or size >= TELEGRAM_HARD_MAX_BYTES:
        raise ValueError("output size is outside reviewed Telegram native-video bounds")


def _validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("provider_write_authorized") is not False or contract.get("source_mutation_allowed") is not False:
        raise ValueError("video conversion contract must remain provider-inert and source-read-only")
    if contract.get("document_fallback_allowed") is not False:
        raise ValueError("document fallback must remain forbidden")

    audio_review = contract.get("source_audio_review")
    if not isinstance(audio_review, dict):
        raise ValueError("exact source audio review is missing")
    if audio_review.get("status") != "exact_probe_reviewed_for_transport_preservation":
        raise ValueError("source audio review is not accepted for transport preservation")
    expected_audio_review = {
        "reviewed_video_count": EXPECTED_VIDEO_COUNT,
        "required_audio_stream_count_per_source": 1,
        "required_source_audio_codec": EXPECTED_SOURCE_AUDIO_CODEC,
        "required_source_audio_sample_rate_hz": EXPECTED_AUDIO_SAMPLE_RATE_HZ,
        "required_source_audio_channels": EXPECTED_AUDIO_CHANNELS,
    }
    for key, expected in expected_audio_review.items():
        if audio_review.get(key) != expected:
            raise ValueError(f"video contract source audio review mismatch: {key}")

    output_policy = contract.get("output_policy")
    if not isinstance(output_policy, dict):
        raise ValueError("video output policy is missing")
    audio_policy = output_policy.get("audio_policy")
    if not isinstance(audio_policy, dict):
        raise ValueError("video audio output policy is missing")
    if audio_policy.get("source_audio_codec_reviewed") != EXPECTED_SOURCE_AUDIO_CODEC:
        raise ValueError("video contract reviewed source audio codec differs from builder")
    if audio_policy.get("output_audio_codec") != EXPECTED_OUTPUT_AUDIO_CODEC:
        raise ValueError("video contract output audio codec differs from builder")
    if audio_policy.get("audio_bitrate_target") != EXPECTED_AUDIO_BITRATE:
        raise ValueError("video contract audio bitrate differs from builder")
    if audio_policy.get("sample_rate_hz") != EXPECTED_AUDIO_SAMPLE_RATE_HZ:
        raise ValueError("video contract audio sample rate differs from builder")
    if audio_policy.get("channels") != EXPECTED_AUDIO_CHANNELS:
        raise ValueError("video contract audio channels differ from builder")
    if audio_policy.get("extra_audio_streams_allowed") is not False:
        raise ValueError("video contract must forbid extra audio streams")

    size_policy = output_policy.get("size_policy")
    if not isinstance(size_policy, dict) or size_policy.get("telegram_hard_max_bytes") != TELEGRAM_HARD_MAX_BYTES:
        raise ValueError("video contract hard-size limit differs from builder")
    if output_policy.get("overwrite_existing_output") is not False:
        raise ValueError("video contract must forbid output overwrite")


def _evidence_identity(evidence: dict[str, Any]) -> str:
    identity = {key: value for key, value in evidence.items() if key not in {"generated_at_utc", "evidence_sha256"}}
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(canonical)


def build_all(
    *,
    source_checkout: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    evidence_path: Path = DEFAULT_EVIDENCE,
) -> dict[str, Any]:
    manifest = _json(SOURCE_MANIFEST)
    contract = _json(CONVERSION_CONTRACT)
    if manifest.get("project_key") != EXPECTED_PROJECT or contract.get("project_key") != EXPECTED_PROJECT:
        raise ValueError("Milovi video project identity mismatch")
    _validate_contract(contract)
    videos = manifest.get("videos")
    if not isinstance(videos, list) or len(videos) != EXPECTED_VIDEO_COUNT:
        raise ValueError("exactly 16 frozen Milovi source videos are required")
    media_ids = tuple(str(item.get("id") or "") for item in videos if isinstance(item, dict))
    if media_ids != EXPECTED_MEDIA_IDS:
        raise ValueError("Milovi media identities must remain exact ordered v01-v16")
    v04 = videos[3]
    if not isinstance(v04, dict) or v04.get("title") != "Видео: меренговый рулет":
        raise ValueError("canonical v04 editorial identity must remain meringue roll")

    expected_commit = str(manifest.get("source_commit") or "")
    actual_commit = _run(["git", "rev-parse", "HEAD"], cwd=source_checkout)
    if actual_commit != expected_commit:
        raise ValueError("source checkout does not match frozen Milovi source commit")

    ffmpeg_version = _tool_version("ffmpeg")
    ffprobe_version = _tool_version("ffprobe")
    environment = _environment_record(ffmpeg_version, ffprobe_version)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for raw in videos:
        if not isinstance(raw, dict):
            raise ValueError("invalid Milovi video source entry")
        media_id = str(raw.get("id") or "")
        source_rel = Path(str(raw.get("source_path") or ""))
        source_path = source_checkout / source_rel
        if not source_path.is_file():
            raise ValueError(f"missing exact source bytes for {media_id}: {source_rel}")
        if source_path.stat().st_size != int(raw.get("source_byte_size") or 0):
            raise ValueError(f"source byte size mismatch for {media_id}")
        if _git_blob_sha1(source_path) != str(raw.get("source_git_blob_sha1") or ""):
            raise ValueError(f"source Git blob mismatch for {media_id}")

        source_sha256 = _sha256_file(source_path)
        source_probe = _normalized_probe(_probe(source_path))
        if "webm" not in source_probe["container"].split(","):
            raise ValueError(f"{media_id} exact source container is not WebM")
        _validate_reviewed_source_audio(media_id, source_probe)

        output_path = output_dir / f"milovi-{media_id}.mp4"
        if output_path.exists():
            raise ValueError(f"refusing to overwrite existing output: {output_path}")
        argv = conversion_argv(source_path, output_path, source_has_audio=True)
        subprocess.run(argv, check=True)
        output_probe = _normalized_probe(_probe(output_path))
        _validate_output(source_probe, output_probe, output_path)

        records.append(
            {
                "media_id": media_id,
                "source_git_blob_sha1": raw["source_git_blob_sha1"],
                "source_sha256": source_sha256,
                "source_probe": source_probe,
                "ffmpeg_version": ffmpeg_version,
                "ffprobe_version": ffprobe_version,
                "execution_environment_digest": environment["execution_environment_digest"],
                "conversion_command_argv": argv,
                "output_path": output_path.as_posix(),
                "output_sha256": _sha256_file(output_path),
                "output_byte_size": output_path.stat().st_size,
                "output_container": output_probe["container"],
                "output_video_codec": output_probe["video_codec"],
                "output_pixel_format": output_probe["pixel_format"],
                "output_width": output_probe["width"],
                "output_height": output_probe["height"],
                "output_avg_frame_rate": output_probe["avg_frame_rate"],
                "output_duration_seconds": output_probe["duration_seconds"],
                "output_audio_present": output_probe["audio_present"],
                "output_audio_codec": output_probe["audio_codec"],
                "output_audio_sample_rate_hz": output_probe["audio_sample_rate_hz"],
                "output_audio_channels": output_probe["audio_channels"],
                "poster": raw["poster"],
                "editorial_title": raw["title"],
            }
        )

    evidence: dict[str, Any] = {
        "schema_name": "video-channel-manager.milovi-telegram-video-conversion-evidence",
        "schema_version": 1,
        "project_key": EXPECTED_PROJECT,
        "owning_issue": 353,
        "status": "accepted_16_of_16",
        "provider_access_performed": False,
        "provider_write_performed": False,
        "source_repository": manifest["source_repository"],
        "source_commit": expected_commit,
        "source_manifest": SOURCE_MANIFEST.as_posix(),
        "conversion_contract": CONVERSION_CONTRACT.as_posix(),
        "source_audio_review": contract["source_audio_review"],
        "accepted_output_count": len(records),
        "declared_video_count": EXPECTED_VIDEO_COUNT,
        "toolchain": environment,
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "outputs": records,
    }
    evidence["evidence_sha256"] = _evidence_identity(evidence)
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provider-free exact Milovi Telegram video artifact builder")
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = build_all(
        source_checkout=args.source_checkout,
        output_dir=args.output_dir,
        evidence_path=args.evidence,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "accepted_output_count": result["accepted_output_count"],
                "evidence_sha256": result["evidence_sha256"],
                "provider_access_performed": False,
                "provider_write_performed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
