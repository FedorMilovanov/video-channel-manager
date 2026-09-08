"""Initial channel manager schema.

Revision ID: 0001
Revises:
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Freeze the original 0001 baseline. Using every table in current Base.metadata
# would make later ORM models appear retroactively in this historical migration
# and then collide with their own subsequent Alembic revisions on fresh installs.
_BASELINE_TABLE_NAMES = (
    "workspaces",
    "platform_accounts",
    "channels",
    "remote_videos",
    "collections",
    "collection_memberships",
    "audit_snapshots",
    "audit_findings",
    "change_plans",
    "change_operations",
    "operation_attempts",
)


def _baseline_tables():
    from video_channel_manager.persistence.models import Base

    return [Base.metadata.tables[name] for name in _BASELINE_TABLE_NAMES]


def upgrade() -> None:
    bind = op.get_bind()
    from video_channel_manager.persistence.models import Base

    Base.metadata.create_all(bind=bind, tables=_baseline_tables())


def downgrade() -> None:
    bind = op.get_bind()
    from video_channel_manager.persistence.models import Base

    Base.metadata.drop_all(bind=bind, tables=_baseline_tables())
