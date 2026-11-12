from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from video_channel_manager.cli import youtube as youtube_cli
from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text
from video_channel_manager.platforms.youtube.writer import YouTubeWriteError

QUOTA_ERROR = (
    "YouTube API 403 in videos: The request cannot be completed because "
    'you have exceeded your <a href="/youtube/data/getting-started#quota">quota</a>. '
    "[kind=permanent_http attempts=1]"
)


class QuotaSimulationWriter:
    def __init__(self, *, fail_at: str) -> None:
        self.fail_at = fail_at
        self.replace_calls = 0
        self.restore_calls = 0

    def replace_description(self, **kwargs: Any) -> SimpleNamespace:
        self.replace_calls += 1
        if self.fail_at == "replace":
            # A PUT may have been accepted but its final response was ambiguous.
            raise YouTubeWriteError(QUOTA_ERROR)
        return SimpleNamespace(video_id=kwargs["video_id"], title="Original title", revision="new-revision")

    def restore_description_if_current(self, **_kwargs: Any) -> SimpleNamespace:
        self.restore_calls += 1
        return SimpleNamespace(revision="rolled-back-revision")


def _write_plan(path: Path) -> None:
    operation = {
        "operation": "replace_video_description",
        "platform": "youtube",
        "ruleset": "quota-recovery-regression",
        "video_id": "video-1",
        "channel_id": "channel-1",
        "title": "Original title",
        "expected_revision": "original-revision",
        "before_description": "Previous text",
        "after_description": "Source link and copyright",
        "before_sha256": sha256_text("Previous text"),
        "after_sha256": sha256_text("Source link and copyright"),
    }
    plan: dict[str, Any] = {
        "ruleset": "quota-recovery-regression",
        "target_channel_id": "channel-1",
        "source_audit_sha256": "sha256:test-evidence",
        "videos_checked": 1,
        "operations_count": 1,
        "unresolved_error_videos": 0,
        "operations": [operation],
        "unresolved": [],
    }
    finalize_copy_plan(plan, checked_video_ids=["video-1"])
    path.write_text(json.dumps(plan), encoding="utf-8")


def _run_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, fail_at: str
) -> tuple[QuotaSimulationWriter, dict[str, Any], Path, Path, Path]:
    plan = tmp_path / "signed-plan.json"
    backup = tmp_path / "backup.json"
    receipt = tmp_path / "receipt.json"
    _write_plan(plan)

    writer = QuotaSimulationWriter(fail_at=fail_at)
    store = SimpleNamespace(load_token=lambda _account: SimpleNamespace(scopes=[youtube_cli.YOUTUBE_FORCE_SSL_SCOPE]))
    monkeypatch.setattr(youtube_cli, "prepare_windows_youtube_console", lambda: None)
    monkeypatch.setattr(youtube_cli, "require_lord_god_youtube_presentation", lambda _plan: None)
    monkeypatch.setattr(youtube_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube_cli, "_writer_components", lambda *_args: (store, None, writer))
    monkeypatch.setattr(
        youtube_cli,
        "preflight_copy_operations",
        lambda operations, **_kwargs: SimpleNamespace(
            prepared=operations, already_applied=0, revision_drift_tolerated=0
        ),
    )

    def verify(*_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
        if fail_at == "postflight":
            raise YouTubeWriteError(QUOTA_ERROR)
        if fail_at == "nonquota":
            raise YouTubeWriteError("YouTube API 500 in videos: unexpected server failure")
        raise AssertionError("verify must not run after writer failure")

    monkeypatch.setattr(youtube_cli, "verify_copy_operations", verify)
    with pytest.raises(typer.Exit) as error:
        youtube_cli.apply_copy_fixes(
            plan=plan,
            account="writer",
            confirm_channel="channel-1",
            execute=True,
            max_operations=1,
            backup_output=backup,
            result_output=receipt,
            client_secret=None,
        )
    assert error.value.exit_code == 2
    assert backup.is_file() and receipt.is_file()
    return writer, json.loads(receipt.read_text(encoding="utf-8")), plan, backup, receipt


@pytest.mark.parametrize("failure_stage,applied_count", [("postflight", 1), ("replace", 0)])
def test_quota_does_not_attempt_rollback_after_provider_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str, applied_count: int
) -> None:
    writer, result, _, _, _ = _run_apply(tmp_path, monkeypatch, fail_at=failure_stage)
    assert writer.replace_calls == 1
    assert writer.restore_calls == 0
    assert result["status"] == "pending_reconciliation"
    assert result["summary"]["attempted"] == 1
    assert result["summary"]["applied"] == applied_count
    assert result["summary"]["rollback_failed"] == 0
    assert result["rollback"] == []
    assert "quota" in result["error"].casefold()


def test_nonquota_error_retains_existing_guarded_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer, result, _, _, _ = _run_apply(tmp_path, monkeypatch, fail_at="nonquota")
    assert writer.replace_calls == 1
    assert writer.restore_calls == 1
    assert result["status"] == "failed_rolled_back"
    assert result["summary"]["rollback_safe_original"] == 1


@pytest.mark.parametrize(
    "error,expected",
    [
        (YouTubeWriteError(QUOTA_ERROR), True),
        (YouTubeWriteError("YouTube API 403 in videos: dailyLimitExceeded"), True),
        (YouTubeWriteError("YouTube API 403 in videos: insufficientPermissions"), False),
        (YouTubeWriteError("YouTube API 500 in videos: quota message in logs"), False),
        (ValueError(QUOTA_ERROR), False),
    ],
)
def test_quota_detector_does_not_mask_other_provider_failures(
    error: BaseException, expected: bool
) -> None:
    assert youtube_cli._is_youtube_quota_exhaustion(error) is expected


def test_pending_quota_receipt_is_supported_for_read_only_owner_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = tmp_path / "signed-plan.json"
    backup = tmp_path / "backup.json"
    receipt = tmp_path / "receipt.json"
    report = tmp_path / "reconciled.json"
    _write_plan(plan)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    backup.write_text(
        json.dumps(
            {
                "schema_name": "video-manager.youtube-copy-backup",
                "source_plan": str(plan),
                "channel_id": "channel-1",
                "account": "writer",
                "operations": payload["operations"],
            }
        ),
        encoding="utf-8",
    )
    receipt.write_text(
        json.dumps(
            {
                "schema_name": "video-manager.youtube-copy-apply-result",
                "status": "pending_reconciliation",
                "source_plan": str(plan),
                "backup": str(backup),
                "channel_id": "channel-1",
                "account": "writer",
                "attempted": [{"video_id": "video-1"}],
                "applied": [{"video_id": "video-1"}],
                "summary": {"attempted": 1, "applied": 1, "postflight_verified": 0},
            }
        ),
        encoding="utf-8",
    )

    class ReadOnlyWriter:
        def read_description(self, video_id: str) -> SimpleNamespace:
            assert video_id == "video-1"
            return SimpleNamespace(
                video_id=video_id,
                channel_id="channel-1",
                title="Original title",
                description="Source link and copyright",
                revision="current-revision",
            )

        def replace_description(self, **_kwargs: Any) -> None:
            raise AssertionError("No provider writes during reconciliation")

    monkeypatch.setattr(youtube_cli, "_writer_components", lambda *_args: (None, None, ReadOnlyWriter()))
    with pytest.raises(typer.Exit) as outcome:
        youtube_cli.reconcile_copy_fixes(
            plan=plan,
            backup=backup,
            result=receipt,
            account="writer",
            confirm_channel="channel-1",
            report_output=report,
            client_secret=None,
        )
    assert outcome.value.exit_code == 2  # Never promote an incomplete receipt to completed.
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["receipt_state"] == "pending_reconciliation"
    assert evidence["rows"][0]["state"] == "live_after"
    assert evidence["outcome"] == "live_after_receipt_not_terminally_verified"
    assert evidence["safe_to_replay"] is False
    assert evidence["provider_writes"] == 0
