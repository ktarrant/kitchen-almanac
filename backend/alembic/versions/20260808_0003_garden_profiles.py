"""Add garden context and link wishlists.

Revision ID: 20260808_0003
Revises: 20260808_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0003"
down_revision: str | None = "20260808_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "garden_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("location_input", sa.String(length=255), nullable=False),
        sa.Column("postal_code", sa.String(length=10), nullable=True, index=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("location_status", sa.String(length=40), nullable=False),
        sa.Column("target_year", sa.Integer(), nullable=False),
        sa.Column("experience_level", sa.String(length=20), nullable=False),
        sa.Column("growing_methods", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("wishlists") as batch_op:
        batch_op.add_column(sa.Column("garden_profile_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_wishlists_garden_profile_id", ["garden_profile_id"])
        batch_op.create_foreign_key(
            "fk_wishlists_garden_profile_id",
            "garden_profiles",
            ["garden_profile_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("wishlists") as batch_op:
        batch_op.drop_constraint("fk_wishlists_garden_profile_id", type_="foreignkey")
        batch_op.drop_index("ix_wishlists_garden_profile_id")
        batch_op.drop_column("garden_profile_id")
    op.drop_table("garden_profiles")
