"""SQLAlchemy engine, session factory and declarative base.

SQLite is used for local execution. To switch to PostgreSQL later, set
DATABASE_URL to a postgres connection string - the models are database
agnostic and schema-creation is handled by SQLAlchemy metadata.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all():
    from . import models  # noqa: F401  (imports register all tables)

    Base.metadata.create_all(bind=engine)