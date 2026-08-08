"""Add versioned climate datasets and location evidence.

Revision ID: 20260808_0005
Revises: 20260808_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0005"
down_revision: str | None = "20260808_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "climate_dataset_versions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("dataset_kind", sa.String(length=50), nullable=False, index=True),
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
        "location_evidence_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("garden_profile_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("climate_dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("normalized_value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("source_document_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=False),
        sa.Column("extraction_method", sa.String(length=80), nullable=False),
        sa.Column("extractor_version", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(["garden_profile_id"], ["garden_profiles.id"]),
        sa.ForeignKeyConstraint(["climate_dataset_version_id"], ["climate_dataset_versions.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.UniqueConstraint("garden_profile_id", "climate_dataset_version_id", "field_name"),
    )


def downgrade() -> None:
    op.drop_table("location_evidence_claims")
    op.drop_table("climate_dataset_versions")
