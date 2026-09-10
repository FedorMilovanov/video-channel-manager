from __future__ import annotations

import struct
from pathlib import Path

import pytest

from video_channel_manager.instagram.artifact import (
    InstagramArtifactCompatibilityError,
    bind_instagram_reel_probe,
)
from video_channel_manager.instagram.mp4_structure import (
    InstagramMp4StructureError,
    inspect_instagram_mp4_structure,
)
from video_channel_manager.local_media.artifact import MediaProbeEvidence


def _probe(path: Path, *, sample_rate_hz: int = 44_100, audio_channels: int = 2) -> MediaProbeEvidence:
    return MediaProbeEvidence(
        path=str(path.resolve()),
        size_bytes=1234,
        sha256="sha256:" + "a" * 64,
        duration_seconds=12.0,
        format_names=("mov", "mp4", "m4a", "3gp", "3g2", "mj2"),
        video_stream_count=1,
        audio_stream_count=1,
        video_codec="h264",
        audio_codec="aac",
        width=1080,
        height=1920,
        sample_rate_hz=sample_rate_hz,
        audio_channels=audio_channels,
        video_frame_rate_fps=30.0,
        video_bitrate_bps=5_000_000,
        audio_bitrate_bps=128_000,
    )


def _box(box_type: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), box_type) + payload


def _mp4_bytes(*, edit_list: bool = False, moov_after_mdat: bool = False) -> bytes:
    ftyp = _box(b"ftyp", b"isom\x00\x00\x02\x00isom")
    trak_payload = _box(b"tkhd")
    if edit_list:
        trak_payload += _box(b"edts", _box(b"elst"))
    moov = _box(b"moov", _box(b"trak", trak_payload))
    mdat = _box(b"mdat", b"payload")
    return ftyp + (mdat + moov if moov_after_mdat else moov + mdat)


def test_reel_contract_accepts_44100_hz_aac(tmp_path: Path) -> None:
    path = tmp_path / "reel.mp4"
    binding = bind_instagram_reel_probe(
        _probe(path, sample_rate_hz=44_100),
        media_manifest_sha256="sha256:" + "b" * 64,
    )
    assert binding.audio_sample_rate_hz == 44_100
    assert binding.audio_channels == 2


def test_reel_contract_rejects_audio_above_48000_hz(tmp_path: Path) -> None:
    path = tmp_path / "reel.mp4"
    with pytest.raises(InstagramArtifactCompatibilityError) as error:
        bind_instagram_reel_probe(
            _probe(path, sample_rate_hz=96_000),
            media_manifest_sha256="sha256:" + "b" * 64,
        )
    assert "audio_sample_rate_above_48000_hz" in error.value.reasons


def test_reel_contract_rejects_more_than_stereo_audio(tmp_path: Path) -> None:
    path = tmp_path / "reel.mp4"
    with pytest.raises(InstagramArtifactCompatibilityError) as error:
        bind_instagram_reel_probe(
            _probe(path, audio_channels=6),
            media_manifest_sha256="sha256:" + "b" * 64,
        )
    assert "audio_channels_not_mono_or_stereo" in error.value.reasons


def test_mp4_structure_accepts_faststart_without_edit_lists(tmp_path: Path) -> None:
    path = tmp_path / "clean.mp4"
    path.write_bytes(_mp4_bytes())
    evidence = inspect_instagram_mp4_structure(path)
    assert evidence.moov_before_mdat is True
    assert evidence.edit_list_paths == ()
    assert evidence.ftyp_offset == 0


def test_mp4_structure_rejects_edit_list(tmp_path: Path) -> None:
    path = tmp_path / "edit-list.mp4"
    path.write_bytes(_mp4_bytes(edit_list=True))
    with pytest.raises(InstagramMp4StructureError) as error:
        inspect_instagram_mp4_structure(path)
    assert "mp4_edit_list_present" in error.value.reasons


def test_mp4_structure_rejects_moov_after_mdat(tmp_path: Path) -> None:
    path = tmp_path / "slow-start.mp4"
    path.write_bytes(_mp4_bytes(moov_after_mdat=True))
    with pytest.raises(InstagramMp4StructureError) as error:
        inspect_instagram_mp4_structure(path)
    assert "mp4_moov_not_before_mdat" in error.value.reasons


def test_mp4_structure_fails_closed_on_truncated_box(tmp_path: Path) -> None:
    path = tmp_path / "truncated.mp4"
    path.write_bytes(struct.pack(">I4s", 100, b"ftyp") + b"tiny")
    with pytest.raises(InstagramMp4StructureError):
        inspect_instagram_mp4_structure(path)
