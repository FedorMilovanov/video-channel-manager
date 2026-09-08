"""Add durable Instagram publication ledger.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instagram_publications",
        sa.Column("publication_key", sa.String(length=200), nullable=False),
        sa.Column("account_id", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("provider_container_id", sa.String(length=255), nullable=True),
        sa.Column("provider_media_id", sa.String(length=255), nullable=True),
        sa.Column("provider_status", sa.String(length=100), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=200), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("publish_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("publication_key"),
    )


def downgrade() -> None:
    op.drop_table("instagram_publications")
