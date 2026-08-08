"""Add evidence source scope.

Revision ID: 20260808_0009
Revises: 20260808_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0009"
down_revision: str | None = "20260808_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("source_documents") as batch_op:
        batch_op.add_column(sa.Column("source_scope", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("source_documents") as batch_op:
        batch_op.drop_column("source_scope")
