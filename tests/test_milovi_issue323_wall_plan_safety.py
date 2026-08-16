from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_planner import (
    Issue323Capability,
    Issue323ItemState,
    Issue323NextAction,
    plan_issue323_item,
)


def _state(*, durable_status: str, wall_remote_id: str | None = None) -> Issue323ItemState:
    return Issue323ItemState(
        durable_status=durable_status,
        upload_stage=None,
        provider_effect_durable=False,
        clip_remote_id="-68859909_456239240",
        clip_identity_origin="journal",
        wall_remote_id=wall_remote_id,
        clip_copy_state="legacy",
        wall_copy_state=None,
        existing_clip_preflight_complete=True,
    )


@pytest.mark.parametrize("durable_status", ["wall_intent", "wall_may_exist"])
def test_durable_wall_intent_requires_reconciliation_and_never_create_wall(durable_status: str) -> None:
    plan = plan_issue323_item(_state(durable_status=durable_status))

    assert plan.action is Issue323NextAction.RECONCILE_EXISTING_WALL
    assert plan.required_capabilities == (
        Issue323Capability.READ_PROVIDER_STATE,
        Issue323Capability.RECONCILE_PROVIDER_EFFECT,
    )
    assert Issue323Capability.CREATE_WALL not in plan.required_capabilities
    assert plan.forbids_reupload is True
    assert plan.forbids_repost is True


def test_wall_verified_without_remote_identity_fails_closed() -> None:
    plan = plan_issue323_item(_state(durable_status="wall_verified"))

    assert plan.action is Issue323NextAction.STOP_CONFLICT
    assert plan.required_capabilities == ()
    assert plan.forbids_reupload is True
    assert plan.forbids_repost is True


def test_existing_nonverified_wall_identity_requires_reconciliation() -> None:
    plan = plan_issue323_item(
        _state(durable_status="pending", wall_remote_id="-68859909_480")
    )

    assert plan.action is Issue323NextAction.RECONCILE_EXISTING_WALL
    assert Issue323Capability.CREATE_WALL not in plan.required_capabilities
