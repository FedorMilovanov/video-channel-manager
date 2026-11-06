from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from video_channel_manager.cli import youtube as youtube_cli
from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text


class ReadOnlyWriter:
    def __init__(self, description: str, *, channel_id: str = "channel-1") -> None:
        self.description = description
        self.channel_id = channel_id
        self.read_count = 0

    def read_description(self, video_id: str) -> SimpleNamespace:
        self.read_count += 1
        assert video_id == "video-1"
        return SimpleNamespace(
            video_id=video_id,
            channel_id=self.channel_id,
            title="Exact source video",
            description=self.description,
            revision="new-server-revision",
        )

    def replace_description(self, **kwargs: Any) -> None:
        raise AssertionError("read-only reconciliation must not dispatch videos.update")

    def restore_description_if_current(self, **kwargs: Any) -> None:
        raise AssertionError("read-only reconciliation must never roll back")


def _evidence_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    return (
        tmp_path / "signed-plan.json",
        tmp_path / "before-backup.json",
        tmp_path / "write-result.json",
        tmp_path / "new-readonly-report.json",
    )


def _plan(path: Path) -> dict[str, Any]:
    op = {
        "operation": "replace_video_description",
        "platform": "youtube",
        "ruleset": "readonly-test",
        "video_id": "video-1",
        "channel_id": "channel-1",
        "expected_revision": "previous-revision",
        "title": "Exact source video",
        "before_description": "Original description",
        "after_description": "Reviewed final description",
        "before_sha256": sha256_text("Original description"),
        "after_sha256": sha256_text("Reviewed final description"),
    }
    payload: dict[str, Any] = {
        "ruleset": "readonly-test",
        "target_channel_id": "channel-1",
        "source_audit_sha256": "sha256:source-audit",
        "videos_checked": 1,
        "operations_count": 1,
        "unresolved_error_videos": 0,
        "operations": [op],
        "unresolved": [],
    }
    finalize_copy_plan(payload, checked_video_ids=["video-1"])
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def _write_complete_receipts(plan_path: Path, backup_path: Path, result_path: Path, plan: dict[str, Any]) -> None:
    backup_path.write_text(
        json.dumps(
            {
                "schema_name": "video-manager.youtube-copy-backup",
                "channel_id": "channel-1",
                "account": "reader",
                "source_plan": str(plan_path),
                "operations": plan["operations"],
            }
        ),
        encoding="utf-8",
    )
    result_path.write_text(
        json.dumps(
            {
                "schema_name": "video-manager.youtube-copy-apply-result",
                "channel_id": "channel-1",
                "account": "reader",
                "source_plan": str(plan_path),
                "backup": str(backup_path),
                "status": "completed",
                "summary": {"postflight_verified": 1, "applied": 1, "attempted": 1},
                "attempted": [{"video_id": "video-1"}],
                "applied": [{"video_id": "video-1"}],
            }
        ),
        encoding="utf-8",
    )


def _run_reconcile(
    monkeypatch: pytest.MonkeyPatch,
    plan_path: Path,
    backup_path: Path,
    result_path: Path,
    report_path: Path,
    writer: ReadOnlyWriter,
) -> None:
    monkeypatch.setattr(youtube_cli, "require_lord_god_youtube_presentation", lambda _plan: None)
    monkeypatch.setattr(youtube_cli, "_writer_components", lambda *_args: (None, None, writer))
    youtube_cli.reconcile_copy_fixes(
        plan_path,
        backup=backup_path,
        result=result_path,
        account="reader",
        confirm_channel="channel-1",
        report_output=report_path,
        client_secret=None,
    )


def test_readonly_completed_receipt_and_live_after_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    plan = _plan(plan_path)
    _write_complete_receipts(plan_path, backup_path, result_path, plan)
    writer = ReadOnlyWriter("Reviewed final description\n")
    _run_reconcile(monkeypatch, plan_path, backup_path, result_path, report_path, writer)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "completed_live_verified"
    assert report["terminally_verified"] is True
    assert report["safe_to_replay"] is False
    assert report["provider_writes"] == 0
    assert report["rows"][0]["state"] == "live_after"
    assert writer.read_count == 1
    assert plan_path.exists() and backup_path.exists() and result_path.exists()


def test_missing_result_and_live_before_is_unknown_not_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    _plan(plan_path)
    writer = ReadOnlyWriter("Original description")
    with pytest.raises(typer.Exit) as exc:
        _run_reconcile(monkeypatch, plan_path, backup_path, result_path, report_path, writer)
    assert exc.value.exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "live_before_or_partial_unknown_no_replay"
    assert report["receipt_state"] == "missing"
    assert report["backup_state"] == "missing"
    assert report["safe_to_replay"] is False


def test_live_after_but_running_receipt_remains_not_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    plan = _plan(plan_path)
    _write_complete_receipts(plan_path, backup_path, result_path, plan)
    receipt = json.loads(result_path.read_text(encoding="utf-8"))
    receipt["status"] = "running"
    result_path.write_text(json.dumps(receipt), encoding="utf-8")
    writer = ReadOnlyWriter("Reviewed final description")
    with pytest.raises(typer.Exit) as exc:
        _run_reconcile(monkeypatch, plan_path, backup_path, result_path, report_path, writer)
    assert exc.value.exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "live_after_receipt_not_terminally_verified"
    assert report["receipt_state"] == "running"


def test_third_party_edit_blocks_reconciliation_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    plan = _plan(plan_path)
    _write_complete_receipts(plan_path, backup_path, result_path, plan)
    with pytest.raises(typer.Exit) as exc:
        _run_reconcile(monkeypatch, plan_path, backup_path, result_path, report_path, ReadOnlyWriter("Other editor"))
    assert exc.value.exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "manual_or_concurrent_description_conflict"
    assert report["rows"][0]["state"] == "live_third_state"


def test_mismatched_backup_evidence_blocks_before_owner_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    plan = _plan(plan_path)
    _write_complete_receipts(plan_path, backup_path, result_path, plan)
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    backup["operations"][0]["before_description"] = "Wrong source"
    backup_path.write_text(json.dumps(backup), encoding="utf-8")
    writer = ReadOnlyWriter("Reviewed final description")
    with pytest.raises(typer.Exit) as exc:
        _run_reconcile(monkeypatch, plan_path, backup_path, result_path, report_path, writer)
    assert exc.value.exit_code == 2
    assert writer.read_count == 0
    assert not report_path.exists()


def test_existing_readonly_report_is_never_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    plan = _plan(plan_path)
    _write_complete_receipts(plan_path, backup_path, result_path, plan)
    report_path.write_bytes(b"original evidence")
    writer = ReadOnlyWriter("Reviewed final description")
    with pytest.raises(typer.Exit) as exc:
        _run_reconcile(monkeypatch, plan_path, backup_path, result_path, report_path, writer)
    assert exc.value.exit_code == 2
    assert report_path.read_bytes() == b"original evidence"
    assert writer.read_count == 0


def test_completed_receipt_with_empty_backup_does_not_fake_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    plan = _plan(plan_path)
    _write_complete_receipts(plan_path, backup_path, result_path, plan)
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    backup["operations"] = []
    backup_path.write_text(json.dumps(backup), encoding="utf-8")
    writer = ReadOnlyWriter("Reviewed final description")
    with pytest.raises(typer.Exit) as exc:
        _run_reconcile(monkeypatch, plan_path, backup_path, result_path, report_path, writer)
    assert exc.value.exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "live_after_receipt_not_terminally_verified"
    assert report["terminally_verified"] is False
    assert report["safe_to_replay"] is False
