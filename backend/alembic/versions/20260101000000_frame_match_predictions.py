"""Allow frameless movie ingestion and add match prediction fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260101000000_frame_match_predictions"
down_revision = "20251219214916_frame_failure_and_embedding_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.alter_column("movie_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("predicted_movie_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("match_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("predicted_timestamp", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("predicted_shot_id", sa.String(length=100), nullable=True))
        batch_op.create_foreign_key(
            "fk_frames_predicted_movie_id_movies",
            "movies",
            ["predicted_movie_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_frames_predicted_movie_id", ["predicted_movie_id"])


def downgrade() -> None:
    with op.batch_alter_table("frames") as batch_op:
        batch_op.drop_index("ix_frames_predicted_movie_id")
        batch_op.drop_constraint(
            "fk_frames_predicted_movie_id_movies", type_="foreignkey"
        )
        batch_op.drop_column("predicted_shot_id")
        batch_op.drop_column("predicted_timestamp")
        batch_op.drop_column("match_confidence")
        batch_op.drop_column("predicted_movie_id")
        batch_op.alter_column("movie_id", existing_type=sa.Integer(), nullable=False)
