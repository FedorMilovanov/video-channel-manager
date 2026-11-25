"""A broken browser page must not erase capture failures or leak cleanup details."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from video_channel_manager.platforms.vk import milovi_d48_youtube_fallback as fallback
from video_channel_manager.platforms.vk import milovi_d48_youtube_overlay_clean as clean
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence as sequence
from video_channel_manager.platforms.vk import milovi_video_sequence_evidence_stable as stable


class BrokenPage:
    @property
    def url(self) -> str:
        raise RuntimeError("page already closed")

    def close(self) -> None:
        raise RuntimeError("sensitive browser url")


def _raise_capture(**kwargs: Any) -> Any:
    raise ValueError("capture failure")


def test_fallback_retains_capture_error_when_url_and_cleanup_also_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sequence, "_capture_page_sequence", _raise_capture)
    warning = Mock()
    monkeypatch.setattr(stable._LOGGER, "warning", warning)
    seed = SimpleNamespace(context=SimpleNamespace(new_page=BrokenPage))
    result, attempts, transport = fallback._capture_with_direct_transports(
        seed_page=seed, output_dir=tmp_path, wait_ms=1
    )
    assert result.status == "capture_error"
    assert result.error == "ValueError: capture failure"
    assert result.final_url == ""
    assert len(attempts) == 4
    assert transport is None
    assert warning.call_count == 4
    warning.assert_called_with("Could not close capture page (%s)", "RuntimeError")


def test_overlay_capture_retains_error_and_restores_monkeypatched_functions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sequence, "_capture_page_sequence", _raise_capture)
    original_find = sequence._find_video_handle
    original_seek = sequence._seek_video
    result, suppressions = clean._capture_one(
        page=BrokenPage(), url="https://example.test", output_dir=tmp_path, wait_ms=1
    )
    assert result.status == "capture_error"
    assert result.error == "ValueError: capture failure"
    assert result.final_url == ""
    assert suppressions == []
    assert sequence._find_video_handle is original_find
    assert sequence._seek_video is original_seek


def test_isolated_capture_cleanup_does_not_replace_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    capture = sequence.CaptureResult(
        status="captured",
        canonical_url="original",
        final_url="final",
        duration_s=1,
        video_width=1,
        video_height=1,
        frames=(),
        page_title="",
        block_hints=(),
    )
    monkeypatch.setattr(stable, "_ORIGINAL_CAPTURE", Mock(return_value=capture))
    warning = Mock()
    monkeypatch.setattr(stable._LOGGER, "warning", warning)
    seed = SimpleNamespace(context=SimpleNamespace(new_page=BrokenPage))
    result = stable._isolated_capture_page_sequence(
        page=seed, platform="other", expected_id="id", url="original", output_dir=tmp_path, wait_ms=1
    )
    assert result == capture
    warning.assert_called_once_with("Could not close capture page (%s)", "RuntimeError")


def test_overlay_transport_cleanup_is_reported_without_masking_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = sequence.CaptureResult(
        status="captured",
        canonical_url="original",
        final_url="final",
        duration_s=1,
        video_width=1,
        video_height=1,
        frames=(),
        page_title="",
        block_hints=(),
    )
    monkeypatch.setattr(clean, "_capture_one", Mock(return_value=(capture, [])))
    warning = Mock()
    monkeypatch.setattr(stable._LOGGER, "warning", warning)
    seed = SimpleNamespace(context=SimpleNamespace(new_page=BrokenPage))
    result, attempts, transport, _ = clean._capture_with_clean_transports(
        seed_page=seed, output_dir=tmp_path, wait_ms=1
    )
    assert result == capture
    assert len(attempts) == 1
    assert transport == "nocookie_embed"
    warning.assert_called_once_with("Could not close capture page (%s)", "RuntimeError")
