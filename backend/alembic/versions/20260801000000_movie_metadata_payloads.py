"""Add raw metadata storage for movies."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260801000000_movie_metadata_payloads"
down_revision = "20260702000000_merge_movie_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("movies") as batch_op:
        batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("movies") as batch_op:
        batch_op.drop_column("metadata_json")
