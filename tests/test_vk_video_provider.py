from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
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
            "published_description": render_vk_video_description("Описание", source_video_id="yt-1").text,
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
        self.community_videos: list[dict[str, Any]] = []

    def list_community_videos(self, *, community_id: int, page_size: int = 200) -> list[dict[str, Any]]:
        assert community_id == COMMUNITY_ID
        assert page_size == 200
        return list(self.community_videos)

    def capture_upload_wall_guard(self, *, community_id: int, head_limit: int = 100):
        del community_id, head_limit
        self.guard_calls += 1
        raise AssertionError("native video upload must not read wall state")


def _adapter(root: Path, writer: _FakeWriter) -> VkNativeVideoUploadAdapter:
    adapter = object.__new__(VkNativeVideoUploadAdapter)
    adapter.repository_root = root.resolve()
    adapter.journal_directory = (root / "journal").resolve()
    adapter.account_alias = "legendary-poet"
    adapter.store = SimpleNamespace(data_dir=root / ".data")
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


def _valid_owner_absence(*, source_id: str = "yt-1") -> dict[str, Any]:
    return {
        "schema_name": "video-manager.vk-owner-creator-absence-v1",
        "project_key": "legendary-poet",
        "community_id": COMMUNITY_ID,
        "owner_id": OWNER_ID,
        "source_channel_id": CHANNEL_ID,
        "source_video_id": source_id,
        "capture_method": "owner_authenticated_creator_read_only",
        "read_only": True,
        "provider_effect": "safe_read_only",
        "verdict": "confirmed_absent",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "surfaces": {
            surface: {
                "pagination_complete": True,
                "covered_states": [
                    "published",
                    "postponed",
                    "draft",
                    "private",
                    "processing",
                    "accepted",
                ],
                "exact_source_matches": [],
                "unresolved_candidates": [],
            }
            for surface in ("ordinary_video", "native_clip")
        },
    }


def _inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "repo"
    root.mkdir()
    media = root / "yt-1.mp4"
    media.write_bytes(b"video")
    manifest = root / "yt-1-manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(provider_module, "load_media_artifact_manifest", lambda _path: _artifact(media))
    proof = root / "owner-absence.json"
    proof.write_text(json.dumps(_valid_owner_absence()) + "\n", encoding="utf-8")
    operation = _operation_with_payload(
        _operation("yt-1-manifest.json", file_sha256(manifest)),
        owner_absence_evidence_path="owner-absence.json",
        owner_absence_evidence_sha256=file_sha256(proof),
    )
    return root, media, operation


def test_video_v2_operation_and_provider_journal_are_stable_across_fresh_snapshots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, first = _inputs(tmp_path, monkeypatch)
    second = WaveOperation.build(
        sequence=9,
        project=first.project,
        source_snapshot_id="c" * 64,
        policy_version=VK_VIDEO_POLICY_VERSION,
        spec=WaveOperationSpec(
            order_key="different-attempt-order",
            operation_kind=VK_VIDEO_OPERATION_KIND,
            mutation_class=MutationClass.AMBIGUOUS_MUTATION,
            payload={**first.payload, "youtube_snapshot_id": "fresh-snapshot"},
        ),
    )
    adapter = _adapter(root, _FakeWriter())

    assert second.operation_id == first.operation_id
    assert adapter._provider_journal_path(second) == adapter._provider_journal_path(first)


def test_video_adapter_rejects_unregistered_source_channel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    bad = WaveOperation.build(
        sequence=0,
        project=operation.project,
        source_snapshot_id=operation.source_snapshot_id,
        policy_version=VK_VIDEO_POLICY_VERSION,
        spec=WaveOperationSpec(
            order_key=operation.order_key,
            operation_kind=VK_VIDEO_OPERATION_KIND,
            mutation_class=MutationClass.AMBIGUOUS_MUTATION,
            payload={**operation.payload, "source_channel_id": "UC-other"},
        ),
    )
    adapter = _adapter(root, _FakeWriter())

    with pytest.raises(OperationRejectedError, match="registered project channel"):
        adapter.execute(bad)


def test_video_provider_journal_path_is_stable_across_attempt_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    first = _adapter(root, _FakeWriter())
    second = _adapter(root, _FakeWriter())
    second.journal_directory = root / "another-attempt" / "journal"

    assert first._provider_journal_path(operation) == second._provider_journal_path(operation)
    assert "operator-output/vk-upload-state/legendary-poet" in first._provider_journal_path(operation).as_posix()


def test_video_adapter_blocks_live_duplicate_before_upload_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    writer = _FakeWriter()
    writer.community_videos = [
        {
            "owner_id": OWNER_ID,
            "id": 777,
            "title": "Поэма",
            "description": "Источник видео: https://www.youtube.com/watch?v=yt-1",
            "duration": 305,
        }
    ]
    adapter = _adapter(root, writer)
    dispatched = 0

    def forbidden_execute(*_args: Any, **_kwargs: Any) -> None:
        nonlocal dispatched
        dispatched += 1
        raise AssertionError("upload must not dispatch when source already exists")

    monkeypatch.setattr(provider_module, "execute_upload_operation", forbidden_execute)

    with pytest.raises(OperationRejectedError, match="already contains the source video"):
        adapter.execute(operation)

    assert dispatched == 0


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


def _operation_with_payload(operation: WaveOperation, **updates: Any) -> WaveOperation:
    return WaveOperation.build(
        sequence=operation.sequence,
        project=operation.project,
        source_snapshot_id=operation.source_snapshot_id,
        policy_version=operation.policy_version,
        spec=WaveOperationSpec(
            order_key=operation.order_key,
            operation_kind=operation.operation_kind,
            mutation_class=operation.mutation_class,
            payload={**operation.payload, **updates},
        ),
    )


def test_video_adapter_reviewed_179_seconds_requires_explicit_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, original = _inputs(tmp_path, monkeypatch)
    adapter = _adapter(root, _FakeWriter())
    short_unreviewed = _operation_with_payload(original, source_duration_seconds=179)
    reviewed = _operation_with_payload(
        original,
        source_duration_seconds=179,
        reviewed_short_horizontal_video=True,
    )

    with pytest.raises(OperationRejectedError, match="explicit reviewed short-horizontal approval"):
        adapter._validate_operation(short_unreviewed)

    assert adapter._validate_operation(reviewed)["reviewed_short_horizontal_video"] is True
    assert reviewed.operation_id == short_unreviewed.operation_id

    with pytest.raises(OperationRejectedError, match="only valid for <=180s"):
        adapter._validate_operation(_operation_with_payload(original, reviewed_short_horizontal_video=True))

    with pytest.raises(OperationRejectedError, match="must be a boolean"):
        adapter._validate_operation(_operation_with_payload(original, reviewed_short_horizontal_video="true"))


def test_video_adapter_reviewed_short_rejects_vertical_artifact_before_provider_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, media, original = _inputs(tmp_path, monkeypatch)
    operation = _operation_with_payload(
        original,
        source_duration_seconds=179,
        reviewed_short_horizontal_video=True,
    )
    artifact = _artifact(media)
    artifact.probe = SimpleNamespace(width=1080, height=1920, video_stream_count=1, audio_stream_count=1)
    monkeypatch.setattr(provider_module, "load_media_artifact_manifest", lambda _path: artifact)
    adapter = _adapter(root, _FakeWriter())

    def forbidden_dispatch(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("vertical media must never reach provider dispatch")

    monkeypatch.setattr(provider_module, "execute_upload_operation", forbidden_dispatch)
    with pytest.raises(OperationRejectedError, match="verified horizontal video"):
        adapter.execute(operation)


def test_video_adapter_reviewed_179_seconds_retains_video_only_no_wall_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, media, original = _inputs(tmp_path, monkeypatch)
    operation = _operation_with_payload(
        original,
        source_duration_seconds=179,
        reviewed_short_horizontal_video=True,
    )
    artifact = _artifact(media)
    artifact.probe = SimpleNamespace(width=1920, height=1080, video_stream_count=1, audio_stream_count=1)
    monkeypatch.setattr(provider_module, "load_media_artifact_manifest", lambda _path: artifact)
    adapter = _adapter(root, _FakeWriter())
    calls = 0

    def fake_execute(record: dict[str, Any], **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        assert kwargs["readiness"].allowed_types == ("video",)
        assert kwargs["readiness"].minimum_duration_seconds > 0
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
    assert evidence["upload_stage"] == UploadStage.VERIFIED.value
    assert evidence["remote_id"] == f"{OWNER_ID}_501"


def test_video_upload_fails_closed_without_owner_creator_absence_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, original = _inputs(tmp_path, monkeypatch)
    adapter = _adapter(root, _FakeWriter())
    operation = WaveOperation.build(
        sequence=original.sequence,
        project=original.project,
        source_snapshot_id=original.source_snapshot_id,
        policy_version=original.policy_version,
        spec=WaveOperationSpec(
            order_key=original.order_key,
            operation_kind=original.operation_kind,
            mutation_class=original.mutation_class,
            payload={
                key: value
                for key, value in original.payload.items()
                if not key.startswith("owner_absence_evidence_")
            },
        ),
    )

    def forbidden_dispatch(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("provider dispatch must remain blocked without complete owner state")

    monkeypatch.setattr(provider_module, "execute_upload_operation", forbidden_dispatch)
    with pytest.raises(OperationRejectedError, match="fresh complete owner Creator absence evidence"):
        adapter.execute(operation)


@pytest.mark.parametrize(
    ("change", "error_fragment"),
    [
        ({"observed_at": "2020-01-01T00:00:00+00:00"}, "stale or from the future"),
        ({"observed_at": "2026-11-08T17:00:00"}, "timezone-aware"),
        ({"community_id": COMMUNITY_ID + 1}, "community_id"),
        ({"source_video_id": "different-yt-source"}, "source_video_id"),
        ({"verdict": "unknown"}, "verdict"),
        ({"provider_effect": "may_exist"}, "provider_effect"),
        ({"capture_method": "public_video_get_only"}, "capture_method"),
        ({"read_only": False}, "read_only"),
    ],
)
def test_video_upload_owner_absence_evidence_rejects_untrusted_or_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, Any],
    error_fragment: str,
) -> None:
    root, _media, original = _inputs(tmp_path, monkeypatch)
    proof = root / "owner-absence.json"
    evidence = _valid_owner_absence()
    evidence.update(change)
    proof.write_text(json.dumps(evidence) + "\n", encoding="utf-8")
    operation = _operation_with_payload(
        original, owner_absence_evidence_sha256=file_sha256(proof)
    )
    adapter = _adapter(root, _FakeWriter())

    def forbidden_dispatch(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("invalid owner proof cannot dispatch provider upload")

    monkeypatch.setattr(provider_module, "execute_upload_operation", forbidden_dispatch)
    with pytest.raises(OperationRejectedError, match=error_fragment):
        adapter.execute(operation)


@pytest.mark.parametrize(
    ("surface", "mutated", "error_fragment"),
    [
        ("ordinary_video", {"pagination_complete": False}, "incomplete pagination"),
        ("native_clip", {"covered_states": ["published"]}, "does not cover every state"),
        ("ordinary_video", {"exact_source_matches": ["-235216998_77"]}, "contains matches"),
        ("native_clip", {"unresolved_candidates": ["same title 179s"]}, "contains matches"),
    ],
)
def test_video_upload_owner_absence_never_ignores_hidden_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
    mutated: dict[str, Any],
    error_fragment: str,
) -> None:
    root, _media, original = _inputs(tmp_path, monkeypatch)
    proof = root / "owner-absence.json"
    evidence = _valid_owner_absence()
    evidence["surfaces"][surface].update(mutated)
    proof.write_text(json.dumps(evidence) + "\n", encoding="utf-8")
    operation = _operation_with_payload(
        original, owner_absence_evidence_sha256=file_sha256(proof)
    )
    adapter = _adapter(root, _FakeWriter())

    def forbidden_dispatch(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("unknown draft/private/scheduled/native media blocks upload")

    monkeypatch.setattr(provider_module, "execute_upload_operation", forbidden_dispatch)
    with pytest.raises(OperationRejectedError, match=error_fragment):
        adapter.execute(operation)


def test_video_upload_rejects_modified_owner_proof_after_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    proof = root / "owner-absence.json"
    proof.write_text(proof.read_text(encoding="utf-8") + " ", encoding="utf-8")
    adapter = _adapter(root, _FakeWriter())

    def forbidden_dispatch(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("tampered evidence cannot dispatch provider upload")

    monkeypatch.setattr(provider_module, "execute_upload_operation", forbidden_dispatch)
    with pytest.raises(OperationRejectedError, match="SHA-256"):
        adapter.execute(operation)


def test_video_existing_reservation_is_reconciled_without_new_owner_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _media, operation = _inputs(tmp_path, monkeypatch)
    legacy = _operation_with_payload(
        operation,
        owner_absence_evidence_path="",
        owner_absence_evidence_sha256="",
    )
    adapter = _adapter(root, _FakeWriter())
    journal = adapter._provider_journal_path(legacy)
    journal.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        journal,
        {
            "stage": UploadStage.PROCESSING.value,
            "source_video_id": "yt-1",
            "reservation_dispatch_started_at": "2026-11-08T15:00:00+00:00",
            "reservation": {
                "remote_id": f"{OWNER_ID}_501",
                "owner_id": OWNER_ID,
                "video_id": 501,
            },
        },
    )
    dispatches = 0

    def fake_reconcile(record: dict[str, Any], **kwargs: Any) -> None:
        nonlocal dispatches
        dispatches += 1
        assert kwargs["media_path"] is None
        assert kwargs["media_artifact"] is None
        record["stage"] = UploadStage.VERIFIED.value
        record["verification"] = {"item_sha256": "sha256:" + "1" * 64}
        kwargs["persist"]()

    monkeypatch.setattr(provider_module, "execute_upload_operation", fake_reconcile)
    outcome = adapter.reconcile(legacy)
    assert dispatches == 1
    assert outcome["remote_id"] == f"{OWNER_ID}_501"
