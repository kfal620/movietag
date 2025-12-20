"""Add enriched metadata fields to frames."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260315000000_frame_metadata_enrichment"
down_revision = "20260101000000_frame_match_predictions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.add_column(sa.Column("shot_timestamp", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("scene_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("metadata_source", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.drop_column("metadata_source")
        batch_op.drop_column("scene_summary")
        batch_op.drop_column("shot_timestamp")
