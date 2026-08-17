from __future__ import annotations

from typing import Any

import pytest

from video_channel_manager.platforms.vk.milovi_issue323_planner import (
    Issue323Capability,
    Issue323ItemState,
    Issue323NextAction,
    plan_issue323_item,
)
from video_channel_manager.platforms.vk.milovi_issue323_promotion_spec import promotion_text_sha256
from video_channel_manager.platforms.vk.milovi_issue323_read_model import (
    MiloviIssue323ReadModelBlocked,
    _resolve_wall_incarnation,
)
from video_channel_manager.platforms.vk.milovi_rollout_sources import ROLL_OUT_IDS
from video_channel_manager.platforms.vk.upload_lifecycle import UploadStage
from video_channel_manager.platforms.vk.wall_safety import (
    VkWallPostFingerprint,
    VkWallSnapshot,
    VkWallSurface,
)

OWNER_ID = -68859909
COMMUNITY_ID = 68859909
CLIP_REMOTE_ID = "-68859909_456239240"
WALL_REMOTE_ID = "-68859909_500"
SUCCESSOR_REMOTE_ID = "-68859909_501"
PUBLISH_DATE = 1786906800
BEFORE_SLOT = PUBLISH_DATE - 3600
AFTER_SLOT = PUBLISH_DATE + 3600


class _ReadOnlyWallProvider:
    """Minimal wall-read surface: the matrix has no provider mutation method."""

    def __init__(self, posts: dict[int, dict[str, Any]]) -> None:
        self.posts = posts
        self.read_post_calls: list[int] = []

    def read_post(self, *, community_id: int, post_id: int) -> dict[str, Any] | None:
        assert community_id == COMMUNITY_ID
        self.read_post_calls.append(post_id)
        value = self.posts.get(post_id)
        return dict(value) if value is not None else None


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


@pytest.mark.parametrize(
    ("state", "expected_action"),
    [
        pytest.param(
            _state(),
            Issue323NextAction.REQUIRE_EXISTING_CLIP_PREFLIGHT,
            id="empty-state-needs-read-only-inventory-preflight",
        ),
        pytest.param(
            _state(existing_clip_preflight_complete=True),
            Issue323NextAction.ELIGIBLE_FOR_SINGLE_UPLOAD,
            id="one-clean-preflight-path-can-create-clip",
        ),
        pytest.param(
            _state(
                upload_stage=UploadStage.RESERVATION_INTENT_COMMITTED,
                provider_effect_durable=True,
            ),
            Issue323NextAction.RECONCILE_PROVIDER_EFFECT_WITHOUT_REPLAY,
            id="durable-intent-without-id-reconciles-no-replay",
        ),
        pytest.param(
            _state(
                upload_stage=UploadStage.UNKNOWN_REQUIRES_RECONCILIATION,
                provider_effect_durable=True,
            ),
            Issue323NextAction.RECONCILE_PROVIDER_EFFECT_WITHOUT_REPLAY,
            id="unknown-provider-effect-reconciles-no-replay",
        ),
        pytest.param(
            _state(
                durable_status="upload_in_progress",
                upload_stage=UploadStage.RESERVED,
                provider_effect_durable=True,
                clip_remote_id=CLIP_REMOTE_ID,
                clip_identity_origin="upload_record",
            ),
            Issue323NextAction.RECONCILE_PROVIDER_EFFECT_THEN_WALL,
            id="reserved-clip-identity-never-reuploads",
        ),
        pytest.param(
            _state(
                durable_status="upload_in_progress",
                upload_stage=UploadStage.PROCESSING,
                provider_effect_durable=True,
                clip_remote_id=CLIP_REMOTE_ID,
                clip_identity_origin="upload_record",
            ),
            Issue323NextAction.RECONCILE_PROVIDER_EFFECT_THEN_WALL,
            id="processing-clip-identity-never-reuploads",
        ),
        pytest.param(
            _state(
                durable_status="upload_in_progress",
                upload_stage=UploadStage.VERIFIED,
                provider_effect_durable=True,
                clip_remote_id=CLIP_REMOTE_ID,
                clip_identity_origin="upload_record",
            ),
            Issue323NextAction.RESUME_FROM_VERIFIED_CLIP,
            id="verified-upload-resumes-wall-without-reupload",
        ),
        pytest.param(
            _state(
                durable_status="clip_verified",
                clip_remote_id=CLIP_REMOTE_ID,
                clip_identity_origin="journal",
            ),
            Issue323NextAction.RESUME_WALL_ONLY,
            id="durable-clip-verified-resumes-wall-only",
        ),
        pytest.param(
            _state(
                clip_remote_id=CLIP_REMOTE_ID,
                clip_identity_origin="inventory",
                existing_clip_preflight_complete=True,
            ),
            Issue323NextAction.ADOPT_EXISTING_CLIP,
            id="inventory-hit-is-adopt-only",
        ),
        pytest.param(
            _state(
                durable_status="wall_intent",
                clip_remote_id=CLIP_REMOTE_ID,
                wall_remote_id=WALL_REMOTE_ID,
            ),
            Issue323NextAction.RECONCILE_EXISTING_WALL,
            id="wall-intent-is-reconcile-only",
        ),
        pytest.param(
            _state(
                durable_status="wall_may_exist",
                clip_remote_id=CLIP_REMOTE_ID,
                wall_remote_id=WALL_REMOTE_ID,
            ),
            Issue323NextAction.RECONCILE_EXISTING_WALL,
            id="wall-may-exist-is-reconcile-only",
        ),
        pytest.param(
            _state(durable_status="wall_verified", clip_remote_id=CLIP_REMOTE_ID),
            Issue323NextAction.STOP_CONFLICT,
            id="verified-wall-without-id-stops",
        ),
        pytest.param(
            _state(
                durable_status="wall_verified",
                clip_remote_id=CLIP_REMOTE_ID,
                wall_remote_id=WALL_REMOTE_ID,
                clip_copy_state="promoted",
                wall_copy_state="promoted",
            ),
            Issue323NextAction.PHASE_A_COMPLETE_PROMOTED,
            id="promoted-wall-is-terminal",
        ),
        pytest.param(
            _state(
                durable_status="wall_verified",
                clip_remote_id=CLIP_REMOTE_ID,
                wall_remote_id=WALL_REMOTE_ID,
                clip_copy_state="unreviewed_exact",
                wall_copy_state="legacy",
            ),
            Issue323NextAction.PHASE_A_COMPLETE_PROMOTION_PENDING,
            id="manual-copy-never-grants-phase-a-provider-capability",
        ),
    ],
)
def test_planner_authority_state_space(
    state: Issue323ItemState,
    expected_action: Issue323NextAction,
) -> None:
    """Only one normalized state may grant Clip creation; durable effects never do."""

    plan = plan_issue323_item(state)

    assert plan.action is expected_action
    if expected_action is Issue323NextAction.ELIGIBLE_FOR_SINGLE_UPLOAD:
        assert plan.required_capabilities == (Issue323Capability.CREATE_CLIP,)
        assert plan.forbids_reupload is False
    else:
        assert Issue323Capability.CREATE_CLIP not in plan.required_capabilities

    if state.provider_effect_durable or state.clip_remote_id is not None or state.wall_remote_id is not None:
        assert plan.forbids_reupload is True

    if state.wall_remote_id is not None:
        assert Issue323Capability.CREATE_CLIP not in plan.required_capabilities
        if state.durable_status in {"wall_intent", "wall_may_exist", "wall_verified"}:
            assert plan.forbids_repost is True


def _raw_wall_post(post_id: int, *, deleted: bool = False, text: str = "reviewed wall") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "owner_id": OWNER_ID,
        "id": post_id,
        "date": PUBLISH_DATE,
    }
    if deleted:
        payload["is_deleted"] = True
        return payload
    payload.update(
        text=text,
        attachments=[
            {
                "type": "video",
                "video": {"owner_id": OWNER_ID, "id": 456239240},
            }
        ],
    )
    return payload


def _fingerprint(
    remote_id: str,
    *,
    surface: VkWallSurface,
    text: str = "reviewed wall",
) -> VkWallPostFingerprint:
    owner_text, post_text = remote_id.split("_", 1)
    return VkWallPostFingerprint(
        owner_id=int(owner_text),
        post_id=int(post_text),
        surface=surface,
        publish_date=PUBLISH_DATE,
        text_sha256=f"sha256:{promotion_text_sha256(text)}",
        attachments=(f"video{CLIP_REMOTE_ID}",),
    )


def _snapshot(*posts: VkWallPostFingerprint) -> VkWallSnapshot:
    return VkWallSnapshot(
        community_id=COMMUNITY_ID,
        captured_at="2026-08-16T18:00:00+00:00",
        complete=True,
        published_pages=1,
        postponed_pages=1,
        posts=posts,
    )


def _journal(*, second_wall_remote_id: str | None = None) -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {source_id: {} for source_id in ROLL_OUT_IDS}
    items[ROLL_OUT_IDS[0]]["wall_remote_id"] = WALL_REMOTE_ID
    if second_wall_remote_id is not None:
        items[ROLL_OUT_IDS[1]]["wall_remote_id"] = second_wall_remote_id
    return {"items": items}


def test_wall_incarnation_matrix_exact_postponed_before_slot() -> None:
    provider = _ReadOnlyWallProvider({500: _raw_wall_post(500)})

    remote_id, surface, _raw, mode = _resolve_wall_incarnation(
        writer=provider,  # type: ignore[arg-type]
        snapshot=_snapshot(_fingerprint(WALL_REMOTE_ID, surface=VkWallSurface.POSTPONED)),
        journal=_journal(),
        wall_remote_id=WALL_REMOTE_ID,
        clip_remote_id=CLIP_REMOTE_ID,
        publish_date=PUBLISH_DATE,
        now_epoch=BEFORE_SLOT,
    )

    assert (remote_id, surface, mode) == (WALL_REMOTE_ID, VkWallSurface.POSTPONED, "journaled_id")
    assert provider.read_post_calls == [500]


def test_wall_incarnation_matrix_exact_old_id_can_survive_aggregate_omission_after_slot() -> None:
    provider = _ReadOnlyWallProvider({500: _raw_wall_post(500)})

    remote_id, surface, _raw, mode = _resolve_wall_incarnation(
        writer=provider,  # type: ignore[arg-type]
        snapshot=_snapshot(),
        journal=_journal(),
        wall_remote_id=WALL_REMOTE_ID,
        clip_remote_id=CLIP_REMOTE_ID,
        publish_date=PUBLISH_DATE,
        now_epoch=AFTER_SLOT,
    )

    assert (remote_id, surface, mode) == (WALL_REMOTE_ID, VkWallSurface.PUBLISHED, "exact_old_id")
    assert provider.read_post_calls == [500]


def test_wall_incarnation_matrix_unique_successor_is_adoptable_only_after_slot() -> None:
    provider = _ReadOnlyWallProvider(
        {
            500: _raw_wall_post(500, deleted=True),
            501: _raw_wall_post(501),
        }
    )

    remote_id, surface, _raw, mode = _resolve_wall_incarnation(
        writer=provider,  # type: ignore[arg-type]
        snapshot=_snapshot(_fingerprint(SUCCESSOR_REMOTE_ID, surface=VkWallSurface.PUBLISHED)),
        journal=_journal(),
        wall_remote_id=WALL_REMOTE_ID,
        clip_remote_id=CLIP_REMOTE_ID,
        publish_date=PUBLISH_DATE,
        now_epoch=AFTER_SLOT,
    )

    assert (remote_id, surface, mode) == (SUCCESSOR_REMOTE_ID, VkWallSurface.PUBLISHED, "published_successor")
    assert provider.read_post_calls == [500, 501]


@pytest.mark.parametrize(
    ("snapshot", "posts", "now_epoch", "message"),
    [
        pytest.param(
            _snapshot(),
            {},
            BEFORE_SLOT,
            "disappeared before its frozen slot",
            id="cardinality-zero-before-slot-stops",
        ),
        pytest.param(
            _snapshot(_fingerprint(WALL_REMOTE_ID, surface=VkWallSurface.PUBLISHED)),
            {500: _raw_wall_post(500)},
            BEFORE_SLOT,
            "published before its scheduled slot",
            id="published-before-slot-stops",
        ),
        pytest.param(
            _snapshot(),
            {500: _raw_wall_post(500, deleted=True)},
            AFTER_SLOT,
            "No published successor exists",
            id="cardinality-zero-after-slot-tombstone-stops",
        ),
        pytest.param(
            _snapshot(
                _fingerprint(SUCCESSOR_REMOTE_ID, surface=VkWallSurface.PUBLISHED),
                _fingerprint("-68859909_502", surface=VkWallSurface.PUBLISHED),
            ),
            {500: _raw_wall_post(500, deleted=True)},
            AFTER_SLOT,
            "Published successor is ambiguous",
            id="cardinality-more-than-one-successor-stops",
        ),
        pytest.param(
            _snapshot(
                _fingerprint(WALL_REMOTE_ID, surface=VkWallSurface.POSTPONED),
                _fingerprint(SUCCESSOR_REMOTE_ID, surface=VkWallSurface.PUBLISHED),
            ),
            {500: _raw_wall_post(500)},
            AFTER_SLOT,
            "Logical wall mapping is duplicated",
            id="old-id-plus-successor-duplicate-stops",
        ),
    ],
)
def test_wall_incarnation_blocking_state_space(
    snapshot: VkWallSnapshot,
    posts: dict[int, dict[str, Any]],
    now_epoch: int,
    message: str,
) -> None:
    provider = _ReadOnlyWallProvider(posts)

    with pytest.raises(MiloviIssue323ReadModelBlocked, match=message):
        _resolve_wall_incarnation(
            writer=provider,  # type: ignore[arg-type]
            snapshot=snapshot,
            journal=_journal(),
            wall_remote_id=WALL_REMOTE_ID,
            clip_remote_id=CLIP_REMOTE_ID,
            publish_date=PUBLISH_DATE,
            now_epoch=now_epoch,
        )


def test_wall_successor_cannot_collide_with_another_journaled_source() -> None:
    provider = _ReadOnlyWallProvider(
        {
            500: _raw_wall_post(500, deleted=True),
            501: _raw_wall_post(501),
        }
    )

    with pytest.raises(MiloviIssue323ReadModelBlocked, match="collides with another journaled wall ID"):
        _resolve_wall_incarnation(
            writer=provider,  # type: ignore[arg-type]
            snapshot=_snapshot(_fingerprint(SUCCESSOR_REMOTE_ID, surface=VkWallSurface.PUBLISHED)),
            journal=_journal(second_wall_remote_id=SUCCESSOR_REMOTE_ID),
            wall_remote_id=WALL_REMOTE_ID,
            clip_remote_id=CLIP_REMOTE_ID,
            publish_date=PUBLISH_DATE,
            now_epoch=AFTER_SLOT,
        )


def test_state_space_fake_has_no_provider_mutation_surface() -> None:
    forbidden = {
        "begin_upload",
        "upload_file",
        "edit_video",
        "edit_post",
        "delete_post",
        "create_post",
    }

    assert forbidden.isdisjoint(dir(_ReadOnlyWallProvider))
    public_methods = {name for name in dir(_ReadOnlyWallProvider) if not name.startswith("_")}
    assert public_methods == {"read_post"}
