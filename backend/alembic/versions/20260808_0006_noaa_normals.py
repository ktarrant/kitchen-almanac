"""Add NOAA climate station normals.

Revision ID: 20260808_0006
Revises: 20260808_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0006"
down_revision: str | None = "20260808_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "climate_station_normals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("climate_dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("station_id", sa.String(length=20), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("annual_mean_f", sa.Float(), nullable=False),
        sa.Column("annual_minimum_f", sa.Float(), nullable=False),
        sa.Column("annual_maximum_f", sa.Float(), nullable=False),
        sa.Column("annual_precipitation_in", sa.Float(), nullable=False),
        sa.Column("growing_degree_days_base_50_f", sa.Float(), nullable=False),
        sa.Column("last_spring_frost_50", sa.String(length=5), nullable=False),
        sa.Column("first_fall_frost_50", sa.String(length=5), nullable=False),
        sa.Column("growing_season_days_50", sa.Integer(), nullable=False),
        sa.Column("completeness_class", sa.String(length=1), nullable=False),
        sa.Column("minimum_years", sa.Integer(), nullable=False),
        sa.Column("source_locator", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["climate_dataset_version_id"], ["climate_dataset_versions.id"]),
        sa.UniqueConstraint("climate_dataset_version_id", "station_id"),
    )


def downgrade() -> None:
    op.drop_table("climate_station_normals")
