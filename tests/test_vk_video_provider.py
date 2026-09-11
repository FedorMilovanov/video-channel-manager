from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.wave_engine.vk_video_provider as provider_module
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired, UploadStage
from video_channel_manager.platforms.vk.text import render_vk_video_description
from video_channel_manager.wave_engine.canonical import file_sha256, write_json_atomic
from video_channel_manager.wave_engine.engine import OperationRejectedError, UnknownProviderOutcomeError
from video_channel_manager.wave_engine.models import (
    MutationClass,
    ProjectBinding,
    WaveOperation,
    WaveOperationSpec,
)
from video_channel_manager.wave_engine.vk_video_provider import (
    VK_VIDEO_OPERATION_KIND,
    VK_VIDEO_POLICY_VERSION,
    VkNativeVideoUploadAdapter,
)


COMMUNITY_ID = 235216998
OWNER_ID = -COMMUNITY_ID
CHANNEL_ID = "UC-78ys2S3cQ3lpqgXfo-SvQ"


def _operation(manifest_path: str, manifest_sha256: str) -> WaveOperation:
    spec = WaveOperationSpec(
        order_key="2026-09-01T12:00:00+00:00-yt-1",
        operation_kind=VK_VIDEO_OPERATION_KIND,
        mutation_class=MutationClass.AMBIGUOUS_MUTATION,
        payload={
            "source_video_id": "yt-1",
            "source_channel_id": CHANNEL_ID,
            "youtube_snapshot_id": "youtube-snapshot",
            "target_snapshot_id": "vk-snapshot",
            "source_title": "Поэма",
            "source_duration_seconds": 305,
            "privacy_status": "public",
            "published_title": "Поэма",
            "published_description": render_vk_video_description("Описание").text,
            "media_manifest_path": manifest_path,
            "media_manifest_sha256": manifest_sha256,
            "media_artifact_manifest_sha256": "sha256:" + "a" * 64,
            "processing_timeout_seconds": 60,
            "wallpost": False,
            "auto_publish": False,
            "repeat": False,
        },
    )
    return WaveOperation.build(
        sequence=0,
        project=ProjectBinding(
            project_key="legendary-poet",
            community_id=COMMUNITY_ID,
            owner_id=OWNER_ID,
        ),
        source_snapshot_id="b" * 64,
        policy_version=VK_VIDEO_POLICY_VERSION,
        spec=spec,
    )


class _FakeWriter:
    def __init__(self) -> None:
        self.guard_calls = 0

    def capture_upload_wall_guard(self, *, community_id: int, head_limit: int = 100):
        del community_id, head_limit
        self.guard_calls += 1
        raise AssertionError("native video upload must not read wall state")


def _adapter(root: Path, writer: _FakeWriter) -> VkNativeVideoUploadAdapter:
    adapter = object.__new__(VkNativeVideoUploadAdapter)
    adapter.repository_root = root.resolve()
    adapter.journal_directory = (root / "journal").resolve()
    adapter.account_alias = "legendary-poet"
    adapter.writer = writer
    adapter._owns_writer = False
    adapter._community_ids = {COMMUNITY_ID}
    return adapter


def _artifact(media: Path) -> SimpleNamespace:
    return SimpleNamespace(
        source=SimpleNamespace(
            project_key="legendary-poet",
            source_channel_id=CHANNEL_ID,
            source_id="yt-1",
        ),
        acquisition=SimpleNamespace(authoritative_final_path=str(media.resolve())),
        manifest_sha256="sha256:" + "a" * 64,
    )


def _inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "repo"
    root.mkdir()
    media = root / "yt-1.mp4"
    media.write_bytes(b"video")
    manifest = root / "yt-1-manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(provider_module, "load_media_artifact_manifest", lambda _path: _artifact(media))
    operation = _operation("yt-1-manifest.json", file_sha256(manifest))
    return root, media, operation


def test_video_adapter_does_not_read_wall_before_upload_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, media, operation = _inputs(tmp_path, monkeypatch)
    writer = _FakeWriter()
    adapter = _adapter(root, writer)
    dispatched = 0

    def fake_execute(record: dict[str, Any], **kwargs: Any) -> None:
        nonlocal dispatched
        dispatched += 1
        assert kwargs["media_path"] == media.resolve()
        assert kwargs["wall_before_snapshot"] is None
        record["stage"] = UploadStage.VERIFIED.value
        record["reservation"] = {
            "remote_id": f"{OWNER_ID}_501",
            "owner_id": OWNER_ID,
            "video_id": 501,
        }
        record["verification"] = {"item_sha256": "sha256:" + "1" * 64}
        kwargs["persist"]()

    monkeypatch.setattr(provider_module, "execute_upload_operation", fake_execute)

    evidence = adapter.execute(operation)

    assert dispatched == 1
    assert writer.guard_calls == 0
    assert evidence["remote_id"] == f"{OWNER_ID}_501"


def test_video_adapter_success_persists_exact_verified_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, media, operation = _inputs(tmp_path, monkeypatch)
    writer = _FakeWriter()
    adapter = _adapter(root, writer)
    calls = 0

    def fake_execute(record: dict[str, Any], **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        assert kwargs["media_path"] == media.resolve()
        assert kwargs["wall_before_snapshot"] is None
        record["stage"] = UploadStage.VERIFIED.value
        record["reservation"] = {
            "remote_id": f"{OWNER_ID}_501",
            "owner_id": OWNER_ID,
            "video_id": 501,
        }
        record["verification"] = {"item_sha256": "sha256:" + "1" * 64}
        kwargs["persist"]()

    monkeypatch.setattr(provider_module, "execute_upload_operation", fake_execute)

    evidence = adapter.execute(operation)

    assert calls == 1
    assert writer.guard_calls == 0
    assert evidence["remote_id"] == f"{OWNER_ID}_501"
    assert evidence["upload_stage"] == UploadStage.VERIFIED.value
    assert "wall_delta_status" not in evidence
    journal = root / evidence["provider_journal_path"]
    assert journal.is_file()


def test_video_adapter_explicit_video_save_rejection_is_known_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    adapter = _adapter(root, _FakeWriter())

    def fake_execute(record: dict[str, Any], **kwargs: Any) -> None:
        record["reservation_dispatch_started_at"] = "2026-09-11T08:00:00+00:00"
        kwargs["persist"]()
        raise provider_module.UploadRejected("video.save was rejected")

    monkeypatch.setattr(provider_module, "execute_upload_operation", fake_execute)

    with pytest.raises(OperationRejectedError, match="video.save was rejected"):
        adapter.execute(operation)


def test_video_adapter_post_reservation_failure_is_unknown_not_retry_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    adapter = _adapter(root, _FakeWriter())

    def fake_execute(record: dict[str, Any], **kwargs: Any) -> None:
        record["reservation_dispatch_started_at"] = "2026-09-10T18:00:00+00:00"
        record["reservation"] = {
            "remote_id": f"{OWNER_ID}_501",
            "owner_id": OWNER_ID,
            "video_id": 501,
        }
        kwargs["persist"]()
        raise UploadRecoveryRequired("response lost")

    monkeypatch.setattr(provider_module, "execute_upload_operation", fake_execute)

    with pytest.raises(UnknownProviderOutcomeError, match="response lost"):
        adapter.execute(operation)


def test_video_adapter_reconciliation_uses_exact_journaled_id_without_media_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    adapter = _adapter(root, _FakeWriter())
    provider_path = adapter._provider_journal_path(operation)
    provider_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        provider_path,
        {
            "stage": UploadStage.PROCESSING.value,
            "source_video_id": "yt-1",
            "reservation": {
                "remote_id": f"{OWNER_ID}_501",
                "owner_id": OWNER_ID,
                "video_id": 501,
            },
        },
    )
    calls = 0

    def fake_execute(record: dict[str, Any], **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        assert kwargs["media_path"] is None
        assert kwargs["media_artifact"] is None
        assert kwargs["wall_before_snapshot"] is None
        assert record["reservation"]["remote_id"] == f"{OWNER_ID}_501"
        record["stage"] = UploadStage.VERIFIED.value
        record["verification"] = {"item_sha256": "sha256:" + "1" * 64}
        kwargs["persist"]()

    monkeypatch.setattr(provider_module, "execute_upload_operation", fake_execute)

    evidence = adapter.reconcile(operation)

    assert calls == 1
    assert evidence["remote_id"] == f"{OWNER_ID}_501"
    assert evidence["reconciliation"] == "exact_remote_id_verified"
