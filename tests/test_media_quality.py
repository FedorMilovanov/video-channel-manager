from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from video_channel_manager.local_media.quality import MediaQualityError, probe_media, sha256_file


def _completed(payload: object, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["ffprobe"],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr=stderr,
    )


def test_sha256_file_streams_file_content(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video-bytes")

    assert sha256_file(media, chunk_size=3) == f"sha256:{hashlib.sha256(b'video-bytes').hexdigest()}"


def test_probe_media_requires_audio_and_video_and_returns_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video-bytes")
    payload = {
        "format": {"format_name": "mov,mp4,m4a", "duration": "42.5", "size": str(media.stat().st_size)},
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
            {"index": 1, "codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
        ],
    }
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _completed(payload))

    report = probe_media(media)

    assert report.duration_seconds == 42.5
    assert report.format_names == ("mov", "mp4", "m4a")
    assert report.video_stream_count == 1
    assert report.audio_stream_count == 1
    assert report.video_codec == "h264"
    assert report.audio_codec == "aac"
    assert report.width == 1920
    assert report.height == 1080
    assert report.sample_rate_hz == 48000
    assert report.audio_channels == 2
    assert report.sha256 == f"sha256:{hashlib.sha256(b'video-bytes').hexdigest()}"
    assert report.to_dict()["size_bytes"] == len(b"video-bytes")


def test_probe_media_rejects_missing_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video")
    payload = {
        "format": {"duration": "5"},
        "streams": [{"codec_type": "video", "codec_name": "h264"}],
    }
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _completed(payload))

    with pytest.raises(MediaQualityError, match="no audio stream"):
        probe_media(media)


def test_probe_media_reports_ffprobe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"broken")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _completed({}, returncode=1, stderr="invalid data found"),
    )

    with pytest.raises(MediaQualityError, match="invalid data found"):
        probe_media(media)


def test_probe_media_rejects_nonpositive_timeout(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video")

    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        probe_media(media, timeout_seconds=0)
