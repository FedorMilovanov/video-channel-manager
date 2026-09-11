from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from video_channel_manager.instagram.mp4_structure import (
    InstagramMp4StructureError,
    inspect_instagram_mp4_video_sample,
)


class InstagramClosedGopError(ValueError):
    """Local AVC/HEVC stream cannot be proved to use closed GOPs."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__(f"Instagram closed-GOP proof failed: {', '.join(reasons)}")


@dataclass(frozen=True, slots=True)
class InstagramClosedGopEvidence:
    codec: str
    nal_length_size: int
    intra_frame_count: int
    idr_frame_count: int

    @property
    def closed_gop(self) -> bool:
        return self.intra_frame_count > 0 and self.intra_frame_count == self.idr_frame_count


def _nonnegative_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _positive_int(value: object) -> int | None:
    parsed = _nonnegative_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _nal_types(access_unit: bytes, *, codec: str, nal_length_size: int) -> tuple[int, ...]:
    if nal_length_size not in {1, 2, 4}:
        raise InstagramClosedGopError(("nal_length_size_unsupported",))

    offset = 0
    nal_types: list[int] = []
    while offset < len(access_unit):
        if len(access_unit) - offset < nal_length_size:
            raise InstagramClosedGopError(("truncated_nal_length_prefix",))
        nal_size = int.from_bytes(access_unit[offset : offset + nal_length_size], "big")
        offset += nal_length_size
        if nal_size <= 0 or offset + nal_size > len(access_unit):
            raise InstagramClosedGopError(("invalid_length_prefixed_nal_unit",))
        nal = access_unit[offset : offset + nal_size]
        offset += nal_size

        if codec == "h264":
            if not nal or nal[0] & 0x80:
                raise InstagramClosedGopError(("invalid_h264_nal_header",))
            nal_type = nal[0] & 0x1F
            if nal_type == 0:
                raise InstagramClosedGopError(("invalid_h264_nal_type",))
        elif codec == "hevc":
            if len(nal) < 2 or nal[0] & 0x80 or (nal[1] & 0x07) == 0:
                raise InstagramClosedGopError(("invalid_hevc_nal_header",))
            nal_type = (nal[0] >> 1) & 0x3F
        else:
            raise InstagramClosedGopError(("video_codec_not_h264_or_hevc",))
        nal_types.append(nal_type)

    if not nal_types:
        raise InstagramClosedGopError(("access_unit_has_no_nal_units",))
    return tuple(nal_types)


def _is_idr_access_unit(nal_types: tuple[int, ...], *, codec: str) -> bool:
    if codec == "h264":
        return 5 in nal_types
    if codec == "hevc":
        return any(nal_type in {19, 20} for nal_type in nal_types)
    raise InstagramClosedGopError(("video_codec_not_h264_or_hevc",))


def _intra_frames(
    path: Path,
    *,
    ffprobe: str,
    timeout_seconds: float,
) -> tuple[dict[str, Any], ...]:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_frames",
        "-show_entries",
        "frame=pict_type,pkt_pos,pkt_size",
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
        raise InstagramClosedGopError(("ffprobe_not_found",)) from exc
    except subprocess.TimeoutExpired as exc:
        raise InstagramClosedGopError(("ffprobe_closed_gop_timeout",)) from exc

    if completed.returncode != 0:
        raise InstagramClosedGopError(("ffprobe_closed_gop_failed",))
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise InstagramClosedGopError(("ffprobe_closed_gop_invalid_json",)) from exc
    if not isinstance(payload, dict):
        raise InstagramClosedGopError(("ffprobe_closed_gop_non_object",))

    raw_frames = payload.get("frames")
    if not isinstance(raw_frames, list):
        raise InstagramClosedGopError(("ffprobe_closed_gop_frames_missing",))
    frames = tuple(
        frame
        for frame in raw_frames
        if isinstance(frame, dict) and str(frame.get("pict_type") or "").strip().upper() == "I"
    )
    if not frames:
        raise InstagramClosedGopError(("intra_frame_missing",))
    return frames


def inspect_instagram_closed_gop(
    path: Path,
    *,
    expected_codec: str | None = None,
    ffprobe: str = "ffprobe",
    timeout_seconds: float = 120.0,
) -> InstagramClosedGopEvidence:
    """Fail closed unless every intra access unit is an AVC/HEVC IDR access unit.

    This is intentionally stricter than merely trusting container key-frame flags:
    open-GOP encoders commonly emit non-IDR I pictures at later GOP boundaries.
    """

    candidate = path.expanduser().resolve()
    if not candidate.is_file():
        raise InstagramClosedGopError(("media_file_missing",))

    try:
        sample = inspect_instagram_mp4_video_sample(candidate)
    except InstagramMp4StructureError as exc:
        raise InstagramClosedGopError(exc.reasons) from exc

    codec = sample.codec
    normalized_expected = (expected_codec or codec).strip().lower()
    if normalized_expected != codec:
        raise InstagramClosedGopError(("mp4_sample_codec_mismatch",))

    frames = _intra_frames(candidate, ffprobe=ffprobe, timeout_seconds=timeout_seconds)
    file_size = candidate.stat().st_size
    idr_count = 0

    try:
        with candidate.open("rb") as stream:
            for index, frame in enumerate(frames):
                packet_pos = _nonnegative_int(frame.get("pkt_pos"))
                packet_size = _positive_int(frame.get("pkt_size"))
                if packet_pos is None or packet_size is None:
                    raise InstagramClosedGopError((f"intra_packet_location_missing:{index}",))
                if packet_pos + packet_size > file_size:
                    raise InstagramClosedGopError((f"intra_packet_outside_file:{index}",))

                stream.seek(packet_pos)
                access_unit = stream.read(packet_size)
                if len(access_unit) != packet_size:
                    raise InstagramClosedGopError((f"intra_packet_truncated:{index}",))
                try:
                    nal_types = _nal_types(
                        access_unit,
                        codec=codec,
                        nal_length_size=sample.nal_length_size,
                    )
                except InstagramClosedGopError as exc:
                    raise InstagramClosedGopError(
                        tuple(f"intra_frame_{index}:{reason}" for reason in exc.reasons)
                    ) from exc
                if not _is_idr_access_unit(nal_types, codec=codec):
                    raise InstagramClosedGopError((f"non_idr_intra_frame:{index}",))
                idr_count += 1
    except InstagramClosedGopError:
        raise
    except OSError as exc:
        raise InstagramClosedGopError((f"closed_gop_read_failed:{type(exc).__name__}",)) from exc

    return InstagramClosedGopEvidence(
        codec=codec,
        nal_length_size=sample.nal_length_size,
        intra_frame_count=len(frames),
        idr_frame_count=idr_count,
    )


__all__ = [
    "InstagramClosedGopError",
    "InstagramClosedGopEvidence",
    "inspect_instagram_closed_gop",
]
