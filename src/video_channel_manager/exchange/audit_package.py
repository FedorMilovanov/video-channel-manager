from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from video_channel_manager.domain.models import (
    ChannelRecord,
    CollectionMembership,
    CollectionRecord,
    StrictModel,
    VideoRecord,
)


class AuditFinding(StrictModel):
    finding_id: UUID = Field(default_factory=uuid4)
    rule_id: str = Field(min_length=1)
    severity: Literal["info", "warning", "error"]
    subject_key: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class AuditPackage(StrictModel):
    """Versioned read-only snapshot exported for a human or external AI."""

    schema_name: Literal["video-manager.audit-package"] = "video-manager.audit-package"
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: UUID = Field(default_factory=uuid4)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    channel: ChannelRecord
    videos: list[VideoRecord] = Field(default_factory=list)
    collections: list[CollectionRecord] = Field(default_factory=list)
    memberships: list[CollectionMembership] = Field(default_factory=list)
    findings: list[AuditFinding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "AuditPackage":
        channel = self.channel.ref
        video_keys = {item.ref.stable_key for item in self.videos}
        collection_keys = {item.ref.stable_key for item in self.collections}

        all_refs = [self.channel.ref, *(item.ref for item in self.videos), *(item.ref for item in self.collections)]
        for ref in all_refs:
            if ref.platform != channel.platform or ref.channel_id != channel.channel_id:
                raise ValueError("all remote objects in an AuditPackage must belong to its channel")

        for membership in self.memberships:
            if membership.video_ref.stable_key not in video_keys:
                raise ValueError(f"membership references unknown video: {membership.video_ref.stable_key}")
            if membership.collection_ref.stable_key not in collection_keys:
                raise ValueError(f"membership references unknown collection: {membership.collection_ref.stable_key}")
        return self
