"""Add face embeddings for cast members and actor detections."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260420000000_face_recognition_embeddings"
down_revision = "20260315000000_frame_metadata_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cast_members") as batch_op:
        batch_op.add_column(sa.Column("face_embedding", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("face_embedding_model", sa.String(length=100), nullable=True))

    with op.batch_alter_table("actor_detections") as batch_op:
        batch_op.add_column(sa.Column("embedding", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("actor_detections") as batch_op:
        batch_op.drop_column("embedding")

    with op.batch_alter_table("cast_members") as batch_op:
        batch_op.drop_column("face_embedding_model")
        batch_op.drop_column("face_embedding")
