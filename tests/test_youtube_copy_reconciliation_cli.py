from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from video_channel_manager.cli import youtube as youtube_cli
from video_channel_manager.platforms.youtube.copy_plan import finalize_copy_plan, sha256_text
from video_channel_manager.platforms.youtube.lord_god_presentation import (
    LORD_GOD_OWNER_CHANNEL,
    require_lord_god_youtube_presentation,
)


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


def test_readonly_reconciles_valid_archived_lord_god_plan_rejected_by_new_publish_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path, backup_path, result_path, report_path = _evidence_paths(tmp_path)
    plan = _plan(plan_path)
    operation = plan["operations"][0]
    plan["target_channel_id"] = LORD_GOD_OWNER_CHANNEL
    plan["project_key"] = "lord-god-strength"
    plan["link_profile"] = "lord-god-strength"
    operation["channel_id"] = LORD_GOD_OWNER_CHANNEL
    operation["before_description"] = "Original material: https://t.me/lordchrist/626"
    operation["after_description"] = "The old published text omitted the archival source."
    operation["before_sha256"] = sha256_text(operation["before_description"])
    operation["after_sha256"] = sha256_text(operation["after_description"])
    finalize_copy_plan(plan, checked_video_ids=["video-1"])
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="original_source_or_related_link_not_preserved"):
        require_lord_god_youtube_presentation(plan)

    writer = ReadOnlyWriter(operation["after_description"], channel_id=LORD_GOD_OWNER_CHANNEL)
    monkeypatch.setattr(youtube_cli, "_writer_components", lambda *_args: (None, None, writer))
    with pytest.raises(typer.Exit) as outcome:
        youtube_cli.reconcile_copy_fixes(
            plan_path,
            backup=backup_path,
            result=result_path,
            account="reader",
            confirm_channel=LORD_GOD_OWNER_CHANNEL,
            report_output=report_path,
            client_secret=None,
        )
    assert outcome.value.exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "live_after_receipt_not_terminally_verified"
    assert report["rows"][0]["state"] == "live_after"
    assert report["safe_to_replay"] is False
    assert report["provider_writes"] == 0
    assert writer.read_count == 1


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


def test_playlist_rename_reconciles_exact_pending_effect_without_second_put(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    from video_channel_manager.youtube_release_provider import ReleaseProviderResult

    channel = "UC-78ys2S3cQ3lpqgXfo-SvQ"
    account = "legendary-poet"
    current: dict[str, Any] = {
        "id": "playlist-1",
        "snippet": {"channelId": channel, "title": "Old", "description": "Keep"},
        "status": {"privacyStatus": "public"},
        "localizations": {},
    }
    api = Mock()
    api.list_my_channels.return_value = [SimpleNamespace(ref=SimpleNamespace(channel_id=channel))]
    provider = Mock()
    provider.read_playlist_metadata.side_effect = lambda *_args, **_kwargs: current

    def ambiguous(**kwargs: Any) -> ReleaseProviderResult:
        kwargs["before_dispatch"]()
        return ReleaseProviderResult(provider_effect="may_exist")

    provider.rename_playlist.side_effect = ambiguous
    monkeypatch.setattr(youtube_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube_cli, "_components", lambda *_args: (None, None, api))
    monkeypatch.setattr(youtube_cli, "YouTubeReleaseProvider", lambda **_kwargs: provider)

    def run(*, execute: bool) -> None:
        youtube_cli.rename_playlist(
            "playlist-1",
            account=account,
            confirm_channel=channel,
            title="New",
            execute=execute,
            client_secret=None,
        )

    run(execute=False)
    assert not list((tmp_path / "reports").glob("*.json"))
    for _ in range(2):
        with pytest.raises(typer.Exit):
            run(execute=True)
    provider.rename_playlist.assert_called_once()
    journal = next((tmp_path / "reports").glob("*.json"))
    assert json.loads(journal.read_text(encoding="utf-8"))["status"] == "pending_reconciliation"
    current["snippet"]["title"] = "New"
    run(execute=True)
    provider.rename_playlist.assert_called_once()
    assert json.loads(journal.read_text(encoding="utf-8"))["status"] == "verified"


@pytest.mark.parametrize("outcome", ["list", "download", "foreign_video", "foreign_track", "existing_file"])
def test_caption_cli_exact_owner_inventory_and_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    from unittest.mock import Mock

    channel = "UC-78ys2S3cQ3lpqgXfo-SvQ"
    api = Mock()
    api.list_my_channels.return_value = [SimpleNamespace(ref=SimpleNamespace(channel_id=channel))]
    api.get_video.return_value = SimpleNamespace(
        ref=SimpleNamespace(channel_id="foreign" if outcome == "foreign_video" else channel, remote_id="video-1")
    )
    provider = Mock()
    provider.read_caption_inventory.return_value = {"track-1": {"videoId": "video-1", "language": "ru"}}
    provider.download_caption_srt.return_value = b"1\n00:00:01,000 --> 00:00:02,000\nTest\n"
    monkeypatch.setattr(youtube_cli, "_components", lambda *_args: (None, None, api))
    monkeypatch.setattr(youtube_cli, "YouTubeReleaseProvider", lambda **_kwargs: provider)
    output = None if outcome == "list" else tmp_path / "source.srt"
    track = None if outcome == "list" else "other" if outcome == "foreign_track" else "track-1"
    if outcome == "existing_file":
        output.write_bytes(b"keep")

    def run() -> None:
        youtube_cli.captions(
            "video-1",
            account="legendary-poet",
            confirm_channel=channel,
            download_track=track,
            output=output,
            client_secret=None,
        )

    if outcome in {"list", "download"}:
        run()
        provider.read_caption_inventory.assert_called_once_with("video-1")
    else:
        with pytest.raises(typer.Exit):
            run()
    if outcome == "download":
        provider.download_caption_srt.assert_called_once_with("track-1")
        assert output.read_bytes() == provider.download_caption_srt.return_value
    else:
        provider.download_caption_srt.assert_not_called()
        if outcome == "existing_file":
            assert output.read_bytes() == b"keep"


def test_caption_cli_reconciles_pending_insert_without_second_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    from video_channel_manager.youtube_release_provider import ReleaseProviderResult

    channel = "UC-78ys2S3cQ3lpqgXfo-SvQ"
    srt = tmp_path / "lyrics.srt"
    srt.write_bytes(b"1\n00:00:00,000 --> 00:00:01,000\nTest\n")
    api = Mock()
    api.list_my_channels.return_value = [SimpleNamespace(ref=SimpleNamespace(channel_id=channel))]
    api.get_video.return_value = SimpleNamespace(
        ref=SimpleNamespace(channel_id=channel, remote_id="video-1"), duration_seconds=2
    )
    provider = Mock()
    provider.read_caption_inventory.return_value = {}
    provider.verified_caption_id.return_value = None

    def ambiguous(**kwargs: Any) -> ReleaseProviderResult:
        kwargs["before_dispatch"]()
        return ReleaseProviderResult(provider_effect="may_exist", remote_id="manual")

    provider.insert_caption_srt.side_effect = ambiguous
    monkeypatch.setattr(youtube_cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    monkeypatch.setattr(youtube_cli, "_components", lambda *_args: (None, None, api))
    monkeypatch.setattr(youtube_cli, "YouTubeReleaseProvider", lambda **_kwargs: provider)

    def run(execute: bool) -> None:
        youtube_cli.add_caption(
            "video-1",
            srt=srt,
            account="legendary-poet",
            confirm_channel=channel,
            language="ru",
            name="Lyrics",
            execute=execute,
            client_secret=None,
        )

    run(False)
    assert not list((tmp_path / "reports").glob("*.json"))
    for _ in range(2):
        with pytest.raises(typer.Exit):
            run(True)
    provider.insert_caption_srt.assert_called_once()
    journal = next((tmp_path / "reports").glob("*.json"))
    assert json.loads(journal.read_text(encoding="utf-8"))["status"] == "pending_reconciliation"
    provider.read_caption_inventory.return_value = {
        "manual": {"videoId": "video-1", "language": "ru", "name": "Lyrics", "trackKind": "standard"}
    }
    provider.verified_caption_id.return_value = "manual"
    run(True)
    provider.insert_caption_srt.assert_called_once()
    assert json.loads(journal.read_text(encoding="utf-8"))["status"] == "verified"
