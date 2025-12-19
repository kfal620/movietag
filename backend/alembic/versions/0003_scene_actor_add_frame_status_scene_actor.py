"""Add frame ingest status, storage fields, scene attributes, and actor detections."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_scene_actor"
down_revision = "0002_tmdb_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.add_column(sa.Column("storage_uri", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("signed_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=50), server_default="pending", nullable=False))
        batch_op.add_column(sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("embedding_model", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("ingest_task_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("tagging_task_id", sa.String(length=255), nullable=True))
        batch_op.create_index(op.f("ix_frames_ingest_task_id"), ["ingest_task_id"], unique=False)
        batch_op.create_index(op.f("ix_frames_tagging_task_id"), ["tagging_task_id"], unique=False)

    op.create_table(
        "scene_attributes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("frame_id", sa.Integer(), nullable=False),
        sa.Column("attribute", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["frame_id"], ["frames.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scene_attributes_id"), "scene_attributes", ["id"], unique=False)
    op.create_index(op.f("ix_scene_attributes_frame_id"), "scene_attributes", ["frame_id"], unique=False)

    op.create_table(
        "actor_detections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("frame_id", sa.Integer(), nullable=False),
        sa.Column("cast_member_id", sa.Integer(), nullable=True),
        sa.Column("face_index", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("bbox", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cast_member_id"], ["cast_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["frame_id"], ["frames.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("frame_id", "cast_member_id", "face_index", name="uq_actor_detection_frame_cast"),
    )
    op.create_index(op.f("ix_actor_detections_id"), "actor_detections", ["id"], unique=False)
    op.create_index(op.f("ix_actor_detections_frame_id"), "actor_detections", ["frame_id"], unique=False)
    op.create_index(op.f("ix_actor_detections_cast_member_id"), "actor_detections", ["cast_member_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_actor_detections_cast_member_id"), table_name="actor_detections")
    op.drop_index(op.f("ix_actor_detections_frame_id"), table_name="actor_detections")
    op.drop_index(op.f("ix_actor_detections_id"), table_name="actor_detections")
    op.drop_table("actor_detections")

    op.drop_index(op.f("ix_scene_attributes_frame_id"), table_name="scene_attributes")
    op.drop_index(op.f("ix_scene_attributes_id"), table_name="scene_attributes")
    op.drop_table("scene_attributes")

    with op.batch_alter_table("frames") as batch_op:
        batch_op.drop_index(op.f("ix_frames_tagging_task_id"))
        batch_op.drop_index(op.f("ix_frames_ingest_task_id"))
        batch_op.drop_column("tagging_task_id")
        batch_op.drop_column("ingest_task_id")
        batch_op.drop_column("embedding_model")
        batch_op.drop_column("captured_at")
        batch_op.drop_column("ingested_at")
        batch_op.drop_column("status")
        batch_op.drop_column("signed_url")
        batch_op.drop_column("storage_uri")
