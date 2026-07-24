from uuid import uuid4

import pytest
from pydantic import ValidationError

from video_channel_manager.application.plan_guard import PlanGuard
from video_channel_manager.config.settings import AppSettings
from video_channel_manager.domain.enums import OperationType, PlatformName, RiskLevel
from video_channel_manager.domain.models import RemoteRef
from video_channel_manager.exchange.change_plan import ChangeOperation, ChangePlan


def channel_ref(remote_id: str = "UC1") -> RemoteRef:
    return RemoteRef(platform=PlatformName.YOUTUBE, channel_id="UC1", remote_id=remote_id)


def test_valid_playlist_plan_passes_guard() -> None:
    plan = ChangePlan(
        source_snapshot_id=uuid4(),
        title="Playlist cleanup",
        channel=channel_ref(),
        operations=[
            ChangeOperation(
                operation=OperationType.ADD_TO_COLLECTION,
                target=channel_ref("v1"),
                payload={"collection_id": "p1"},
                expected_revision="rev-v1",
                rationale="Missing author playlist",
            )
        ],
    )
    assert PlanGuard(AppSettings()).validate(plan).is_valid


def test_duplicate_operation_ids_are_rejected() -> None:
    operation_id = uuid4()
    operation = ChangeOperation(
        operation_id=operation_id,
        operation=OperationType.UPDATE_VIDEO_TITLE,
        target=channel_ref("v1"),
        payload={"title": "New title"},
        expected_revision="rev-v1",
        rationale="Normalize title",
    )
    with pytest.raises(ValidationError, match="unique"):
        ChangePlan(
            source_snapshot_id=uuid4(),
            title="Duplicate IDs",
            channel=channel_ref(),
            operations=[operation, operation.model_copy(deep=True)],
        )


def test_destructive_operation_is_blocked_by_default() -> None:
    plan = ChangePlan(
        source_snapshot_id=uuid4(),
        title="Delete duplicate",
        channel=channel_ref(),
        operations=[
            ChangeOperation(
                operation=OperationType.DELETE_VIDEO,
                target=channel_ref("v1"),
                expected_revision="rev-v1",
                risk=RiskLevel.DESTRUCTIVE,
                rationale="Confirmed duplicate",
            )
        ],
    )
    result = PlanGuard(AppSettings()).validate(plan)
    assert not result.is_valid
    assert result.errors[0].code == "destructive_operation_disabled"


def test_missing_expected_revision_is_rejected_by_policy() -> None:
    plan = ChangePlan(
        source_snapshot_id=uuid4(),
        title="Unsafe update",
        channel=channel_ref(),
        operations=[
            ChangeOperation(
                operation=OperationType.UPDATE_VIDEO_TITLE,
                target=channel_ref("v1"),
                payload={"title": "New title"},
                rationale="Normalize title",
            )
        ],
    )
    result = PlanGuard(AppSettings()).validate(plan)
    assert any(issue.code == "missing_expected_revision" for issue in result.errors)
