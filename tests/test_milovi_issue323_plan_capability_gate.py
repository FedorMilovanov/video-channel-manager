from __future__ import annotations

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_planner import (
    Issue323Capability,
    Issue323ItemPlan,
    Issue323NextAction,
    Issue323PlanCapabilityError,
    require_issue323_capability,
)


def _wall_plan() -> Issue323ItemPlan:
    return Issue323ItemPlan(
        action=Issue323NextAction.RESUME_WALL_ONLY,
        required_capabilities=(Issue323Capability.CREATE_WALL,),
        forbids_reupload=True,
        forbids_repost=False,
    )


def test_exact_planned_capability_is_accepted() -> None:
    require_issue323_capability(_wall_plan(), Issue323Capability.CREATE_WALL)


def test_unplanned_clip_creation_fails_closed_with_plan_digest() -> None:
    plan = _wall_plan()

    with pytest.raises(Issue323PlanCapabilityError, match=plan.digest):
        require_issue323_capability(plan, Issue323Capability.CREATE_CLIP)
