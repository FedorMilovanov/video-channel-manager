from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from video_channel_manager.domain.enums import DESTRUCTIVE_OPERATIONS, OperationType, RiskLevel
from video_channel_manager.domain.models import RemoteRef, StrictModel


class ChangeOperation(StrictModel):
    operation_id: UUID = Field(default_factory=uuid4)
    operation: OperationType
    target: RemoteRef
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_revision: str | None = None
    risk: RiskLevel = RiskLevel.LOW
    rationale: str = Field(min_length=1)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_operation_payload(self) -> "ChangeOperation":
        required_fields: dict[OperationType, tuple[str, ...]] = {
            OperationType.UPDATE_VIDEO_TITLE: ("title",),
            OperationType.UPDATE_VIDEO_DESCRIPTION: ("description",),
            OperationType.REPLACE_DESCRIPTION_TEXT: ("old", "new"),
            OperationType.ADD_DESCRIPTION_BLOCK: ("block",),
            OperationType.REMOVE_DESCRIPTION_BLOCK: ("block_id",),
            OperationType.CREATE_COLLECTION: ("title", "kind"),
            OperationType.UPDATE_COLLECTION: ("changes",),
            OperationType.ADD_TO_COLLECTION: ("collection_id",),
            OperationType.REMOVE_FROM_COLLECTION: ("collection_id",),
            OperationType.REORDER_COLLECTION_ITEM: ("collection_id", "position"),
            OperationType.SET_THUMBNAIL: ("source",),
            OperationType.CHANGE_PRIVACY: ("privacy_status",),
            OperationType.TRANSFER_VIDEO: ("destination_channel_id",),
        }
        missing = [key for key in required_fields.get(self.operation, ()) if key not in self.payload]
        if missing:
            raise ValueError(f"{self.operation} requires payload fields: {', '.join(missing)}")
        if self.operation in DESTRUCTIVE_OPERATIONS and self.risk != RiskLevel.DESTRUCTIVE:
            raise ValueError("destructive operations must declare risk='destructive'")
        return self


class ChangePlan(StrictModel):
    """A machine-readable plan prepared by an external AI or human editor."""

    schema_name: Literal["video-manager.change-plan"] = "video-manager.change-plan"
    schema_version: Literal["1.0"] = "1.0"
    plan_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_snapshot_id: UUID
    title: str = Field(min_length=1)
    channel: RemoteRef
    operations: list[ChangeOperation] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def validate_plan_integrity(self) -> "ChangePlan":
        operation_ids = [item.operation_id for item in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("operation_id values must be unique inside a ChangePlan")
        for item in self.operations:
            if item.target.platform != self.channel.platform or item.target.channel_id != self.channel.channel_id:
                raise ValueError("every operation target must belong to the plan channel")
        return self
