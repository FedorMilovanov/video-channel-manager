from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from video_channel_manager.domain.enums import ChannelKind, CollectionKind, PlatformName


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RemoteRef(StrictModel):
    platform: PlatformName
    channel_id: str = Field(min_length=1)
    remote_id: str = Field(min_length=1)

    @field_validator("channel_id", "remote_id")
    @classmethod
    def strip_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("identifier cannot be blank")
        return value

    @property
    def stable_key(self) -> str:
        return f"{self.platform}:{self.channel_id}:{self.remote_id}"


class ChannelRecord(StrictModel):
    ref: RemoteRef
    title: str = Field(min_length=1)
    kind: ChannelKind
    description: str = ""
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoRecord(StrictModel):
    ref: RemoteRef
    title: str = Field(min_length=1)
    description: str = ""
    duration_seconds: int | None = Field(default=None, ge=0)
    published_at: datetime | None = None
    privacy_status: str | None = None
    tags: list[str] = Field(default_factory=list)
    thumbnail_url: str | None = None
    revision: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectionRecord(StrictModel):
    ref: RemoteRef
    title: str = Field(min_length=1)
    kind: CollectionKind
    description: str = ""
    privacy_status: str | None = None
    revision: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectionMembership(StrictModel):
    collection_ref: RemoteRef
    video_ref: RemoteRef
    position: int | None = Field(default=None, ge=0)
    membership_id: str | None = None
    revision: str | None = None
