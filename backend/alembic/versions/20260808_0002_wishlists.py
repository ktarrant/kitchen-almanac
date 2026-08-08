"""Add persisted wishlist resolution.

Revision ID: 20260808_0002
Revises: 20260808_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0002"
down_revision: str | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wishlists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_version_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"]),
    )
    op.create_table(
        "wishlist_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("wishlist_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.String(length=120), nullable=False),
        sa.Column("normalized_text", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("resolution_method", sa.String(length=30), nullable=True),
        sa.Column("resolved_crop_id", sa.String(length=180), nullable=True, index=True),
        sa.ForeignKeyConstraint(["wishlist_id"], ["wishlists.id"]),
        sa.ForeignKeyConstraint(["resolved_crop_id"], ["crops.id"]),
        sa.UniqueConstraint("wishlist_id", "position"),
    )
    op.create_table(
        "wishlist_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("wishlist_entry_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("crop_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("matched_alias", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["wishlist_entry_id"], ["wishlist_entries.id"]),
        sa.ForeignKeyConstraint(["crop_id"], ["crops.id"]),
        sa.UniqueConstraint("wishlist_entry_id", "crop_id"),
        sa.UniqueConstraint("wishlist_entry_id", "rank"),
    )


def downgrade() -> None:
    op.drop_table("wishlist_candidates")
    op.drop_table("wishlist_entries")
    op.drop_table("wishlists")
