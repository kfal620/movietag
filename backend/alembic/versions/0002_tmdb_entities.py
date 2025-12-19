"""Add TMDb identifiers, cast, and artwork tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_tmdb_entities"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("tmdb_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_movies_tmdb_id", "movies", ["tmdb_id"])
    op.create_index(op.f("ix_movies_tmdb_id"), "movies", ["tmdb_id"], unique=False)

    op.create_table(
        "cast_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("profile_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tmdb_id", name="uq_cast_members_tmdb_id"),
    )
    op.create_index(op.f("ix_cast_members_id"), "cast_members", ["id"], unique=False)
    op.create_index(op.f("ix_cast_members_tmdb_id"), "cast_members", ["tmdb_id"], unique=False)

    op.create_table(
        "movie_cast",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("cast_member_id", sa.Integer(), nullable=False),
        sa.Column("character", sa.String(length=255), nullable=True),
        sa.Column("cast_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cast_member_id"], ["cast_members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "cast_member_id", name="uq_movie_cast_pair"),
    )
    op.create_index(op.f("ix_movie_cast_cast_member_id"), "movie_cast", ["cast_member_id"], unique=False)
    op.create_index(op.f("ix_movie_cast_id"), "movie_cast", ["id"], unique=False)
    op.create_index(op.f("ix_movie_cast_movie_id"), "movie_cast", ["movie_id"], unique=False)

    op.create_table(
        "artwork",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("aspect_ratio", sa.Float(), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "file_path", "kind", name="uq_artwork_per_movie"),
    )
    op.create_index(op.f("ix_artwork_id"), "artwork", ["id"], unique=False)
    op.create_index(op.f("ix_artwork_movie_id"), "artwork", ["movie_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_artwork_movie_id"), table_name="artwork")
    op.drop_index(op.f("ix_artwork_id"), table_name="artwork")
    op.drop_table("artwork")

    op.drop_index(op.f("ix_movie_cast_movie_id"), table_name="movie_cast")
    op.drop_index(op.f("ix_movie_cast_id"), table_name="movie_cast")
    op.drop_index(op.f("ix_movie_cast_cast_member_id"), table_name="movie_cast")
    op.drop_table("movie_cast")

    op.drop_index(op.f("ix_cast_members_tmdb_id"), table_name="cast_members")
    op.drop_index(op.f("ix_cast_members_id"), table_name="cast_members")
    op.drop_table("cast_members")

    op.drop_index(op.f("ix_movies_tmdb_id"), table_name="movies")
    op.drop_constraint("uq_movies_tmdb_id", "movies", type_="unique")
    op.drop_column("movies", "tmdb_id")
