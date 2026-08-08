"""Add versioned postal-area coordinate data.

Revision ID: 20260808_0004
Revises: 20260808_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0004"
down_revision: str | None = "20260808_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "location_dataset_versions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("schema_version", sa.String(length=30), nullable=False),
        sa.Column("parser_version", sa.String(length=30), nullable=False),
        sa.Column("source_document_id", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
    )
    op.create_table(
        "postal_code_locations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("postal_code", sa.String(length=5), nullable=False, index=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("coordinate_method", sa.String(length=50), nullable=False),
        sa.Column("source_locator", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["location_dataset_version_id"], ["location_dataset_versions.id"]),
        sa.UniqueConstraint("location_dataset_version_id", "postal_code"),
    )
    with op.batch_alter_table("garden_profiles") as batch_op:
        batch_op.add_column(
            sa.Column("location_dataset_version_id", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(sa.Column("coordinate_method", sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column("coordinate_source_locator", sa.String(length=255), nullable=True)
        )
        batch_op.create_index(
            "ix_garden_profiles_location_dataset_version_id",
            ["location_dataset_version_id"],
        )
        batch_op.create_foreign_key(
            "fk_garden_profiles_location_dataset_version_id",
            "location_dataset_versions",
            ["location_dataset_version_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("garden_profiles") as batch_op:
        batch_op.drop_constraint(
            "fk_garden_profiles_location_dataset_version_id", type_="foreignkey"
        )
        batch_op.drop_index("ix_garden_profiles_location_dataset_version_id")
        batch_op.drop_column("coordinate_source_locator")
        batch_op.drop_column("coordinate_method")
        batch_op.drop_column("location_dataset_version_id")
    op.drop_table("postal_code_locations")
    op.drop_table("location_dataset_versions")
