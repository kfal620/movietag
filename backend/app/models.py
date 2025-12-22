"""SQLAlchemy models for core domain objects."""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (UniqueConstraint("tmdb_id", name="uq_movies_tmdb_id"),)

    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    release_year = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    frames = relationship(
        "Frame",
        back_populates="movie",
        cascade="all, delete",
        foreign_keys="Frame.movie_id",
    )
    cast_members = relationship(
        "MovieCast", back_populates="movie", cascade="all, delete"
    )
    artwork = relationship("Artwork", back_populates="movie", cascade="all, delete")


class CastMember(Base):
    __tablename__ = "cast_members"
    __table_args__ = (UniqueConstraint("tmdb_id", name="uq_cast_members_tmdb_id"),)

    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    profile_path = Column(String(512), nullable=True)
    face_embedding = Column(Text, nullable=True)
    face_embedding_model = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    movies = relationship("MovieCast", back_populates="cast_member", cascade="all, delete")


class MovieCast(Base):
    __tablename__ = "movie_cast"
    __table_args__ = (UniqueConstraint("movie_id", "cast_member_id", name="uq_movie_cast_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cast_member_id = Column(
        Integer,
        ForeignKey("cast_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    character = Column(String(255), nullable=True)
    cast_order = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    movie = relationship("Movie", back_populates="cast_members")
    cast_member = relationship("CastMember", back_populates="movies")


class Artwork(Base):
    __tablename__ = "artwork"
    __table_args__ = (
        UniqueConstraint("movie_id", "file_path", "kind", name="uq_artwork_per_movie"),
    )

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(
        Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = Column(String(50), nullable=False)
    file_path = Column(String(512), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    aspect_ratio = Column(Float, nullable=True)
    language = Column(String(10), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    movie = relationship("Movie", back_populates="artwork")


class Frame(Base):
    __tablename__ = "frames"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(
        Integer,
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    match_confidence = Column(Float, nullable=True)
    predicted_timestamp = Column(String(100), nullable=True)
    predicted_shot_id = Column(String(100), nullable=True)
    shot_timestamp = Column(String(100), nullable=True)
    scene_summary = Column(Text, nullable=True)
    metadata_source = Column(String(100), nullable=True)
    file_path = Column(String(512), nullable=False)
    storage_uri = Column(String(512), nullable=True)
    signed_url = Column(String(1024), nullable=True)
    status = Column(String(50), nullable=False, server_default="pending")
    ingested_at = Column(DateTime(timezone=True), nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=True)
    embedding = Column(Text, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_model_version = Column(String(100), nullable=True)
    failure_reason = Column(Text, nullable=True)
    ingest_task_id = Column(String(255), nullable=True, index=True)
    tagging_task_id = Column(String(255), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    movie = relationship(
        "Movie", back_populates="frames", foreign_keys=[movie_id]
    )
    tags = relationship("FrameTag", back_populates="frame", cascade="all, delete")
    scene_attributes = relationship(
        "SceneAttribute", back_populates="frame", cascade="all, delete"
    )
    actor_detections = relationship(
        "ActorDetection", back_populates="frame", cascade="all, delete"
    )



class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name", name="uq_tags_name"),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    frames = relationship("FrameTag", back_populates="tag", cascade="all, delete")


class FrameTag(Base):
    __tablename__ = "frame_tags"
    __table_args__ = (UniqueConstraint("frame_id", "tag_id", name="uq_frame_tag_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    frame_id = Column(
        Integer, ForeignKey("frames.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    frame = relationship("Frame", back_populates="tags")
    tag = relationship("Tag", back_populates="frames")


class SceneAttribute(Base):
    __tablename__ = "scene_attributes"

    id = Column(Integer, primary_key=True, index=True)
    frame_id = Column(
        Integer, ForeignKey("frames.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attribute = Column(String(100), nullable=False)
    value = Column(String(255), nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    frame = relationship("Frame", back_populates="scene_attributes")


class ActorDetection(Base):
    __tablename__ = "actor_detections"
    __table_args__ = (
        UniqueConstraint(
            "frame_id",
            "cast_member_id",
            "face_index",
            name="uq_actor_detection_frame_cast",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    frame_id = Column(
        Integer, ForeignKey("frames.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cast_member_id = Column(
        Integer,
        ForeignKey("cast_members.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    face_index = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    bbox = Column(String(255), nullable=True)
    embedding = Column(Text, nullable=True)
    cluster_label = Column(String(100), nullable=True)
    track_status = Column(String(50), nullable=True)
    emotion = Column(String(50), nullable=True)
    pose_yaw = Column(Float, nullable=True)
    pose_pitch = Column(Float, nullable=True)
    pose_roll = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    frame = relationship("Frame", back_populates="actor_detections")
    cast_member = relationship("CastMember")
