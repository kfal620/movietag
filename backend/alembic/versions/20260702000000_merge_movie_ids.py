"""Merge predicted_movie_id into movie_id."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260702000000_merge_movie_ids"
down_revision = "20260701000000_actor_tracking_attributes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate data: Move predicted_movie_id to movie_id if movie_id is null
    op.execute(
        "UPDATE frames SET movie_id = predicted_movie_id WHERE movie_id IS NULL AND predicted_movie_id IS NOT NULL"
    )
    
    with op.batch_alter_table("frames") as batch_op:
        # We attempt to drop the index and column.
        # If constraint names are required, this might fail, but batch operations
        # usually handle this for SQLite. For Postgres, we might need explicit drop.
        batch_op.drop_index("ix_frames_predicted_movie_id")
        batch_op.drop_column("predicted_movie_id")


def downgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.add_column(sa.Column("predicted_movie_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_frames_predicted_movie_id_movies", "movies", ["predicted_movie_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_frames_predicted_movie_id", ["predicted_movie_id"])
