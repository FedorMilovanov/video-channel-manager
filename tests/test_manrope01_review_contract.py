"""Regression checks for the selected operator Manrope01/large-v3-CPU profile."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validate_manrope01_review import (
    ass_centiseconds,
    check_ass,
    check_asr_provenance,
    check_mp4_streams,
    verify,
)


_STYLE = """[Script Info]
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Style: Body,Manrope Q54,91,&H00F1FAFF&,&H00F1FAFF&,&H00211810&
Style: Kicker,Manrope Q54,32,&H007DE1FF&
Style: Title,Manrope Q54,73,&H00F1FAFF&
[Events]
Dialogue: 2,0:00:00.00,0:00:02.50,Kicker,,0000,0000,0000,,ДЖОН МАКАРТУР · ВОПРОСЫ И ОТВЕТЫ №54
Dialogue: 2,0:00:00.00,0:00:02.50,Title,,0000,0000,0000,,Особое искупление?
"""


def _body(start: str, end: str, *, payload: str = "") -> str:
    if not payload:
        payload = r"{\an5\pos(540,1426)}{\1c&H007DE1FF&}называли{\1c&H00F1FAFF&} бы его"
    return f"Dialogue: 1,{start},{end},Body,,0000,0000,0000,,{payload}\n"


def _healthy_ass() -> str:
    return _STYLE + _body("0:00:00.10", "0:00:00.40") + _body("0:00:00.40", "0:00:00.90")


def _asr() -> dict[str, object]:
    return {
        "model": "faster-whisper-large-v3",
        "device": "cpu",
        "compute_type": "int8",
        "source_id": "source-123",
        "segments": [{"start": 0.1, "end": 0.9, "text": "называли бы его"}],
    }


def _probe() -> dict[str, object]:
    return {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "179.87"},
    }


def test_manrope01_selected_style_and_adjoining_events_pass() -> None:
    assert check_ass(_healthy_ass()) == []
    assert ass_centiseconds("0:00:00.40") == 40


def test_manrope01_rejects_one_centisecond_overlap() -> None:
    bad = _STYLE + _body("0:00:00.10", "0:00:00.41") + _body("0:00:00.40", "0:00:00.90")
    assert any("Overlapping Body" in issue for issue in check_ass(bad))


def test_manrope01_rejects_missing_source_and_internal_index() -> None:
    bad = _healthy_ass().replace("ВОПРОСЫ И ОТВЕТЫ №54", "ВОПРОС 2 ИЗ 17")
    assert any("internal question index" in issue for issue in check_ass(bad))
    no_kicker = "\n".join(line for line in _healthy_ass().splitlines() if ",Kicker," not in line)
    assert any("Missing source attribution" in issue for issue in check_ass(no_kicker))


def test_manrope01_rejects_wrong_font_and_visual_anchor() -> None:
    bad = _healthy_ass().replace("Manrope Q54", "Arial").replace(r"\pos(540,1426)", r"\pos(540,900)")
    errors = check_ass(bad)
    assert any("Manrope" in issue for issue in errors)
    assert any("anchor" in issue for issue in errors)


def test_manrope01_rejects_incorrect_karaoke_palette_and_multiple_rows() -> None:
    bad = _healthy_ass().replace("&H007DE1FF&", "&H00FFFFFF&")
    bad = bad.replace("бы его", r"бы\Nего\Nлишнее")
    errors = check_ass(bad)
    assert any("amber" in issue for issue in errors)
    assert any("two lines" in issue for issue in errors)


def test_largev3_cpu_int8_provenance_fail_closed() -> None:
    assert check_asr_provenance(_asr()) == []
    for field, value in (("model", "small"), ("device", "cuda"), ("compute_type", "float16")):
        bad = _asr()
        bad[field] = value
        assert check_asr_provenance(bad), (field, value)


def test_final_streams_require_playable_h264_aac_and_short_duration() -> None:
    assert check_mp4_streams(_probe()) == []
    bad = _probe()
    bad["format"] = {"duration": "180.01"}
    assert any("duration" in error for error in check_mp4_streams(bad))
    bad = _probe()
    bad["streams"] = [{"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920}]
    assert any("AAC" in error for error in check_mp4_streams(bad))


def test_exact_files_fail_when_ffprobe_reports_missing_moov(tmp_path: Path, monkeypatch) -> None:
    ass = tmp_path / "review.ass"
    asr = tmp_path / "raw.json"
    mp4 = tmp_path / "review.mp4"
    ass.write_text(_healthy_ass(), encoding="utf8")
    asr.write_text(json.dumps(_asr()), encoding="utf8")
    mp4.write_bytes(b"invalid mp4 without moov")

    def reject(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["ffprobe"], stderr="moov atom not found")

    monkeypatch.setattr("scripts.validate_manrope01_review.subprocess.run", reject)
    assert any("Unusable MP4" in issue for issue in verify(ass, asr, mp4))



def test_exact_review_receipt_rejects_nul_json_and_hash_mismatch(
    tmp_path: Path, monkeypatch,
) -> None:
    ass = tmp_path / "q.ass"
    asr = tmp_path / "q_raw.json"
    video = tmp_path / "q.mp4"
    receipt = tmp_path / "q_qa.json"
    ass.write_text(_healthy_ass(), encoding="utf8")
    asr.write_text(json.dumps(_asr()), encoding="utf8")
    video.write_bytes(b"valid-probe-mocked-mp4")
    receipt.write_bytes(b"\x00" * 64)

    def ok(*_args, **_kwargs):
        return subprocess.CompletedProcess(["ffprobe"], 0, json.dumps(_probe()), "")

    monkeypatch.setattr("scripts.validate_manrope01_review.subprocess.run", ok)
    issues = verify(ass, asr, video, receipt=receipt)
    assert any("Invalid or corrupted review receipt" in issue for issue in issues)

    receipt.write_text(json.dumps({"sha256": "0" * 64, "subtitle_overlap_count": 0}), encoding="utf8")
    issues = verify(ass, asr, video, receipt=receipt)
    assert any("SHA-256 differs" in issue for issue in issues)
