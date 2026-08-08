"""Add garden suitability context.

Revision ID: 20260808_0010
Revises: 20260808_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0010"
down_revision: str | None = "20260808_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("garden_profiles") as batch_op:
        batch_op.add_column(sa.Column("support_available", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("max_plant_spread_inches", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("max_container_volume_gallons", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "intended_uses",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "disease_concerns",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("garden_profiles") as batch_op:
        batch_op.drop_column("disease_concerns")
        batch_op.drop_column("intended_uses")
        batch_op.drop_column("max_container_volume_gallons")
        batch_op.drop_column("max_plant_spread_inches")
        batch_op.drop_column("support_available")
