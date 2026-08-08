"""Create provenance and seed catalog tables.

Revision ID: 20260808_0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "dataset_versions",
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
        "crops",
        sa.Column("id", sa.String(length=180), primary_key=True),
        sa.Column("dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("planning_category", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.UniqueConstraint("dataset_version_id", "slug"),
    )
    op.create_table(
        "catalog_corrections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("correction_type", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
    )
    op.create_table(
        "crop_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("crop_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["crop_id"], ["crops.id"]),
        sa.UniqueConstraint("crop_id", "alias"),
    )
    op.create_table(
        "crop_season_appearances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("crop_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("season", sa.String(length=40), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_line", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["crop_id"], ["crops.id"]),
        sa.UniqueConstraint("crop_id", "season", "source_name"),
    )
    op.create_table(
        "evidence_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("normalized_value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column("source_document_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=False),
        sa.Column("extraction_method", sa.String(length=80), nullable=False),
        sa.Column("extractor_version", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
    )


def downgrade() -> None:
    op.drop_table("evidence_claims")
    op.drop_table("crop_season_appearances")
    op.drop_table("crop_aliases")
    op.drop_table("catalog_corrections")
    op.drop_table("crops")
    op.drop_table("dataset_versions")
    op.drop_table("source_documents")
