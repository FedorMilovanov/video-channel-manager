from __future__ import annotations

from video_channel_manager.platforms.vk.milovi_issue323_planner import (
    Issue323Capability,
    Issue323ItemPlan,
    Issue323NextAction,
)


def _plan(*capabilities: Issue323Capability) -> Issue323ItemPlan:
    return Issue323ItemPlan(
        action=Issue323NextAction.RESUME_WALL_ONLY,
        required_capabilities=capabilities,
        forbids_reupload=True,
        forbids_repost=False,
    )


def test_plan_digest_is_deterministic_and_sha256_prefixed() -> None:
    first = _plan(Issue323Capability.CREATE_WALL)
    second = _plan(Issue323Capability.CREATE_WALL)

    assert first.digest == second.digest
    assert first.digest.startswith("sha256:")
    assert len(first.digest) == len("sha256:") + 64


def test_plan_digest_changes_when_capability_changes() -> None:
    wall_only = _plan(Issue323Capability.CREATE_WALL)
    read_then_wall = _plan(Issue323Capability.READ_PROVIDER_STATE, Issue323Capability.CREATE_WALL)

    assert wall_only.digest != read_then_wall.digest


def test_plan_digest_changes_when_replay_constraint_changes() -> None:
    safe = _plan(Issue323Capability.CREATE_WALL)
    different = Issue323ItemPlan(
        action=safe.action,
        required_capabilities=safe.required_capabilities,
        forbids_reupload=False,
        forbids_repost=safe.forbids_repost,
    )

    assert safe.digest != different.digest
