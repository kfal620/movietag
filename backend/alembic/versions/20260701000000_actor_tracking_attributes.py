"""Add tracking and pose attributes to actor detections."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260701000000_actor_tracking_attributes"
down_revision = "20260420000000_face_recognition_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("actor_detections") as batch_op:
        batch_op.add_column(sa.Column("cluster_label", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("track_status", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("emotion", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("pose_yaw", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pose_pitch", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("pose_roll", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("actor_detections") as batch_op:
        batch_op.drop_column("pose_roll")
        batch_op.drop_column("pose_pitch")
        batch_op.drop_column("pose_yaw")
        batch_op.drop_column("emotion")
        batch_op.drop_column("track_status")
        batch_op.drop_column("cluster_label")
