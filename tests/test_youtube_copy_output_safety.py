from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_channel_manager.cli.youtube import _write_json
from video_channel_manager.platforms.youtube import copy_output_safety
from video_channel_manager.platforms.youtube.copy_output_safety import (
    make_console_text_safe,
    reserve_youtube_copy_journals,
)


def test_legacy_windows_stream_does_not_crash_on_cyrillic_or_arrows() -> None:
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    make_console_text_safe(console)
    console.write("Backup → Алексей Коломийцев")
    console.flush()
    output = raw.getvalue().decode("cp1252")
    assert "Backup" in output
    assert r"\u2192" in output
    assert r"\u0410" in output


def test_reserve_journals_exclusively_and_never_overwrite(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    backup = tmp_path / "report" / "backup.json"
    result = tmp_path / "report" / "result.json"

    reserve_youtube_copy_journals(
        plan_path=plan, backup_output=backup, result_output=result, min_free_bytes=0
    )
    assert json.loads(backup.read_text(encoding="utf-8"))["provider_dispatch"] == "not_started"
    assert json.loads(result.read_text(encoding="utf-8"))["provider_dispatch"] == "not_started"

    existing_backup = backup.read_bytes()
    existing_result = result.read_bytes()
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        reserve_youtube_copy_journals(
            plan_path=plan, backup_output=backup, result_output=result, min_free_bytes=0
        )
    assert backup.read_bytes() == existing_backup
    assert result.read_bytes() == existing_result


@pytest.mark.parametrize("alias", ["plan", "backup"])
def test_reservation_rejects_colliding_output_paths(tmp_path: Path, alias: str) -> None:
    plan = tmp_path / "plan.json"
    backup = tmp_path / "backup.json"
    result = plan if alias == "plan" else backup

    with pytest.raises(ValueError, match="three different files"):
        reserve_youtube_copy_journals(
            plan_path=plan, backup_output=backup, result_output=result, min_free_bytes=0
        )
    assert not backup.exists()
    assert not plan.exists()


def test_existing_result_refuses_new_backup_without_mutation(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    backup = tmp_path / "backup.json"
    result = tmp_path / "result.json"
    result.write_bytes(b"previous successful result")

    with pytest.raises(FileExistsError, match="existing YouTube output"):
        reserve_youtube_copy_journals(
            plan_path=plan, backup_output=backup, result_output=result, min_free_bytes=0
        )
    assert not backup.exists()
    assert result.read_bytes() == b"previous successful result"


def test_near_full_disk_fails_closed_before_creating_any_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = tmp_path / "plan.json"
    backup = tmp_path / "backup.json"
    result = tmp_path / "result.json"
    monkeypatch.setattr(copy_output_safety.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))

    with pytest.raises(OSError, match="Insufficient free space"):
        reserve_youtube_copy_journals(
            plan_path=plan, backup_output=backup, result_output=result
        )
    assert not backup.exists()
    assert not result.exists()


def test_repeated_result_replacement_is_complete_and_leaves_no_tmp(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    result.write_text('{"provider_dispatch":"not_started"}', encoding="utf-8")
    for number in range(3):
        _write_json(result, {"status": "running", "attempts": number, "cyrillic": "Иов"})
    assert json.loads(result.read_text(encoding="utf-8")) == {
        "status": "running",
        "attempts": 2,
        "cyrillic": "Иов",
    }
    assert list(tmp_path.glob("*.tmp")) == []
