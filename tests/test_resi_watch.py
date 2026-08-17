from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import video_channel_manager.resi_watch as resi_watch_module
from video_channel_manager.cli.resi import (
    _background_watch_command,
    _render_handoff,
    _start_background_watch,
    resi_app,
)
from video_channel_manager.resi_handoff import ResiHandoffSpec, canonical_source_identity
from video_channel_manager.resi_watch import (
    ManifestObservation,
    PageProbeResult,
    ResiWatchAmbiguous,
    build_audio_probe_command,
    build_audio_sample_command,
    canonical_page_identity,
    create_audio_samples,
    extract_resi_player_id,
    is_resi_manifest_url,
    probe_audio_stream_count,
    source_fingerprint,
    watch_for_new_manifest,
)

RU_OLD = "https://resi.media/GiHDtf/a19407ff-e767-4a17-87d0-f3758bd87bfe/Manifest.mpd?src=emb"
RU_NEW = "https://resi.media/GiHDtf/e4335292-5fe8-4525-b6c0-845265e30192/Manifest.mpd?src=emb"
RU_NEXT = "https://resi.media/GiHDtf/11111111-2222-3333-4444-555555555555/Manifest.mpd?src=emb"
EN_NEW = "https://resi.media/HccRTy/f142475a-2c9b-48d0-bd75-c3be730ca14c/Manifest.mpd?src=emb"
RU_PAGE = "https://www.gracechurch.org/live?language=russian"
EN_PAGE = "https://www.gracechurch.org/live?language=english"
RU_FRAME = "https://control.resi.io/webplayer/video.html?id=52260827-f6e9-4a2e-8978-aed53dbf1413"
EN_FRAME = "https://control.resi.io/webplayer/video.html?id=8fd0d098-1c9e-4580-9f8a-3c8cc57d1624"
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def plain_help(value: str) -> str:
    return ANSI_RE.sub("", value)


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


def write_state(path: Path, *, page: str, manifest: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_name": "video-manager.resi-watch-state",
                "schema_version": 2,
                "target_page_url": page,
                "target_page_identity": canonical_page_identity(page),
                "last_source_identity": canonical_source_identity(manifest),
                "last_manifest_url": manifest,
            }
        ),
        encoding="utf-8",
    )


def test_canonical_page_identity_preserves_language_query_and_ignores_fragment() -> None:
    assert canonical_page_identity(RU_PAGE + "#player") == RU_PAGE
    assert canonical_page_identity("HTTPS://WWW.GRACECHURCH.ORG/live?language=russian") == RU_PAGE
    assert canonical_page_identity(RU_PAGE) != canonical_page_identity(EN_PAGE)
    with pytest.raises(ValueError, match="absolute http"):
        canonical_page_identity("/live?language=russian")


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
    assert persisted["schema_version"] == 2
    assert persisted["target_page_identity"] == canonical_page_identity(RU_PAGE)
    assert persisted["target"]["page_url"] == RU_PAGE
    assert persisted["target"]["player_id"] == "52260827-f6e9-4a2e-8978-aed53dbf1413"
    assert persisted["compare"]["observation"]["manifest_url"] == EN_NEW
    assert persisted["compare"]["observation"]["player_id"] == "8fd0d098-1c9e-4580-9f8a-3c8cc57d1624"
    assert persisted["language_claim"] == "unverified"
    assert persisted["full_download_dispatched"] is False
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    assert state_payload["schema_version"] == 2
    assert state_payload["target_page_identity"] == canonical_page_identity(RU_PAGE)
    assert state_payload["last_source_identity"] == canonical_source_identity(RU_NEW)


def test_watch_uses_page_scoped_persisted_identity_as_restart_baseline(tmp_path: Path) -> None:
    state = tmp_path / "resi-watch-state.json"
    write_state(state, page=RU_PAGE, manifest=RU_NEW)
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


def test_watch_refuses_cross_page_state_reuse(tmp_path: Path) -> None:
    state = tmp_path / "resi-watch-state.json"
    write_state(state, page=EN_PAGE, manifest=EN_NEW)

    with pytest.raises(RuntimeError, match="different target page"):
        watch_for_new_manifest(
            RU_PAGE,
            known_manifest=None,
            compare_page=None,
            timeout_seconds=30,
            poll_seconds=1,
            probe_wait_seconds=1,
            latest_txt=tmp_path / "latest.txt",
            latest_json=tmp_path / "latest.json",
            state_path=state,
            probe=lambda _page, _wait: PageProbeResult(RU_PAGE, RU_PAGE, ()),
        )


def test_watch_refuses_legacy_unscoped_state(tmp_path: Path) -> None:
    state = tmp_path / "resi-watch-state.json"
    state.write_text(json.dumps({"last_source_identity": canonical_source_identity(RU_NEW)}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="legacy/unscoped"):
        watch_for_new_manifest(
            RU_PAGE,
            known_manifest=RU_NEW,
            compare_page=None,
            timeout_seconds=30,
            poll_seconds=1,
            probe_wait_seconds=1,
            latest_txt=tmp_path / "latest.txt",
            latest_json=tmp_path / "latest.json",
            state_path=state,
            probe=lambda _page, _wait: PageProbeResult(RU_PAGE, RU_PAGE, ()),
        )


def test_watch_tolerates_transient_probe_errors_within_configured_budget(tmp_path: Path) -> None:
    calls = [0]

    def probe(_page: str, _wait: float) -> PageProbeResult:
        calls[0] += 1
        if calls[0] <= 4:
            raise OSError("temporary network failure")
        return PageProbeResult(RU_PAGE, RU_PAGE, (observation(RU_PAGE, RU_NEW, RU_FRAME),))

    clock = [0.0]
    payload = watch_for_new_manifest(
        RU_PAGE,
        known_manifest=RU_OLD,
        compare_page=None,
        timeout_seconds=30,
        poll_seconds=1,
        probe_wait_seconds=1,
        max_consecutive_probe_errors=5,
        latest_txt=tmp_path / "latest.txt",
        latest_json=tmp_path / "latest.json",
        state_path=tmp_path / "state.json",
        probe=probe,
        monotonic=lambda: clock[0],
        sleeper=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    assert calls[0] == 5
    assert payload["target"]["manifest_url"] == RU_NEW


def test_watch_fails_at_configured_probe_error_budget(tmp_path: Path) -> None:
    def always_fail(_page: str, _wait: float) -> PageProbeResult:
        raise OSError("offline")

    clock = [0.0]
    with pytest.raises(RuntimeError, match="4 consecutive Resi page probes failed"):
        watch_for_new_manifest(
            RU_PAGE,
            known_manifest=RU_OLD,
            compare_page=None,
            timeout_seconds=30,
            poll_seconds=1,
            probe_wait_seconds=1,
            max_consecutive_probe_errors=4,
            latest_txt=tmp_path / "latest.txt",
            latest_json=tmp_path / "latest.json",
            state_path=tmp_path / "state.json",
            probe=always_fail,
            monotonic=lambda: clock[0],
            sleeper=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        )


def test_watch_fails_closed_when_target_page_exposes_multiple_distinct_manifests(tmp_path: Path) -> None:
    result = PageProbeResult(
        RU_PAGE,
        RU_PAGE,
        (
            observation(RU_PAGE, RU_NEW, RU_FRAME),
            observation(RU_PAGE, RU_NEXT, RU_FRAME),
        ),
    )

    with pytest.raises(ResiWatchAmbiguous, match="multiple distinct new Resi manifests"):
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


def test_audio_probe_command_is_audio_only_metadata_inspection() -> None:
    command = build_audio_probe_command(RU_NEW)
    assert command[0] == "ffprobe"
    assert command[command.index("-select_streams") + 1] == "a"
    assert command[-1] == RU_NEW
    assert "yt-dlp" not in command


def test_audio_stream_count_parses_ffprobe_json(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = subprocess.CompletedProcess(
        args=["ffprobe"],
        returncode=0,
        stdout=json.dumps({"streams": [{"index": 1}]}),
        stderr="",
    )
    monkeypatch.setattr(resi_watch_module.subprocess, "run", lambda *args, **kwargs: completed)
    assert probe_audio_stream_count(RU_NEW) == 1


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


def test_create_audio_samples_fails_closed_when_multiple_audio_streams_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(resi_watch_module.shutil, "which", lambda _tool: "tool.exe")
    monkeypatch.setattr(resi_watch_module, "probe_audio_stream_count", lambda _url: 2)

    with pytest.raises(RuntimeError, match="exactly one audio stream"):
        create_audio_samples(
            RU_NEW,
            points=["50:00"],
            duration_seconds=45,
            output_dir=tmp_path / "samples",
        )


def test_create_audio_samples_persists_single_audio_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resi_watch_module.shutil, "which", lambda _tool: "tool.exe")
    monkeypatch.setattr(resi_watch_module, "probe_audio_stream_count", lambda _url: 1)

    def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        assert check is False
        Path(command[-1]).write_bytes(b"x" * 5000)
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr(resi_watch_module.subprocess, "run", fake_run)
    output_dir = tmp_path / "samples"
    outputs = create_audio_samples(
        RU_NEW,
        points=["50:00"],
        duration_seconds=45,
        output_dir=output_dir,
    )

    assert len(outputs) == 1
    index = json.loads((output_dir / "samples.json").read_text(encoding="utf-8"))
    assert index["schema_version"] == 2
    assert index["audio_stream_count"] == 1
    assert index["audio_selection_contract"] == "single_audio_stream_only"


def test_create_audio_samples_rejects_header_only_or_premature_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(resi_watch_module.shutil, "which", lambda _tool: "tool.exe")
    monkeypatch.setattr(resi_watch_module, "probe_audio_stream_count", lambda _url: 1)

    def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        assert check is False
        Path(command[-1]).write_bytes(b"tiny")
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr(resi_watch_module.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="empty or too small"):
        create_audio_samples(
            RU_NEW,
            points=["90:00"],
            duration_seconds=45,
            output_dir=tmp_path / "samples",
        )


def test_background_watch_command_does_not_recurse_and_preserves_inputs(tmp_path: Path) -> None:
    command = _background_watch_command(
        page_url=RU_PAGE,
        known_manifest=RU_OLD,
        compare_page=EN_PAGE,
        timeout_seconds=10800,
        poll_seconds=30,
        probe_wait_seconds=12,
        max_consecutive_probe_errors=10,
        latest_txt=tmp_path / "latest.txt",
        capture_json=tmp_path / "capture.json",
        state=tmp_path / "state.json",
    )

    assert command[:5] == [command[0], "-u", "-m", "video_channel_manager.cli.resi", "watch"]
    assert "--background" not in command
    assert RU_PAGE in command
    assert RU_OLD in command
    assert EN_PAGE in command
    assert "--max-consecutive-probe-errors" in command


def test_background_launcher_survives_startup_then_writes_pid(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []
    sleeps: list[float] = []

    class FakeProcess:
        pid = 4242

        def poll(self) -> None:
            return None

    def fake_popen(command: list[str], **kwargs: Any) -> FakeProcess:
        calls.append({"command": command, **kwargs})
        return FakeProcess()

    log_path = tmp_path / "watch.log"
    pid_path = tmp_path / "watch.pid"
    pid = _start_background_watch(
        ["python", "watch"],
        repository_root=tmp_path,
        log_path=log_path,
        pid_path=pid_path,
        platform_name="nt",
        popen_factory=fake_popen,
        startup_wait_seconds=1.25,
        sleeper=sleeps.append,
    )

    assert pid == 4242
    assert sleeps == [1.25]
    assert pid_path.read_text(encoding="utf-8").strip() == "4242"
    assert log_path.is_file()
    assert calls[0]["stdin"] is subprocess.DEVNULL
    assert calls[0]["stderr"] == subprocess.STDOUT
    assert calls[0]["cwd"] == tmp_path


def test_background_launcher_fails_if_child_exits_during_startup(tmp_path: Path) -> None:
    class ExitedProcess:
        pid = 5151

        def poll(self) -> int:
            return 2

    with pytest.raises(RuntimeError, match="exited during startup with code 2"):
        _start_background_watch(
            ["python", "watch"],
            repository_root=tmp_path,
            log_path=tmp_path / "watch.log",
            pid_path=tmp_path / "watch.pid",
            platform_name="nt",
            popen_factory=lambda *args, **kwargs: ExitedProcess(),
            startup_wait_seconds=0,
            sleeper=lambda _seconds: None,
        )

    assert not (tmp_path / "watch.pid").exists()


def test_language_confirmed_handoff_injects_single_audio_gate_only_when_requested() -> None:
    spec = ResiHandoffSpec(RU_NEW)
    ordinary = _render_handoff(spec, require_single_audio=False)
    guarded = _render_handoff(spec, require_single_audio=True)

    assert "Language-confirmed FULL download requires exactly one source audio stream" not in ordinary
    assert "Language-confirmed FULL download requires exactly one source audio stream" in guarded
    assert "-rw_timeout 30000000" in guarded
    assert guarded.index("Verifying source has exactly one audio stream") < guarded.index("Available DASH formats")
    assert guarded.index("Available DASH formats") < guarded.index("Downloading best video + best audio")


def test_resi_cli_registers_watch_sample_and_handoff() -> None:
    result = CliRunner().invoke(resi_app, ["--help"], color=False)
    output = plain_help(result.stdout)
    assert result.exit_code == 0
    assert "watch" in output
    assert "sample" in output
    assert "handoff" in output


def test_resi_watch_registers_unattended_controls() -> None:
    from typer.main import get_command

    root_command = get_command(resi_app)
    watch_command = root_command.commands["watch"]
    option_names = {option for parameter in watch_command.params for option in getattr(parameter, "opts", ())}
    assert "--background" in option_names
    assert "--max-consecutive-probe-errors" in option_names


def test_resi_handoff_help_exposes_language_audio_gate() -> None:
    result = CliRunner().invoke(resi_app, ["handoff", "--help"], color=False)
    output = plain_help(result.stdout)
    assert result.exit_code == 0
    assert "--require-single-audio" in output
