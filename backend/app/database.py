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
    _add_missing_columns()


#: Columns added after the first release. ``create_all()`` never alters an
#: existing table, so on SQLite (and any other engine that supports ADD COLUMN)
#: we add them explicitly and idempotently. This keeps existing local databases
#: usable without a manual migration step.
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("experiment_runs", "next_action_category_accuracy", "FLOAT DEFAULT 0"),
    ("experiment_runs", "next_action_category_scored_cases", "INTEGER DEFAULT 0"),
    ("experiment_runs", "next_action_text_match_rate", "FLOAT DEFAULT 0"),
    ("evaluation_results", "next_action_category", "VARCHAR(32) DEFAULT ''"),
    ("evaluation_results", "expected_action_category", "VARCHAR(32) DEFAULT ''"),
    ("evaluation_results", "next_action_category_scored", "BOOLEAN DEFAULT 0"),
    ("evaluation_results", "next_action_text_match", "BOOLEAN DEFAULT 0"),
)


def _add_missing_columns() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, ddl in _ADDITIVE_COLUMNS:
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            if column in present:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))