from __future__ import annotations

from pathlib import Path
from typing import Any

import video_channel_manager.platforms.vk.milovi_issue323_finalize as finalize
from video_channel_manager.platforms.vk.milovi_issue323_planner import Issue323Capability

CLIP_ID = "-68859909_456239240"


def _journal(item: dict[str, Any]) -> dict[str, Any]:
    return {"source_snapshot_id": "snapshot", "items": {"source": item}}


def test_clip_verified_grants_create_wall_and_persists_plan(monkeypatch, tmp_path: Path) -> None:
    item: dict[str, Any] = {
        "status": "clip_verified",
        "clip_remote_id": CLIP_ID,
        "clip_origin": "journal",
    }
    journal = _journal(item)
    capabilities: list[Issue323Capability] = []
    monkeypatch.setattr(
        finalize,
        "_require_executor_capability",
        lambda _plan, capability: capabilities.append(capability),
    )
    monkeypatch.setattr(finalize, "_save", lambda *_args, **_kwargs: None)

    plan = finalize._authorize_wall_continuation(item, journal, tmp_path / "journal.json", CLIP_ID)

    assert capabilities == [Issue323Capability.CREATE_WALL]
    assert plan.required_capabilities == (Issue323Capability.CREATE_WALL,)
    assert item["wall_execution_plan"]["plan"]["action"] == "resume_wall_only_without_reupload"
    assert item["wall_execution_plan"]["plan_digest"] == plan.digest


def test_wall_intent_grants_reconcile_only_and_never_create_wall(monkeypatch, tmp_path: Path) -> None:
    item: dict[str, Any] = {
        "status": "wall_intent",
        "clip_remote_id": CLIP_ID,
        "clip_origin": "journal",
    }
    journal = _journal(item)
    capabilities: list[Issue323Capability] = []
    monkeypatch.setattr(
        finalize,
        "_require_executor_capability",
        lambda _plan, capability: capabilities.append(capability),
    )
    monkeypatch.setattr(finalize, "_save", lambda *_args, **_kwargs: None)

    plan = finalize._authorize_wall_continuation(item, journal, tmp_path / "journal.json", CLIP_ID)

    assert capabilities == [Issue323Capability.RECONCILE_PROVIDER_EFFECT]
    assert Issue323Capability.CREATE_WALL not in plan.required_capabilities
    assert plan.forbids_repost is True
    assert item["wall_execution_plan"]["plan"]["action"] == "reconcile_existing_wall_without_repost"


def test_wall_may_exist_grants_reconcile_only(monkeypatch, tmp_path: Path) -> None:
    item: dict[str, Any] = {
        "status": "wall_may_exist",
        "clip_remote_id": CLIP_ID,
        "clip_origin": "journal",
    }
    journal = _journal(item)
    capabilities: list[Issue323Capability] = []
    monkeypatch.setattr(
        finalize,
        "_require_executor_capability",
        lambda _plan, capability: capabilities.append(capability),
    )
    monkeypatch.setattr(finalize, "_save", lambda *_args, **_kwargs: None)

    plan = finalize._authorize_wall_continuation(item, journal, tmp_path / "journal.json", CLIP_ID)

    assert capabilities == [Issue323Capability.RECONCILE_PROVIDER_EFFECT]
    assert plan.forbids_repost is True
