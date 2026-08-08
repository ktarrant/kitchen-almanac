"""Add cultivar intent to quick-import wishlists.

Revision ID: 20260808_0008
Revises: 20260808_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0008"
down_revision: str | None = "20260808_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wishlists") as batch_op:
        batch_op.add_column(
            sa.Column("cultivar_dataset_version_id", sa.String(length=80), nullable=True)
        )
        batch_op.create_index(
            "ix_wishlists_cultivar_dataset_version_id",
            ["cultivar_dataset_version_id"],
        )
        batch_op.create_foreign_key(
            "fk_wishlists_cultivar_dataset_version_id",
            "cultivar_dataset_versions",
            ["cultivar_dataset_version_id"],
            ["id"],
        )
    with op.batch_alter_table("wishlist_entries") as batch_op:
        batch_op.add_column(
            sa.Column("intent_kind", sa.String(length=30), nullable=False, server_default="crop")
        )
        batch_op.add_column(sa.Column("cultivar_intent_text", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("crop_type_intent", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("resolved_cultivar_id", sa.String(length=180), nullable=True))
        batch_op.create_index(
            "ix_wishlist_entries_resolved_cultivar_id",
            ["resolved_cultivar_id"],
        )
        batch_op.create_foreign_key(
            "fk_wishlist_entries_resolved_cultivar_id",
            "cultivars",
            ["resolved_cultivar_id"],
            ["id"],
        )
    op.create_table(
        "wishlist_cultivar_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("wishlist_entry_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("cultivar_id", sa.String(length=180), nullable=False, index=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("matched_alias", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["wishlist_entry_id"], ["wishlist_entries.id"]),
        sa.ForeignKeyConstraint(["cultivar_id"], ["cultivars.id"]),
        sa.UniqueConstraint("wishlist_entry_id", "cultivar_id"),
        sa.UniqueConstraint("wishlist_entry_id", "rank"),
    )


def downgrade() -> None:
    op.drop_table("wishlist_cultivar_candidates")
    with op.batch_alter_table("wishlist_entries") as batch_op:
        batch_op.drop_constraint(
            "fk_wishlist_entries_resolved_cultivar_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_wishlist_entries_resolved_cultivar_id")
        batch_op.drop_column("resolved_cultivar_id")
        batch_op.drop_column("crop_type_intent")
        batch_op.drop_column("cultivar_intent_text")
        batch_op.drop_column("intent_kind")
    with op.batch_alter_table("wishlists") as batch_op:
        batch_op.drop_constraint(
            "fk_wishlists_cultivar_dataset_version_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_wishlists_cultivar_dataset_version_id")
        batch_op.drop_column("cultivar_dataset_version_id")
