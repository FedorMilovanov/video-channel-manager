from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.album_quality_cli as quality_cli


def test_bind_master_cli_reports_provider_free_exact_provenance(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = object()
    quality = SimpleNamespace(entries=(), quality_master_sha256="sha256:" + "a" * 64)
    entry = SimpleNamespace(
        ordinal=7,
        source_sha256="sha256:" + "b" * 64,
        master_path="/tmp/master-7.flac",
        master_sha256="sha256:" + "c" * 64,
        duration_seconds=408.04,
    )
    updated = SimpleNamespace(entries=(entry,), quality_master_sha256="sha256:" + "d" * 64)
    monkeypatch.setattr(quality_cli, "load_album_manifest", lambda path: manifest)
    monkeypatch.setattr(quality_cli, "quality_master_path_from_manifest_path", lambda path: Path("quality.json"))
    monkeypatch.setattr(quality_cli, "load_or_initialize_quality_master_manifest", lambda path, loaded: quality)

    def bind(
        loaded_manifest: object,
        loaded_quality: object,
        *,
        ordinal: int,
        path: Path,
        ffprobe: str,
    ) -> Any:
        assert loaded_manifest is manifest
        assert loaded_quality is quality
        assert ordinal == 7
        assert path == Path("master-7.flac")
        assert ffprobe == "ffprobe-custom"
        return updated

    monkeypatch.setattr(quality_cli, "bind_quality_master", bind)
    monkeypatch.setattr(quality_cli, "save_quality_master_manifest", lambda path, payload: updated)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "album_quality_cli",
            "--manifest",
            "manifest.json",
            "bind-master",
            "--track",
            "7",
            "--path",
            "master-7.flac",
            "--ffprobe",
            "ffprobe-custom",
        ],
    )

    assert quality_cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "bound": True,
        "track": 7,
        "source_sha256": entry.source_sha256,
        "master_path": entry.master_path,
        "master_sha256": entry.master_sha256,
        "duration_seconds": 408.04,
        "quality_master_sha256": updated.quality_master_sha256,
        "provider_write_performed": False,
    }


def test_validate_cli_requires_complete_master_set_without_provider_access(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = object()
    quality = SimpleNamespace(entries=(object(), object()), quality_master_sha256="sha256:" + "e" * 64)
    checked: list[bool] = []
    monkeypatch.setattr(quality_cli, "load_album_manifest", lambda path: manifest)
    monkeypatch.setattr(quality_cli, "quality_master_path_from_manifest_path", lambda path: Path("quality.json"))
    monkeypatch.setattr(quality_cli, "load_or_initialize_quality_master_manifest", lambda path, loaded: quality)
    monkeypatch.setattr(
        quality_cli,
        "require_complete_quality_masters",
        lambda loaded, masters, *, verify_bytes: checked.append(verify_bytes),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["album_quality_cli", "--manifest", "manifest.json", "validate", "--no-byte-check"],
    )

    assert quality_cli.main() == 0
    assert checked == [False]
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "valid": True,
        "track_count": 2,
        "quality_master_sha256": quality.quality_master_sha256,
        "provider_write_performed": False,
    }
