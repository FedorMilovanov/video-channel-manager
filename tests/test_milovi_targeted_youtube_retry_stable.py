from __future__ import annotations

from pathlib import Path
from typing import Any

from video_channel_manager.platforms.vk import milovi_targeted_youtube_retry as base_retry
from video_channel_manager.platforms.vk import milovi_targeted_youtube_retry_stable as retry_stable
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable_sequence


def test_stable_identity_accepts_exact_local_youtube_capture_url() -> None:
    assert stable_sequence._stable_identity_url_matches(
        platform="youtube",
        expected_id="d48QLgOuiTs",
        raw_url="http://127.0.0.1:8765/youtube/d48QLgOuiTs",
    )
    assert not stable_sequence._stable_identity_url_matches(
        platform="youtube",
        expected_id="d48QLgOuiTs",
        raw_url="http://127.0.0.1:8765/youtube/uA8SbnXzJJc",
    )


def test_wrapper_installs_and_restores_stable_identity(monkeypatch, tmp_path: Path) -> None:
    original_identity = sequence._identity_url_matches
    observed: dict[str, Any] = {}

    def fake_build_targeted_retry(**kwargs: Any) -> dict[str, Any]:
        observed["identity"] = sequence._identity_url_matches
        observed["kwargs"] = kwargs
        return {"status": "completed"}

    monkeypatch.setattr(base_retry, "build_targeted_retry", fake_build_targeted_retry)

    result = retry_stable.build_targeted_retry(
        input_zip=tmp_path / "probe.zip",
        output_dir=tmp_path / "out",
        zip_output=tmp_path / "out.zip",
        browser_executable=tmp_path / "browser.exe",
        headless=True,
        wait_ms=1000,
    )

    assert result == {"status": "completed"}
    assert observed["identity"] is stable_sequence._stable_identity_url_matches
    assert sequence._identity_url_matches is original_identity
    assert observed["kwargs"] == {
        "input_zip": tmp_path / "probe.zip",
        "output_dir": tmp_path / "out",
        "zip_output": tmp_path / "out.zip",
        "browser_executable": tmp_path / "browser.exe",
        "headless": True,
        "wait_ms": 1000,
    }
