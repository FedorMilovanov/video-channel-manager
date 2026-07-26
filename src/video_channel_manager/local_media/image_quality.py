from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from video_channel_manager.local_media.quality import sha256_file

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SOF_MARKERS = frozenset(
    {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
)


class ImageQualityError(RuntimeError):
    """Raised when a local thumbnail is not a valid supported image."""


@dataclass(frozen=True, slots=True)
class ImageQualityReport:
    path: str
    size_bytes: int
    sha256: str
    format: str
    width: int
    height: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(_PNG_SIGNATURE) or len(data) < 24:
        return None
    if data[12:16] != b"IHDR":
        raise ImageQualityError("PNG has no IHDR chunk at the expected position")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    position = 2
    length = len(data)
    while position < length:
        while position < length and data[position] != 0xFF:
            position += 1
        while position < length and data[position] == 0xFF:
            position += 1
        if position >= length:
            break
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            break
        if position + 2 > length:
            raise ImageQualityError("JPEG ended before a segment length")
        segment_length = int.from_bytes(data[position : position + 2], "big")
        if segment_length < 2 or position + segment_length > length:
            raise ImageQualityError("JPEG contains an invalid segment length")
        if marker in _JPEG_SOF_MARKERS:
            if segment_length < 7:
                raise ImageQualityError("JPEG SOF segment is too short")
            height = int.from_bytes(data[position + 3 : position + 5], "big")
            width = int.from_bytes(data[position + 5 : position + 7], "big")
            return width, height
        position += segment_length
    raise ImageQualityError("JPEG contains no supported start-of-frame segment")


def inspect_image(
    path: Path,
    *,
    max_size_bytes: int = 25 * 1024 * 1024,
    calculate_sha256: bool = True,
) -> ImageQualityReport:
    """Validate JPEG/PNG magic and dimensions without trusting the extension."""

    if max_size_bytes <= 0:
        raise ValueError("max_size_bytes must be positive")
    if not path.is_file():
        raise ImageQualityError(f"Image file does not exist: {path}")
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise ImageQualityError(f"Image file is empty: {path}")
    if size_bytes > max_size_bytes:
        raise ImageQualityError(
            f"Image file is {size_bytes} bytes, above the configured limit {max_size_bytes}: {path}"
        )
    data = path.read_bytes()
    dimensions = _png_dimensions(data)
    image_format = "png"
    if dimensions is None:
        dimensions = _jpeg_dimensions(data)
        image_format = "jpeg"
    if dimensions is None:
        raise ImageQualityError(f"Only valid JPEG and PNG thumbnails are supported: {path}")
    width, height = dimensions
    if width <= 0 or height <= 0:
        raise ImageQualityError(f"Image dimensions are not positive: {width}x{height}")
    return ImageQualityReport(
        path=str(path.resolve()),
        size_bytes=size_bytes,
        sha256=sha256_file(path) if calculate_sha256 else "not-calculated",
        format=image_format,
        width=width,
        height=height,
    )


__all__ = ["ImageQualityError", "ImageQualityReport", "inspect_image"]
