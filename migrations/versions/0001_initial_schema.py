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


def upgrade() -> None:
    # The authoritative table definitions live in persistence/models.py.
    # This explicit migration is intentionally generated as a single baseline.
    from video_channel_manager.persistence.models import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from video_channel_manager.persistence.models import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
