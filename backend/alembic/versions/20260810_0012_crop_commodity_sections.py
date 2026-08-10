"""Add Rutgers commodity section metadata to crops.

Revision ID: 20260810_0012
Revises: 20260809_0011
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_0012"
down_revision: str | None = "20260809_0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("crops") as batch_op:
        batch_op.add_column(
            sa.Column("commodity_section_key", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("commodity_section_title", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("commodity_section_position", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("crops") as batch_op:
        batch_op.drop_column("commodity_section_position")
        batch_op.drop_column("commodity_section_title")
        batch_op.drop_column("commodity_section_key")
