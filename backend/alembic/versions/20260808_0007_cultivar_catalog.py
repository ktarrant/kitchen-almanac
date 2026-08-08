"""Add versioned cultivar identities and evidence.

Revision ID: 20260808_0007
Revises: 20260808_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0007"
down_revision: str | None = "20260808_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cultivar_dataset_versions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("schema_version", sa.String(length=30), nullable=False),
        sa.Column("parser_version", sa.String(length=30), nullable=False),
        sa.Column("crop_dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("source_document_id", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(["crop_dataset_version_id"], ["dataset_versions.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
    )
    op.create_table(
        "cultivars",
        sa.Column("id", sa.String(length=180), primary_key=True),
        sa.Column("cultivar_dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("crop_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("crop_type", sa.String(length=80), nullable=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["cultivar_dataset_version_id"], ["cultivar_dataset_versions.id"]),
        sa.ForeignKeyConstraint(["crop_id"], ["crops.id"]),
        sa.UniqueConstraint("cultivar_dataset_version_id", "slug"),
    )
    op.create_table(
        "cultivar_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cultivar_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["cultivar_id"], ["cultivars.id"]),
        sa.UniqueConstraint("cultivar_id", "alias"),
    )
    op.create_table(
        "cultivar_source_identifiers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cultivar_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("source_document_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("source_identifier", sa.String(length=255), nullable=False),
        sa.Column("name_in_source", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["cultivar_id"], ["cultivars.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.UniqueConstraint("cultivar_id", "source_document_id", "source_identifier"),
    )
    op.create_table(
        "cultivar_evidence_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cultivar_dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("subject_kind", sa.String(length=30), nullable=False),
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
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["cultivar_dataset_version_id"], ["cultivar_dataset_versions.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.UniqueConstraint(
            "cultivar_dataset_version_id",
            "subject_kind",
            "subject_id",
            "field_name",
            "source_document_id",
        ),
    )
    op.create_table(
        "commercial_seed_listings",
        sa.Column("id", sa.String(length=180), primary_key=True),
        sa.Column("cultivar_dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("cultivar_id", sa.String(length=180), nullable=True, index=True),
        sa.Column("source_document_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("vendor", sa.String(length=255), nullable=False),
        sa.Column("listing_name", sa.String(length=255), nullable=False),
        sa.Column("source_identifier", sa.String(length=255), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["cultivar_dataset_version_id"], ["cultivar_dataset_versions.id"]),
        sa.ForeignKeyConstraint(["cultivar_id"], ["cultivars.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.UniqueConstraint("cultivar_dataset_version_id", "vendor", "source_identifier"),
    )


def downgrade() -> None:
    op.drop_table("commercial_seed_listings")
    op.drop_table("cultivar_evidence_claims")
    op.drop_table("cultivar_source_identifiers")
    op.drop_table("cultivar_aliases")
    op.drop_table("cultivars")
    op.drop_table("cultivar_dataset_versions")
