"""Add embedding metadata version and failure reason fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251219214916_frame_failure_and_embedding_meta"
down_revision = "0003_scene_actor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.add_column(sa.Column("embedding_model_version", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.drop_column("failure_reason")
        batch_op.drop_column("embedding_model_version")
