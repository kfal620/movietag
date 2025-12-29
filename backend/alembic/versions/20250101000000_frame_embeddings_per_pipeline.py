"""Add frame_embeddings table for multi-pipeline support.

Revision ID: 20250101000000_frame_embeddings_per_pipeline
Revises: 20260701000000_actor_tracking_attributes
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250101000000_frame_embeddings_per_pipeline"
down_revision = "20260701000000_actor_tracking_attributes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add frame_embeddings table for storing embeddings per pipeline."""
    op.create_table(
        "frame_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("frame_id", sa.Integer(), nullable=False),
        sa.Column("pipeline_id", sa.String(length=100), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["frame_id"],
            ["frames.id"],
            name=op.f("fk_frame_embeddings_frame_id_frames"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_frame_embeddings")),
        sa.UniqueConstraint(
            "frame_id",
            "pipeline_id",
            name="uq_frame_embedding_pipeline",
        ),
    )
    op.create_index(
        op.f("ix_frame_embeddings_frame_id"),
        "frame_embeddings",
        ["frame_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_frame_embeddings_pipeline_id"),
        "frame_embeddings",
        ["pipeline_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove frame_embeddings table."""
    op.drop_index(op.f("ix_frame_embeddings_pipeline_id"), table_name="frame_embeddings")
    op.drop_index(op.f("ix_frame_embeddings_frame_id"), table_name="frame_embeddings")
    op.drop_table("frame_embeddings")
