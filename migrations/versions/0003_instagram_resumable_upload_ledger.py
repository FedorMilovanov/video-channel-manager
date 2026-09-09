"""Add durable Instagram resumable-upload child ledger.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instagram_resumable_uploads",
        sa.Column("publication_key", sa.String(length=200), nullable=False),
        sa.Column("provider_container_id", sa.String(length=255), nullable=False),
        sa.Column("upload_uri", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=200), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("upload_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["publication_key"],
            ["instagram_publications.publication_key"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("publication_key"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    row_count = bind.execute(sa.text("SELECT COUNT(*) FROM instagram_resumable_uploads")).scalar_one()
    if row_count:
        raise RuntimeError(
            "Refusing to drop non-empty Instagram resumable-upload ledger; durable provider-write state must be preserved"
        )
    op.drop_table("instagram_resumable_uploads")
