"""Add gardener browse category metadata to crops.

Revision ID: 20260810_0013
Revises: 20260810_0012
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0013"
down_revision: str | None = "20260810_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("crops", sa.Column("browse_category_key", sa.String(100), nullable=True))
    op.add_column("crops", sa.Column("browse_category_title", sa.String(255), nullable=True))
    op.add_column("crops", sa.Column("browse_category_position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("crops", "browse_category_position")
    op.drop_column("crops", "browse_category_title")
    op.drop_column("crops", "browse_category_key")
