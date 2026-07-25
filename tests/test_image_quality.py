from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from video_channel_manager.local_media.image_quality import ImageQualityError, inspect_image


def _png(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def _jpeg(width: int, height: int) -> bytes:
    # SOI + baseline SOF0 segment. The image is sufficient for deterministic
    # header validation; no decoder is used by the quality gate.
    sof = (
        b"\xff\xc0"
        + (17).to_bytes(2, "big")
        + b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03"
        + b"\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def test_inspect_png_uses_magic_dimensions_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "thumbnail.bin"
    content = _png(1280, 720)
    path.write_bytes(content)

    report = inspect_image(path)

    assert report.format == "png"
    assert report.width == 1280
    assert report.height == 720
    assert report.size_bytes == len(content)
    assert report.sha256 == f"sha256:{hashlib.sha256(content).hexdigest()}"


def test_inspect_jpeg_uses_sof_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "thumbnail.jpg"
    path.write_bytes(_jpeg(1920, 1080))

    report = inspect_image(path)

    assert report.format == "jpeg"
    assert report.width == 1920
    assert report.height == 1080


def test_inspect_rejects_extension_only_fake_image(tmp_path: Path) -> None:
    path = tmp_path / "thumbnail.jpg"
    path.write_bytes(b"not-an-image")

    with pytest.raises(ImageQualityError, match="Only valid JPEG and PNG"):
        inspect_image(path)


def test_inspect_rejects_oversized_file_before_reading(tmp_path: Path) -> None:
    path = tmp_path / "thumbnail.png"
    path.write_bytes(_png(1, 1))

    with pytest.raises(ImageQualityError, match="above the configured limit"):
        inspect_image(path, max_size_bytes=4)


def test_inspect_rejects_nonpositive_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "thumbnail.png"
    path.write_bytes(_png(1, 1))

    with pytest.raises(ValueError, match="must be positive"):
        inspect_image(path, max_size_bytes=0)
