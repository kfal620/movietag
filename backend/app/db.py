"""Database session and engine setup."""

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .core.settings import get_settings


def _create_engine():
    settings = get_settings()
    return create_engine(settings.database_url)


engine = _create_engine()
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
