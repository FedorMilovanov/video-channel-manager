from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalize
import video_channel_manager.platforms.vk.milovi_issue323_upload_wall_reconcile as reconcile
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.upload_lifecycle import UploadRecoveryRequired, UploadStage
from video_channel_manager.platforms.vk.wall_safety import build_wall_snapshot

PRIOR_WALL_IDS = [468, 469, 470, 471, 472, 473, 474, 477]
PRIOR_CLIP_IDS = [456239225, 456239226, 456239227, 456239228, 456239229, 456239230, 456239231, 456239232]
PRIOR_DATES = [
    1786723200,
    1786809600,
    1786896000,
    1786982400,
    1787068800,
    1787155200,
    1787241600,
    1787328000,
]
SOURCE9 = ROLL_OUT_IDS[8]
SOURCE9_CLIP_ID = 456239233
AUTO_POST_ID = 478
AUTO_POST_DATE = 1786735800


def _wall_item(index: int, *, surface_post_id: int | None = None) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": PRIOR_WALL_IDS[index] if surface_post_id is None else surface_post_id,
        "date": PRIOR_DATES[index],
        "text": f"prior wall {index}",
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": PRIOR_CLIP_IDS[index],
                    "type": "short_video",
                },
            }
        ],
    }


def _auto_post(*, video_id: int = SOURCE9_CLIP_ID, post_id: int = AUTO_POST_ID) -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": post_id,
        "date": AUTO_POST_DATE,
        "text": "",
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": video_id,
                    "type": "short_video",
                },
            }
        ],
    }


def _historical_before():
    return build_wall_snapshot(
        community_id=68859909,
        published_items=[],
        postponed_items=[_wall_item(index) for index in range(8)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime.fromtimestamp(AUTO_POST_DATE - 30, UTC),
    )


def _current_after(*, video_id: int = SOURCE9_CLIP_ID, include_auto: bool = True):
    published = [_auto_post(video_id=video_id)] if include_auto else []
    return build_wall_snapshot(
        community_id=68859909,
        published_items=published,
        postponed_items=[_wall_item(index) for index in range(8)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime.fromtimestamp(AUTO_POST_DATE + 30, UTC),
    )


def _journal() -> dict[str, Any]:
    items: dict[str, Any] = {}
    for index, source_id in enumerate(ROLL_OUT_IDS[:8]):
        items[source_id] = {
            "status": "wall_verified",
            "clip_remote_id": f"-68859909_{PRIOR_CLIP_IDS[index]}",
            "wall_remote_id": f"-68859909_{PRIOR_WALL_IDS[index]}",
            "publish_date": PRIOR_DATES[index],
        }
    for source_id in ROLL_OUT_IDS[8:]:
        items[source_id] = {"status": "pending"}
    return {"items": items}


def _record(*, source_id: str = SOURCE9, video_id: int = SOURCE9_CLIP_ID) -> dict[str, Any]:
    before = _historical_before()
    after = _current_after(video_id=video_id)
    return {
        "source_video_id": source_id,
        "stage": UploadStage.UNKNOWN_REQUIRES_RECONCILIATION.value,
        "reservation": {
            "owner_id": -68859909,
            "video_id": video_id,
            "remote_id": f"-68859909_{video_id}",
            "upload_url": "journal-only",
        },
        "wall_safety": {
            "before_snapshot_sha256": before.snapshot_sha256,
            "before_captured_at": before.captured_at,
            "before_published_pages": before.published_pages,
            "before_postponed_pages": before.postponed_pages,
            "after_snapshot_sha256": after.snapshot_sha256,
            "after_captured_at": after.captured_at,
            "after_published_pages": after.published_pages,
            "after_postponed_pages": after.postponed_pages,
            "delta": {
                "status": "changed",
                "created": [f"published:-68859909_{AUTO_POST_ID}"],
                "removed": [],
                "changed": [],
                "before_sha256": before.snapshot_sha256,
                "after_sha256": after.snapshot_sha256,
                "reasons": [],
            },
        },
    }


class _Writer:
    def __init__(self, *, exact_video_id: int = SOURCE9_CLIP_ID) -> None:
        self.exact_video_id = exact_video_id
        self.deleted = False
        self.delete_calls: list[tuple[str, dict[str, Any]]] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == AUTO_POST_ID
        if self.deleted:
            return {"owner_id": -68859909, "id": AUTO_POST_ID, "date": AUTO_POST_DATE, "is_deleted": True}
        return _auto_post(video_id=self.exact_video_id)

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000):
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return _current_after(include_auto=not self.deleted)

    def _call(self, method: str, *, params: dict[str, Any]):
        self.delete_calls.append((method, dict(params)))
        assert method == "wall.delete"
        assert params == {"owner_id": -68859909, "post_id": AUTO_POST_ID}
        self.deleted = True
        return 1


def test_exact_upload_created_post_is_deleted_once_and_clip_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _Writer()
    record = _record()
    persisted: list[str] = []
    monkeypatch.setattr(reconcile, "_prove_target", lambda _client: None)

    current, baseline = reconcile.reconcile_issue323_upload_wall_effect(
        record=record,
        current_wall=_current_after(),
        journal=_journal(),
        writer=writer,  # type: ignore[arg-type]
        client=object(),
        source_id=SOURCE9,
        persist=lambda: persisted.append(str(record["issue323_upload_wall_reconcile"]["status"])),
    )

    assert writer.delete_calls == [("wall.delete", {"owner_id": -68859909, "post_id": AUTO_POST_ID})]
    assert writer.deleted is True
    assert baseline.snapshot_sha256 == _historical_before().snapshot_sha256
    assert all(post.post_id != AUTO_POST_ID for post in current.posts)
    state = record["issue323_upload_wall_reconcile"]
    assert state["status"] == "verified_absent"
    assert state["clip_remote_id"] == f"-68859909_{SOURCE9_CLIP_ID}"
    assert state["protected_clip_preserved"] is True
    assert "delete_dispatch_started" in persisted
    assert persisted[-1] == "verified_absent"


def test_wrong_clip_binding_blocks_without_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _Writer(exact_video_id=999)
    record = _record()
    monkeypatch.setattr(reconcile, "_prove_target", lambda _client: None)

    with pytest.raises(UploadRecoveryRequired, match="changed Clip binding"):
        reconcile.reconcile_issue323_upload_wall_effect(
            record=record,
            current_wall=_current_after(),
            journal=_journal(),
            writer=writer,  # type: ignore[arg-type]
            client=object(),
            source_id=SOURCE9,
            persist=lambda: None,
        )

    assert writer.delete_calls == []
    assert writer.deleted is False


def test_live_post_after_committed_delete_dispatch_never_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = _Writer()
    record = _record()
    baseline = _historical_before()
    record["issue323_upload_wall_reconcile"] = {
        "schema_name": reconcile.ISSUE323_UPLOAD_WALL_RECONCILE_SCHEMA,
        "schema_version": 1,
        "status": "delete_dispatch_started",
        "source_id": SOURCE9,
        "clip_remote_id": f"-68859909_{SOURCE9_CLIP_ID}",
        "wall_remote_id": f"-68859909_{AUTO_POST_ID}",
        "preupload_snapshot_sha256": baseline.snapshot_sha256,
        "delete_authorized": True,
        "delete_dispatch_started": True,
    }
    monkeypatch.setattr(reconcile, "_prove_target", lambda _client: None)

    with pytest.raises(UploadRecoveryRequired, match="blind retry is forbidden"):
        reconcile.reconcile_issue323_upload_wall_effect(
            record=record,
            current_wall=_current_after(),
            journal=_journal(),
            writer=writer,  # type: ignore[arg-type]
            client=object(),
            source_id=SOURCE9,
            persist=lambda: None,
        )

    assert writer.delete_calls == []


def test_eighth_source_never_gets_remaining_upload_delete_authority() -> None:
    source8 = ROLL_OUT_IDS[7]
    record = _record(source_id=source8, video_id=PRIOR_CLIP_IDS[7])
    writer = _Writer(exact_video_id=PRIOR_CLIP_IDS[7])

    with pytest.raises(UploadRecoveryRequired, match="sources 9-12"):
        reconcile.reconcile_issue323_upload_wall_effect(
            record=record,
            current_wall=_current_after(video_id=PRIOR_CLIP_IDS[7]),
            journal=_journal(),
            writer=writer,  # type: ignore[arg-type]
            client=object(),
            source_id=source8,
            persist=lambda: None,
        )

    assert writer.delete_calls == []


def test_due_surface_only_change_normalizes_without_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    before = _historical_before()
    current = build_wall_snapshot(
        community_id=68859909,
        published_items=[_wall_item(0)],
        postponed_items=[_wall_item(index) for index in range(1, 8)],
        published_pages=1,
        postponed_pages=1,
        complete=True,
        captured_at=datetime.fromtimestamp(AUTO_POST_DATE + 30, UTC),
    )
    record = _record()
    record["wall_safety"]["after_snapshot_sha256"] = current.snapshot_sha256
    record["wall_safety"]["after_captured_at"] = current.captured_at
    record["wall_safety"]["delta"] = {
        "status": "changed",
        "created": ["published:-68859909_468"],
        "removed": ["postponed:-68859909_468"],
        "changed": [],
        "before_sha256": before.snapshot_sha256,
        "after_sha256": current.snapshot_sha256,
        "reasons": [],
    }
    writer = _Writer()
    monkeypatch.setattr(reconcile, "_prove_target", lambda _client: None)

    actual, baseline = reconcile.reconcile_issue323_upload_wall_effect(
        record=record,
        current_wall=current,
        journal=_journal(),
        writer=writer,  # type: ignore[arg-type]
        client=object(),
        source_id=SOURCE9,
        persist=lambda: None,
    )

    assert actual.snapshot_sha256 == current.snapshot_sha256
    assert baseline.snapshot_sha256 == before.snapshot_sha256
    assert record["issue323_upload_wall_reconcile"]["status"] == "normalized_without_delete"
    assert writer.delete_calls == []


def test_finalizer_retries_same_fresh_clip_through_replay_proof_recovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    asset = SimpleNamespace(
        source_id=SOURCE9,
        title="Cake",
        description="Promoted",
        duration_seconds=30.0,
        media_path=str(tmp_path / "source.mp4"),
    )
    item: dict[str, Any] = {"status": "pending"}
    journal: dict[str, Any] = {"source_snapshot_id": "snapshot", "items": {SOURCE9: item}}
    record: dict[str, Any] = {
        "stage": UploadStage.PLANNED.value,
        "source_video_id": SOURCE9,
    }
    current = SimpleNamespace(complete=True, snapshot_sha256="sha256:current")
    historical = SimpleNamespace(snapshot_sha256="sha256:before")
    capture_calls = 0

    class FakeWriter:
        def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int = 10000):
            nonlocal capture_calls
            capture_calls += 1
            return current

    class FakeUploadWriter:
        client = object()

    class FakeRecoveryWriter:
        last_actual_snapshot_sha256 = "sha256:actual"
        last_effective_snapshot_sha256 = "sha256:effective"
        last_historical_snapshot_sha256 = "sha256:before"
        last_reversed_surface_ids = ()
        last_exact_read_ids = ()

        def __init__(self, *_args, **_kwargs) -> None:
            pass

    monkeypatch.setattr(finalize, "clip_readiness", lambda _asset: object())
    monkeypatch.setattr(finalize, "ensure_upload_record", lambda *_args, **_kwargs: (record, False))
    monkeypatch.setattr(
        finalize, "_has_provider_effect", lambda current_record: current_record["stage"] != UploadStage.PLANNED.value
    )
    monkeypatch.setattr(finalize, "_save", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(finalize, "_Issue323RecoveryWriter", FakeRecoveryWriter)
    monkeypatch.setattr(finalize, "_assert_native_clip", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(finalize, "_upload_remote_id", lambda _record: f"-68859909_{SOURCE9_CLIP_ID}")
    monkeypatch.setattr(
        finalize,
        "_needs_issue323_upload_wall_reconcile",
        lambda current_record: current_record["stage"] == UploadStage.UNKNOWN_REQUIRES_RECONCILIATION.value,
    )

    reconcile_calls: list[str] = []

    def fake_reconcile(**kwargs):
        reconcile_calls.append(kwargs["source_id"])
        return current, historical

    monkeypatch.setattr(finalize, "reconcile_issue323_upload_wall_effect", fake_reconcile)
    execute_calls: list[dict[str, Any]] = []

    def fake_execute(current_record: dict[str, Any], **kwargs):
        execute_calls.append(kwargs)
        if len(execute_calls) == 1:
            current_record["stage"] = UploadStage.UNKNOWN_REQUIRES_RECONCILIATION.value
            current_record["wall_safety"] = {"delta": {"status": "changed"}}
            raise UploadRecoveryRequired("Upload wall postflight is changed; wall reconciliation is required")
        current_record["stage"] = UploadStage.VERIFIED.value

    monkeypatch.setattr(finalize, "execute_upload_operation", fake_execute)

    remote_id = finalize._ensure_promoted_clip(
        asset,  # type: ignore[arg-type]
        object(),
        item,
        journal,
        tmp_path / "journal.json",
        FakeWriter(),  # type: ignore[arg-type]
        FakeUploadWriter(),  # type: ignore[arg-type]
        60,
    )

    assert remote_id == f"-68859909_{SOURCE9_CLIP_ID}"
    assert len(execute_calls) == 2
    assert execute_calls[0]["media_path"] == tmp_path / "source.mp4"
    assert execute_calls[1]["media_path"] is None
    assert execute_calls[1]["media_artifact"] is None
    assert reconcile_calls == [SOURCE9]
    assert capture_calls == 2
    assert item["status"] == "clip_verified"
    assert item["clip_origin"] == "resumed_token_short_video_internal_promotion"
