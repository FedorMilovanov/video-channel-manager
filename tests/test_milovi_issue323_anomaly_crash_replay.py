from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import video_channel_manager.platforms.vk.milovi_issue323_anomaly_reconcile as reconcile
from video_channel_manager.platforms.vk.milovi_issue323_anomaly_reconcile import (
    ANOMALY_CREATED_AT,
    ANOMALY_CREATED_BY,
)
from video_channel_manager.platforms.vk.milovi_issue323_finalize import MiloviFinalizerBlocked


def _live_post() -> dict[str, Any]:
    return {
        "owner_id": -68859909,
        "id": 475,
        "date": ANOMALY_CREATED_AT,
        "from_id": -68859909,
        "created_by": ANOMALY_CREATED_BY,
        "post_type": "post",
        "text": "provider projection",
        "post_source": {"type": "api"},
        "attachments": [
            {
                "type": "video",
                "video": {
                    "owner_id": -68859909,
                    "id": 456239232,
                    "type": "short_video",
                    "description": (
                        "legacy source https://www.youtube.com/shorts/o1WXIMupuws"
                    ),
                },
            }
        ],
    }


def _tombstone() -> dict[str, Any]:
    return {"owner_id": -68859909, "id": 475, "is_deleted": True}


class _Writer:
    def __init__(
        self,
        *,
        current: dict[str, Any],
        finalizer_path: Path,
        fail_after_dispatch: bool = False,
    ) -> None:
        self.current = dict(current)
        self.finalizer_path = finalizer_path
        self.fail_after_dispatch = fail_after_dispatch
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == 68859909
        assert post_id == 475
        return dict(self.current)

    def _call(self, method: str, *, params: dict[str, Any]) -> object:
        self.calls.append((method, dict(params)))
        persisted = json.loads(self.finalizer_path.read_text(encoding="utf-8"))
        cleanup = persisted["cleanup_475"]
        assert cleanup["status"] == "delete_dispatch_started"
        assert cleanup["delete_dispatch_started"] is True
        if self.fail_after_dispatch:
            raise TimeoutError("delete response lost")
        self.current = _tombstone()
        return 1


def _invoke(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    finalizer: dict[str, Any],
    current: dict[str, Any],
    fail_after_dispatch: bool = False,
) -> _Writer:
    path = tmp_path / "finalizer.json"
    writer = _Writer(current=current, finalizer_path=path, fail_after_dispatch=fail_after_dispatch)
    monkeypatch.setattr(reconcile, "_assert_native_clip", lambda *args, **kwargs: {})
    monkeypatch.setattr(reconcile, "_prove_target", lambda _client: None)
    reconcile._cleanup_exact_wall475(
        writer=writer,  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        legacy_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
        promoted_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
        finalizer=finalizer,
        finalizer_path=path,
    )
    return writer


def test_fresh_wall475_delete_persists_dispatch_barrier_before_provider_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    finalizer: dict[str, Any] = {"cleanup_475": {"status": "pending"}}

    writer = _invoke(monkeypatch, tmp_path, finalizer=finalizer, current=_live_post())

    assert writer.calls == [("wall.delete", {"owner_id": -68859909, "post_id": 475})]
    assert finalizer["cleanup_475"]["status"] == "verified_absent"
    assert finalizer["cleanup_475"]["delete_dispatch_started"] is True


def test_crash_after_delete_dispatch_blocks_second_delete_when_post_is_still_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    finalizer: dict[str, Any] = {"cleanup_475": {"status": "pending"}}
    path = tmp_path / "finalizer.json"
    writer = _Writer(current=_live_post(), finalizer_path=path, fail_after_dispatch=True)
    monkeypatch.setattr(reconcile, "_assert_native_clip", lambda *args, **kwargs: {})
    monkeypatch.setattr(reconcile, "_prove_target", lambda _client: None)

    with pytest.raises(TimeoutError, match="delete response lost"):
        reconcile._cleanup_exact_wall475(
            writer=writer,  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            legacy_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
            promoted_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
            finalizer=finalizer,
            finalizer_path=path,
        )

    assert len(writer.calls) == 1
    assert finalizer["cleanup_475"]["status"] == "unknown_requires_reconciliation"
    assert finalizer["cleanup_475"]["delete_dispatch_started"] is True

    writer.fail_after_dispatch = False
    with pytest.raises(MiloviFinalizerBlocked, match="blind retry is forbidden"):
        reconcile._cleanup_exact_wall475(
            writer=writer,  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            legacy_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
            promoted_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
            finalizer=finalizer,
            finalizer_path=path,
        )

    assert len(writer.calls) == 1


def test_prior_dispatch_reconciles_exact_tombstone_without_second_delete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    finalizer: dict[str, Any] = {
        "cleanup_475": {
            "status": "delete_dispatch_started",
            "delete_dispatch_started": True,
        }
    }

    writer = _invoke(monkeypatch, tmp_path, finalizer=finalizer, current=_tombstone())

    assert writer.calls == []
    assert finalizer["cleanup_475"]["status"] == "verified_absent"
    assert finalizer["cleanup_475"]["absence_evidence"] == "wall.getById:is_deleted_true-resume"


def test_consumed_cleanup_authority_never_redeletes_a_reappeared_live_post(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    finalizer: dict[str, Any] = {"cleanup_475": {"status": "verified_absent"}}
    path = tmp_path / "finalizer.json"
    writer = _Writer(current=_live_post(), finalizer_path=path)
    monkeypatch.setattr(reconcile, "_assert_native_clip", lambda *args, **kwargs: {})

    with pytest.raises(MiloviFinalizerBlocked, match="authority was already consumed"):
        reconcile._cleanup_exact_wall475(
            writer=writer,  # type: ignore[arg-type]
            client=object(),  # type: ignore[arg-type]
            legacy_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
            promoted_asset=SimpleNamespace(source_id="o1WXIMupuws"),  # type: ignore[arg-type]
            finalizer=finalizer,
            finalizer_path=path,
        )

    assert writer.calls == []
