from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalize


class _Writer:
    def __init__(self, snapshot: Any) -> None:
        self.snapshot = snapshot

    def capture_wall_snapshot(self, *, community_id: int, max_posts_per_surface: int) -> Any:
        assert community_id == 68859909
        assert max_posts_per_surface == 10000
        return self.snapshot


def test_verified_provider_effect_proves_due_successor_before_historical_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual = SimpleNamespace(complete=True, snapshot_sha256="actual")
    supplemented = SimpleNamespace(complete=True, snapshot_sha256="supplemented")
    historical = SimpleNamespace(complete=True, snapshot_sha256="historical")
    writer = _Writer(actual)
    upload_writer = SimpleNamespace(client=object())
    asset = SimpleNamespace(
        source_id="1_SuzeQD_1g",
        title="Milovi Cake",
        duration_seconds=29,
        description="reviewed promoted copy",
        media_path="must-not-be-used.mp4",
    )
    record: dict[str, Any] = {
        "stage": "verified",
        "wall_safety": {"before_snapshot_sha256": "durable-baseline"},
    }
    item: dict[str, Any] = {"status": "upload_in_progress", "upload_record": record}
    journal: dict[str, Any] = {"source_snapshot_id": "milovi-test-snapshot"}
    order: list[str] = []
    execution: dict[str, Any] = {}

    monkeypatch.setattr(finalize, "clip_readiness", lambda _asset: object())
    monkeypatch.setattr(finalize, "ensure_upload_record", lambda current, **_kwargs: (current, False))
    monkeypatch.setattr(finalize, "_has_provider_effect", lambda _record: True)
    monkeypatch.setattr(finalize, "_save", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(finalize, "_assert_native_clip", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(finalize, "_upload_remote_id", lambda _record: "-68859909_456239233")

    def supplement(
        observed_writer: Any,
        current: Any,
        *,
        journal: Any,
        source_id: str,
    ) -> tuple[Any, tuple[str, ...]]:
        assert observed_writer is writer
        assert current is actual
        assert journal is not None
        assert source_id == asset.source_id
        order.append("exact-successor-proof")
        return supplemented, ("-68859909_468",)

    def resume_baseline(
        current_record: Any,
        current: Any,
        *,
        journal: Any,
        successor_resolution_proven: bool = False,
        **_kwargs: Any,
    ) -> Any:
        assert current_record is record
        assert current is supplemented
        assert journal is not None
        assert successor_resolution_proven is True
        order.append("historical-baseline")
        return historical

    def execute(current_record: dict[str, Any], **kwargs: Any) -> None:
        execution.update(kwargs)
        assert kwargs["media_path"] is None
        assert kwargs["media_artifact"] is None
        assert kwargs["wall_before_snapshot"] is historical
        assert isinstance(kwargs["writer"], finalize._Issue323RecoveryWriter)
        current_record["stage"] = "verified"

    monkeypatch.setattr(finalize, "_supplement_due_prior_wall_readbacks", supplement)
    monkeypatch.setattr(finalize, "_resume_wall_baseline", resume_baseline)
    monkeypatch.setattr(finalize, "execute_upload_operation", execute)

    remote_id = finalize._ensure_promoted_clip(
        asset,
        object(),
        item,
        journal,
        tmp_path / "journal.json",
        writer,  # type: ignore[arg-type]
        upload_writer,  # type: ignore[arg-type]
        60,
    )

    assert order == ["exact-successor-proof", "historical-baseline"]
    assert remote_id == "-68859909_456239233"
    assert item["status"] == "clip_verified"
    assert item["clip_remote_id"] == remote_id
    assert item["clip_origin"] == "resumed_token_short_video_internal_promotion"
    assert journal["provider_write_attempted"] is True
    assert execution["community_id"] == 68859909
