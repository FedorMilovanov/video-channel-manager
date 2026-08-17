from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from video_channel_manager.cli.resi import resi_app
from video_channel_manager.resi_watch import (
    ManifestObservation,
    PageProbeResult,
    ResiWatchAmbiguous,
    build_audio_sample_command,
    extract_resi_player_id,
    is_resi_manifest_url,
    source_fingerprint,
    watch_for_new_manifest,
)
from video_channel_manager.resi_handoff import canonical_source_identity

RU_OLD = "https://resi.media/GiHDtf/a19407ff-e767-4a17-87d0-f3758bd87bfe/Manifest.mpd?src=emb"
RU_NEW = "https://resi.media/GiHDtf/e4335292-5fe8-4525-b6c0-845265e30192/Manifest.mpd?src=emb"
RU_NEXT = "https://resi.media/GiHDtf/11111111-2222-3333-4444-555555555555/Manifest.mpd?src=emb"
EN_NEW = "https://resi.media/HccRTy/f142475a-2c9b-48d0-bd75-c3be730ca14c/Manifest.mpd?src=emb"
RU_PAGE = "https://www.gracechurch.org/live?language=russian"
EN_PAGE = "https://www.gracechurch.org/live?language=english"
RU_FRAME = "https://control.resi.io/webplayer/video.html?id=52260827-f6e9-4a2e-8978-aed53dbf1413"
EN_FRAME = "https://control.resi.io/webplayer/video.html?id=8fd0d098-1c9e-4580-9f8a-3c8cc57d1624"


def observation(page: str, manifest: str, frame: str) -> ManifestObservation:
    return ManifestObservation(
        page_url=page,
        final_page_url=page,
        manifest_url=manifest,
        source_identity=canonical_source_identity(manifest),
        source_fingerprint=source_fingerprint(manifest),
        frame_url=frame,
        player_id=extract_resi_player_id(frame),
    )


def test_resi_manifest_filter_is_strict_and_ignores_segments() -> None:
    assert is_resi_manifest_url(RU_NEW)
    assert is_resi_manifest_url(RU_NEW.replace("resi.media", "edge.resi.media"))
    assert not is_resi_manifest_url(RU_NEW.replace("https://", "http://"))
    assert not is_resi_manifest_url("https://resi.media/GiHDtf/id/chunk-stream0-00001.m4s")
    assert not is_resi_manifest_url("https://example.com/GiHDtf/id/Manifest.mpd")


def test_extracts_exact_resi_player_id_only_from_control_player() -> None:
    assert extract_resi_player_id(RU_FRAME) == "52260827-f6e9-4a2e-8978-aed53dbf1413"
    assert extract_resi_player_id("https://example.com/webplayer/video.html?id=wrong") is None
    assert extract_resi_player_id(None) is None


def test_watch_ignores_known_russian_source_then_persists_new_capture_and_english_comparison(tmp_path: Path) -> None:
    target_results = iter(
        [
            PageProbeResult(RU_PAGE, RU_PAGE, (observation(RU_PAGE, RU_OLD, RU_FRAME),)),
            PageProbeResult(RU_PAGE, RU_PAGE, (observation(RU_PAGE, RU_NEW, RU_FRAME),)),
        ]
    )

    def probe(page: str, wait_seconds: float) -> PageProbeResult:
        assert wait_seconds == 1
        if page == EN_PAGE:
            return PageProbeResult(EN_PAGE, EN_PAGE, (observation(EN_PAGE, EN_NEW, EN_FRAME),))
        return next(target_results)

    clock = [0.0]
    latest_txt = tmp_path / "latest-resi-manifest.txt"
    latest_json = tmp_path / "latest-resi-manifest.json"
    state = tmp_path / "resi-watch-state.json"

    payload = watch_for_new_manifest(
        RU_PAGE,
        known_manifest=RU_OLD,
        compare_page=EN_PAGE,
        timeout_seconds=30,
        poll_seconds=2,
        probe_wait_seconds=1,
        latest_txt=latest_txt,
        latest_json=latest_json,
        state_path=state,
        probe=probe,
        monotonic=lambda: clock[0],
        sleeper=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    assert latest_txt.read_text(encoding="utf-8").strip() == RU_NEW
    persisted = json.loads(latest_json.read_text(encoding="utf-8"))
    assert persisted == payload
    assert persisted["target"]["page_url"] == RU_PAGE
    assert persisted["target"]["player_id"] == "52260827-f6e9-4a2e-8978-aed53dbf1413"
    assert persisted["compare"]["observation"]["manifest_url"] == EN_NEW
    assert persisted["compare"]["observation"]["player_id"] == "8fd0d098-1c9e-4580-9f8a-3c8cc57d1624"
    assert persisted["language_claim"] == "unverified"
    assert persisted["full_download_dispatched"] is False
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    assert state_payload["last_source_identity"] == canonical_source_identity(RU_NEW)


def test_watch_uses_persisted_identity_as_restart_baseline(tmp_path: Path) -> None:
    state = tmp_path / "resi-watch-state.json"
    state.write_text(json.dumps({"last_source_identity": canonical_source_identity(RU_NEW)}), encoding="utf-8")
    results = iter(
        [
            PageProbeResult(RU_PAGE, RU_PAGE, (observation(RU_PAGE, RU_NEW, RU_FRAME),)),
            PageProbeResult(RU_PAGE, RU_PAGE, (observation(RU_PAGE, RU_NEXT, RU_FRAME),)),
        ]
    )
    clock = [0.0]

    payload = watch_for_new_manifest(
        RU_PAGE,
        known_manifest=None,
        compare_page=None,
        timeout_seconds=30,
        poll_seconds=1,
        probe_wait_seconds=1,
        latest_txt=tmp_path / "latest.txt",
        latest_json=tmp_path / "latest.json",
        state_path=state,
        probe=lambda _page, _wait: next(results),
        monotonic=lambda: clock[0],
        sleeper=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    assert payload["target"]["manifest_url"] == RU_NEXT


def test_watch_fails_closed_when_target_page_exposes_multiple_distinct_manifests(tmp_path: Path) -> None:
    result = PageProbeResult(
        RU_PAGE,
        RU_PAGE,
        (
            observation(RU_PAGE, RU_NEW, RU_FRAME),
            observation(RU_PAGE, RU_NEXT, RU_FRAME),
        ),
    )

    with pytest.raises(ResiWatchAmbiguous, match="multiple distinct Resi manifests"):
        watch_for_new_manifest(
            RU_PAGE,
            known_manifest=RU_OLD,
            compare_page=None,
            timeout_seconds=1,
            poll_seconds=1,
            probe_wait_seconds=1,
            latest_txt=tmp_path / "latest.txt",
            latest_json=tmp_path / "latest.json",
            state_path=tmp_path / "state.json",
            probe=lambda _page, _wait: result,
        )


def test_audio_sample_command_is_bounded_audio_only_and_never_full_download(tmp_path: Path) -> None:
    output = tmp_path / "sample.m4a"
    command = build_audio_sample_command(RU_NEW, at="70:00", duration_seconds=45, output_path=output)

    assert command[0] == "ffmpeg"
    assert command[command.index("-ss") + 1] == "01:10:00"
    assert command[command.index("-t") + 1] == "45"
    assert command[command.index("-map") + 1] == "0:a:0"
    assert "-vn" in command
    assert "yt-dlp" not in command
    assert "h264_nvenc" not in command
    assert str(output) == command[-1]


def test_resi_cli_registers_watch_sample_and_handoff() -> None:
    result = CliRunner().invoke(resi_app, ["--help"])
    assert result.exit_code == 0
    assert "watch" in result.stdout
    assert "sample" in result.stdout
    assert "handoff" in result.stdout
