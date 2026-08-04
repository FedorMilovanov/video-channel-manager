from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from video_channel_manager.wave_engine.canonical import write_json_atomic


canonical_module = importlib.import_module("video_channel_manager.wave_engine.canonical")


def test_interrupted_atomic_replace_preserves_previous_file_and_removes_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "result.json"
    write_json_atomic(target, {"status": "previous"})
    previous = target.read_bytes()

    def fail_replace(source: object, destination: object) -> None:
        raise OSError(f"replace interrupted: {source!s} -> {destination!s}")

    monkeypatch.setattr(canonical_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace interrupted"):
        canonical_module.write_json_atomic(target, {"status": "new"})

    assert target.read_bytes() == previous
    assert list(tmp_path.glob(".result.json.*.tmp")) == []
