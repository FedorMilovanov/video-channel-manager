from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage

PLAN_SCHEMA_VERSION = 1


class Issue323NextAction(StrEnum):
    STOP_CONFLICT = "stop_conflict"
    REQUIRE_EXISTING_CLIP_PREFLIGHT = "require_existing_clip_preflight"
    ELIGIBLE_FOR_SINGLE_UPLOAD = "eligible_for_single_upload_after_executor_existing_clip_preflight"
    RECONCILE_PROVIDER_EFFECT_WITHOUT_REPLAY = "reconcile_provider_effect_without_replay"
    RESUME_FROM_VERIFIED_CLIP = "resume_from_verified_clip_without_reupload_then_wall"
    RESUME_WALL_ONLY = "resume_wall_only_without_reupload"
    ADOPT_EXISTING_CLIP = "adopt_existing_clip_without_reupload_then_wall"
    RECONCILE_PROVIDER_EFFECT_THEN_WALL = "reconcile_provider_effect_without_reupload_then_wall"
    RESUME_WALL_WITHOUT_REUPLOAD = "resume_wall_without_reupload"
    RECONCILE_EXISTING_WALL = "reconcile_existing_wall_without_repost"
    PHASE_A_COMPLETE_PROMOTED = "phase_a_complete_promoted"
    PHASE_A_COMPLETE_PROMOTION_PENDING = "phase_a_complete_promotion_pending"


class Issue323Capability(StrEnum):
    READ_PROVIDER_STATE = "read_provider_state"
    ADOPT_DURABLE_CLIP = "adopt_durable_clip"
    CREATE_CLIP = "create_clip"
    CREATE_WALL = "create_wall"
    RECONCILE_PROVIDER_EFFECT = "reconcile_provider_effect"


@dataclass(frozen=True, slots=True)
class Issue323ItemState:
    durable_status: str
    upload_stage: UploadStage | None
    provider_effect_durable: bool
    clip_remote_id: str | None
    clip_identity_origin: str | None
    wall_remote_id: str | None
    clip_copy_state: str | None
    wall_copy_state: str | None
    existing_clip_preflight_complete: bool


@dataclass(frozen=True, slots=True)
class Issue323ItemPlan:
    action: Issue323NextAction
    required_capabilities: tuple[Issue323Capability, ...]
    forbids_reupload: bool
    forbids_repost: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "action": self.action.value,
            "required_capabilities": [capability.value for capability in self.required_capabilities],
            "forbids_reupload": self.forbids_reupload,
            "forbids_repost": self.forbids_repost,
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _plan(
    action: Issue323NextAction,
    *capabilities: Issue323Capability,
    forbids_reupload: bool,
    forbids_repost: bool,
) -> Issue323ItemPlan:
    return Issue323ItemPlan(
        action=action,
        required_capabilities=tuple(capabilities),
        forbids_reupload=forbids_reupload,
        forbids_repost=forbids_repost,
    )


def blocked_issue323_item_plan() -> Issue323ItemPlan:
    return _plan(
        Issue323NextAction.STOP_CONFLICT,
        forbids_reupload=True,
        forbids_repost=True,
    )


def plan_issue323_item(state: Issue323ItemState) -> Issue323ItemPlan:
    """Reduce normalized durable/provider evidence into one provider-inert continuation plan."""

    if state.wall_remote_id is not None:
        if state.durable_status != "wall_verified":
            return _plan(
                Issue323NextAction.RECONCILE_EXISTING_WALL,
                Issue323Capability.READ_PROVIDER_STATE,
                Issue323Capability.RECONCILE_PROVIDER_EFFECT,
                forbids_reupload=True,
                forbids_repost=True,
            )
        if state.clip_copy_state == "promoted" and state.wall_copy_state == "promoted":
            return _plan(
                Issue323NextAction.PHASE_A_COMPLETE_PROMOTED,
                forbids_reupload=True,
                forbids_repost=True,
            )
        return _plan(
            Issue323NextAction.PHASE_A_COMPLETE_PROMOTION_PENDING,
            forbids_reupload=True,
            forbids_repost=True,
        )

    if state.clip_remote_id is not None:
        if (
            state.provider_effect_durable
            and state.upload_stage is UploadStage.VERIFIED
            and state.clip_identity_origin == "upload_record"
        ):
            return _plan(
                Issue323NextAction.RESUME_FROM_VERIFIED_CLIP,
                Issue323Capability.ADOPT_DURABLE_CLIP,
                Issue323Capability.CREATE_WALL,
                forbids_reupload=True,
                forbids_repost=False,
            )
        if state.durable_status == "clip_verified":
            return _plan(
                Issue323NextAction.RESUME_WALL_ONLY,
                Issue323Capability.CREATE_WALL,
                forbids_reupload=True,
                forbids_repost=False,
            )
        if state.clip_identity_origin == "inventory":
            return _plan(
                Issue323NextAction.ADOPT_EXISTING_CLIP,
                Issue323Capability.ADOPT_DURABLE_CLIP,
                Issue323Capability.CREATE_WALL,
                forbids_reupload=True,
                forbids_repost=False,
            )
        if state.provider_effect_durable:
            return _plan(
                Issue323NextAction.RECONCILE_PROVIDER_EFFECT_THEN_WALL,
                Issue323Capability.READ_PROVIDER_STATE,
                Issue323Capability.RECONCILE_PROVIDER_EFFECT,
                forbids_reupload=True,
                forbids_repost=False,
            )
        return _plan(
            Issue323NextAction.RESUME_WALL_WITHOUT_REUPLOAD,
            Issue323Capability.CREATE_WALL,
            forbids_reupload=True,
            forbids_repost=False,
        )

    if state.provider_effect_durable:
        return _plan(
            Issue323NextAction.RECONCILE_PROVIDER_EFFECT_WITHOUT_REPLAY,
            Issue323Capability.READ_PROVIDER_STATE,
            Issue323Capability.RECONCILE_PROVIDER_EFFECT,
            forbids_reupload=True,
            forbids_repost=True,
        )

    if not state.existing_clip_preflight_complete:
        return _plan(
            Issue323NextAction.REQUIRE_EXISTING_CLIP_PREFLIGHT,
            Issue323Capability.READ_PROVIDER_STATE,
            forbids_reupload=True,
            forbids_repost=True,
        )

    return _plan(
        Issue323NextAction.ELIGIBLE_FOR_SINGLE_UPLOAD,
        Issue323Capability.CREATE_CLIP,
        forbids_reupload=False,
        forbids_repost=True,
    )
