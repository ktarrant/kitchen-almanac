"""Add commercial listing availability metadata.

Revision ID: 20260809_0011
Revises: 20260808_0010
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_0011"
down_revision: str | None = "20260808_0010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("commercial_seed_listings") as batch_op:
        batch_op.add_column(sa.Column("availability_status", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("identity_match_method", sa.String(length=30), nullable=True))
    op.execute(
        "UPDATE commercial_seed_listings SET availability_status = 'unknown', "
        "observed_at = CURRENT_TIMESTAMP, identity_match_method = 'exact_name'"
    )
    with op.batch_alter_table("commercial_seed_listings") as batch_op:
        batch_op.alter_column("availability_status", nullable=False)
        batch_op.alter_column("observed_at", nullable=False)
        batch_op.alter_column("identity_match_method", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("commercial_seed_listings") as batch_op:
        batch_op.drop_column("identity_match_method")
        batch_op.drop_column("observed_at")
        batch_op.drop_column("availability_status")
