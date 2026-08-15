from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from video_channel_manager.cli.vk import vk_app
from video_channel_manager.platforms.vk import milovi_issue323_status_probe as status_probe

runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def test_milovi_323_status_calls_read_only_probe_with_exact_paths(monkeypatch: Any, tmp_path: Path) -> None:
    output = tmp_path / "status.json"
    journal = tmp_path / "journal.json"
    schedule = tmp_path / "schedule.json"
    prepared = tmp_path / "prepared.json"
    observed: dict[str, Path] = {}

    def fake_probe(
        *,
        output_path: Path,
        journal_path: Path,
        schedule_path: Path,
        prepared_manifest_path: Path,
    ) -> dict[str, Any]:
        observed.update(
            output=output_path,
            journal=journal_path,
            schedule=schedule_path,
            prepared=prepared_manifest_path,
        )
        return {
            "status": "verified_read_only",
            "first_action_source_id": "1_SuzeQD_1g",
            "first_safe_next_action": "resume_from_verified_clip_without_reupload_then_wall",
        }

    monkeypatch.setattr(status_probe, "run_issue_323_status_probe", fake_probe)

    result = runner.invoke(
        vk_app,
        [
            "milovi-323-status",
            "--output",
            str(output),
            "--journal",
            str(journal),
            "--schedule",
            str(schedule),
            "--prepared-manifest",
            str(prepared),
        ],
    )

    assert result.exit_code == 0, result.output
    assert observed == {
        "output": output,
        "journal": journal,
        "schedule": schedule,
        "prepared": prepared,
    }
    assert "verified_read_only" in result.output
    assert "1_SuzeQD_1g:resume_from_verified_clip_without_reupload_then_wall" in result.output
    assert "provider-writes=0" in result.output


def test_milovi_323_status_fails_closed(monkeypatch: Any, tmp_path: Path) -> None:
    def blocked_probe(**_kwargs: Any) -> dict[str, Any]:
        raise status_probe.MiloviStatusProbeBlocked("exact live state conflict")

    monkeypatch.setattr(status_probe, "run_issue_323_status_probe", blocked_probe)

    result = runner.invoke(
        vk_app,
        [
            "milovi-323-status",
            "--output",
            str(tmp_path / "status.json"),
            "--journal",
            str(tmp_path / "journal.json"),
            "--schedule",
            str(tmp_path / "schedule.json"),
            "--prepared-manifest",
            str(tmp_path / "prepared.json"),
        ],
    )

    assert result.exit_code == 3
    assert "STOP: MiloviStatusProbeBlocked: exact live state conflict" in result.output


def test_milovi_323_status_cli_exposes_no_write_confirmation_flags() -> None:
    result = runner.invoke(vk_app, ["milovi-323-status", "--help"])
    plain_help = _ANSI_ESCAPE.sub("", result.output)

    assert result.exit_code == 0, result.output
    assert "--execute" not in plain_help
    assert "--confirm" not in plain_help
    assert "--output" in plain_help
    assert "--journal" in plain_help
    assert "--schedule" in plain_help
    assert "--prepared-manifest" in plain_help
