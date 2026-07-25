from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)


class PlatformAccount(Base, TimestampMixin):
    __tablename__ = "platform_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("platform", "external_account_id", name="uq_platform_account"),)


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform_account_id: Mapped[str] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    remote_id: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    videos: Mapped[list[RemoteVideo]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    collections: Mapped[list[Collection]] = relationship(back_populates="channel", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("platform", "remote_id", name="uq_channel_remote"),)


class RemoteVideo(Base, TimestampMixin):
    __tablename__ = "remote_videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    remote_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    privacy_status: Mapped[str | None] = mapped_column(String(50))
    revision: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    channel: Mapped[Channel] = relationship(back_populates="videos")

    __table_args__ = (UniqueConstraint("channel_id", "remote_id", name="uq_video_remote"),)


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    remote_id: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    revision: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    channel: Mapped[Channel] = relationship(back_populates="collections")

    __table_args__ = (UniqueConstraint("channel_id", "remote_id", name="uq_collection_remote"),)


class CollectionMembership(Base, TimestampMixin):
    __tablename__ = "collection_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    video_id: Mapped[str] = mapped_column(ForeignKey("remote_videos.id", ondelete="CASCADE"), nullable=False)
    remote_membership_id: Mapped[str | None] = mapped_column(String(255))
    position: Mapped[int | None] = mapped_column(Integer)
    revision: Mapped[str | None] = mapped_column(String(128))

    __table_args__ = (UniqueConstraint("collection_id", "video_id", name="uq_collection_video"),)


class AuditSnapshot(Base, TimestampMixin):
    __tablename__ = "audit_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)


class AuditFinding(Base, TimestampMixin):
    __tablename__ = "audit_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("audit_snapshots.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)


class ChangePlanEntity(Base, TimestampMixin):
    __tablename__ = "change_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("audit_snapshots.id", ondelete="RESTRICT"), nullable=False)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="imported", nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class ChangeOperationEntity(Base, TimestampMixin):
    __tablename__ = "change_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("change_plans.id", ondelete="CASCADE"), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    target_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    risk: Mapped[str] = mapped_column(String(30), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expected_revision: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)


class OperationAttempt(Base):
    __tablename__ = "operation_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation_id: Mapped[str] = mapped_column(ForeignKey("change_operations.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    response_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("operation_id", "attempt_number", name="uq_operation_attempt"),)
