from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_planner import (
    Issue323Capability,
    Issue323ItemState,
    Issue323NextAction,
    blocked_issue323_item_plan,
    plan_issue323_item,
)
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage


def _state(**overrides: object) -> Issue323ItemState:
    values: dict[str, object] = {
        "durable_status": "pending",
        "upload_stage": None,
        "provider_effect_durable": False,
        "clip_remote_id": None,
        "clip_identity_origin": None,
        "wall_remote_id": None,
        "clip_copy_state": None,
        "wall_copy_state": None,
        "existing_clip_preflight_complete": False,
    }
    values.update(overrides)
    return Issue323ItemState(**values)  # type: ignore[arg-type]


def test_clean_state_requires_existing_clip_preflight_before_upload_capability() -> None:
    plan = plan_issue323_item(_state())

    assert plan.action is Issue323NextAction.REQUIRE_EXISTING_CLIP_PREFLIGHT
    assert plan.required_capabilities == (Issue323Capability.READ_PROVIDER_STATE,)
    assert plan.forbids_reupload is True


def test_clean_state_after_empty_inventory_preflight_can_plan_one_clip_creation() -> None:
    plan = plan_issue323_item(_state(existing_clip_preflight_complete=True))

    assert plan.action is Issue323NextAction.ELIGIBLE_FOR_SINGLE_UPLOAD
    assert plan.required_capabilities == (Issue323Capability.CREATE_CLIP,)
    assert plan.forbids_reupload is False
    assert plan.forbids_repost is True


def test_inventory_hit_is_adopted_and_never_reuploaded() -> None:
    plan = plan_issue323_item(
        _state(
            clip_remote_id="-68859909_456239240",
            clip_identity_origin="inventory",
            existing_clip_preflight_complete=True,
        )
    )

    assert plan.action is Issue323NextAction.ADOPT_EXISTING_CLIP
    assert plan.required_capabilities == (
        Issue323Capability.ADOPT_DURABLE_CLIP,
        Issue323Capability.CREATE_WALL,
    )
    assert plan.forbids_reupload is True


def test_durable_verified_upload_record_is_adopted_without_reupload() -> None:
    plan = plan_issue323_item(
        _state(
            durable_status="upload_in_progress",
            upload_stage=UploadStage.VERIFIED,
            provider_effect_durable=True,
            clip_remote_id="-68859909_456239240",
            clip_identity_origin="upload_record",
        )
    )
    assert plan.action is Issue323NextAction.RESUME_FROM_VERIFIED_CLIP
    assert plan.required_capabilities == (
        Issue323Capability.ADOPT_DURABLE_CLIP,
        Issue323Capability.READ_PROVIDER_STATE,
        Issue323Capability.RECONCILE_PROVIDER_EFFECT,
        Issue323Capability.CREATE_WALL,
    )
    assert Issue323Capability.CREATE_CLIP not in plan.required_capabilities
    assert plan.forbids_reupload is True


def test_unresolved_provider_effect_never_grants_replay_capability() -> None:
    plan = plan_issue323_item(
        _state(
            upload_stage=UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
            provider_effect_durable=True,
        )
    )
    assert plan.action is Issue323NextAction.RECONCILE_PROVIDER_EFFECT_WITHOUT_REPLAY
    assert plan.required_capabilities == (
        Issue323Capability.READ_PROVIDER_STATE,
        Issue323Capability.RECONCILE_PROVIDER_EFFECT,
    )
    assert Issue323Capability.CREATE_CLIP not in plan.required_capabilities
    assert plan.forbids_reupload is True


def test_clip_verified_only_plans_wall_continuation() -> None:
    plan = plan_issue323_item(
        _state(
            durable_status="clip_verified",
            clip_remote_id="-68859909_456239240",
            clip_identity_origin="journal",
        )
    )
    assert plan.action is Issue323NextAction.RESUME_WALL_ONLY
    assert plan.required_capabilities == (Issue323Capability.CREATE_WALL,)
    assert plan.forbids_reupload is True


def test_existing_wall_mapping_never_grants_repost_or_reupload() -> None:
    plan = plan_issue323_item(
        _state(
            durable_status="wall_may_exist",
            clip_remote_id="-68859909_456239240",
            wall_remote_id="-68859909_480",
        )
    )
    assert plan.action is Issue323NextAction.RECONCILE_EXISTING_WALL
    assert plan.forbids_reupload is True
    assert plan.forbids_repost is True
    assert Issue323Capability.CREATE_CLIP not in plan.required_capabilities
    assert Issue323Capability.CREATE_WALL not in plan.required_capabilities


def test_completed_promoted_mapping_is_terminal_for_phase_a() -> None:
    plan = plan_issue323_item(
        _state(
            durable_status="wall_verified",
            clip_remote_id="-68859909_456239240",
            wall_remote_id="-68859909_480",
            clip_copy_state="promoted",
            wall_copy_state="promoted",
        )
    )
    assert plan.action is Issue323NextAction.PHASE_A_COMPLETE_PROMOTED
    assert plan.required_capabilities == ()
    assert plan.forbids_reupload is True
    assert plan.forbids_repost is True


def test_completed_legacy_mapping_is_promotion_pending_without_phase_a_write_capability() -> None:
    plan = plan_issue323_item(
        _state(
            durable_status="wall_verified",
            clip_remote_id="-68859909_456239240",
            wall_remote_id="-68859909_480",
            clip_copy_state="legacy",
            wall_copy_state="legacy",
        )
    )
    assert plan.action is Issue323NextAction.PHASE_A_COMPLETE_PROMOTION_PENDING
    assert plan.required_capabilities == ()
    assert plan.forbids_reupload is True
    assert plan.forbids_repost is True


def test_blocked_plan_grants_no_capability() -> None:
    plan = blocked_issue323_item_plan()

    assert plan.action is Issue323NextAction.STOP_CONFLICT
    assert plan.required_capabilities == ()
    assert plan.forbids_reupload is True
    assert plan.forbids_repost is True


def test_plan_serialization_is_deterministic_and_string_stable() -> None:
    state = _state(
        durable_status="clip_verified",
        clip_remote_id="-68859909_456239240",
        clip_identity_origin="journal",
    )

    first = plan_issue323_item(state).as_dict()
    second = plan_issue323_item(state).as_dict()

    assert first == second
    assert first == {
        "schema_version": 1,
        "action": "resume_wall_only_without_reupload",
        "required_capabilities": ["create_wall"],
        "forbids_reupload": True,
        "forbids_repost": False,
    }
