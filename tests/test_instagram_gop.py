from __future__ import annotations

import json
import struct
import subprocess
from pathlib import Path

import pytest

import video_channel_manager.instagram.gop as gop_module
from video_channel_manager.instagram.gop import (
    InstagramClosedGopError,
    inspect_instagram_closed_gop,
)
from video_channel_manager.instagram.mp4_structure import (
    InstagramMp4VideoSampleEvidence,
    inspect_instagram_mp4_video_sample,
)


def _box(box_type: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), box_type) + payload


def _visual_sample_entry(entry_type: bytes, config_type: bytes, config_payload: bytes) -> bytes:
    return _box(entry_type, b"\x00" * 78 + _box(config_type, config_payload))


def _sample_table(entry: bytes) -> bytes:
    stsd = _box(b"stsd", b"\x00" * 4 + struct.pack(">I", 1) + entry)
    return _box(b"moov", _box(b"trak", _box(b"mdia", _box(b"minf", _box(b"stbl", stsd)))))


def _h264_access_unit(*nal_types: int, length_size: int = 4) -> bytes:
    payload = bytearray()
    for nal_type in nal_types:
        nal = bytes([0x60 | nal_type]) + b"payload"
        payload.extend(len(nal).to_bytes(length_size, "big"))
        payload.extend(nal)
    return bytes(payload)


def _hevc_access_unit(*nal_types: int, length_size: int = 4) -> bytes:
    payload = bytearray()
    for nal_type in nal_types:
        nal = bytes([(nal_type & 0x3F) << 1, 0x01]) + b"payload"
        payload.extend(len(nal).to_bytes(length_size, "big"))
        payload.extend(nal)
    return bytes(payload)


def _completed(frames: list[dict[str, object]]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["ffprobe"],
        returncode=0,
        stdout=json.dumps({"frames": frames}),
        stderr="",
    )


def test_mp4_video_sample_reads_avcc_nal_length_size(tmp_path: Path) -> None:
    avcc = bytearray(b"\x01\x64\x00\x28\xff")
    media = tmp_path / "avc.mp4"
    media.write_bytes(_sample_table(_visual_sample_entry(b"avc1", b"avcC", bytes(avcc))))

    evidence = inspect_instagram_mp4_video_sample(media)

    assert evidence.sample_entry_type == "avc1"
    assert evidence.codec == "h264"
    assert evidence.nal_length_size == 4


def test_mp4_video_sample_reads_hvcc_nal_length_size(tmp_path: Path) -> None:
    hvcc = bytearray(b"\x00" * 22)
    hvcc[21] = 0x03
    media = tmp_path / "hevc.mp4"
    media.write_bytes(_sample_table(_visual_sample_entry(b"hvc1", b"hvcC", bytes(hvcc))))

    evidence = inspect_instagram_mp4_video_sample(media)

    assert evidence.sample_entry_type == "hvc1"
    assert evidence.codec == "hevc"
    assert evidence.nal_length_size == 4


def test_closed_gop_h264_requires_every_i_picture_to_be_idr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _h264_access_unit(7, 8, 5)
    second = _h264_access_unit(5)
    media = tmp_path / "closed.mp4"
    media.write_bytes(b"prefix00" + first + second)

    monkeypatch.setattr(
        gop_module,
        "inspect_instagram_mp4_video_sample",
        lambda path: InstagramMp4VideoSampleEvidence("avc1", "h264", 4),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _completed(
            [
                {"pict_type": "I", "pkt_pos": 8, "pkt_size": len(first)},
                {"pict_type": "I", "pkt_pos": 8 + len(first), "pkt_size": len(second)},
                {"pict_type": "P", "pkt_pos": 0, "pkt_size": 1},
            ]
        ),
    )

    evidence = inspect_instagram_closed_gop(media, expected_codec="h264")

    assert evidence.closed_gop is True
    assert evidence.intra_frame_count == 2
    assert evidence.idr_frame_count == 2
    assert evidence.nal_length_size == 4


def test_open_gop_h264_rejects_non_idr_i_picture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _h264_access_unit(5)
    second = _h264_access_unit(1)
    media = tmp_path / "open.mp4"
    media.write_bytes(b"prefix00" + first + second)

    monkeypatch.setattr(
        gop_module,
        "inspect_instagram_mp4_video_sample",
        lambda path: InstagramMp4VideoSampleEvidence("avc1", "h264", 4),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _completed(
            [
                {"pict_type": "I", "pkt_pos": 8, "pkt_size": len(first)},
                {"pict_type": "I", "pkt_pos": 8 + len(first), "pkt_size": len(second)},
            ]
        ),
    )

    with pytest.raises(InstagramClosedGopError) as caught:
        inspect_instagram_closed_gop(media, expected_codec="h264")

    assert caught.value.reasons == ("non_idr_intra_frame:1",)


def test_hevc_cra_i_picture_is_not_accepted_as_closed_gop_idr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cra = _hevc_access_unit(21)
    media = tmp_path / "cra.mp4"
    media.write_bytes(b"prefix00" + cra)

    monkeypatch.setattr(
        gop_module,
        "inspect_instagram_mp4_video_sample",
        lambda path: InstagramMp4VideoSampleEvidence("hvc1", "hevc", 4),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _completed(
            [{"pict_type": "I", "pkt_pos": 8, "pkt_size": len(cra)}]
        ),
    )

    with pytest.raises(InstagramClosedGopError) as caught:
        inspect_instagram_closed_gop(media, expected_codec="hevc")

    assert caught.value.reasons == ("non_idr_intra_frame:0",)


def test_closed_gop_proof_fails_when_ffprobe_packet_location_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = tmp_path / "missing-pos.mp4"
    media.write_bytes(b"some-bytes")

    monkeypatch.setattr(
        gop_module,
        "inspect_instagram_mp4_video_sample",
        lambda path: InstagramMp4VideoSampleEvidence("avc1", "h264", 4),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _completed([{"pict_type": "I", "pkt_size": 10}]),
    )

    with pytest.raises(InstagramClosedGopError) as caught:
        inspect_instagram_closed_gop(media, expected_codec="h264")

    assert caught.value.reasons == ("intra_packet_location_missing:0",)
