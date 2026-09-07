"""Shared pytest fixtures.

Each test gets a freshly seeded, disposable SQLite database so test order
never matters. The temporary DATABASE_URL is set before any backend module is
imported (the engine binds to it at import time).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name.replace(os.sep, '/')}"

from backend.app.database import SessionLocal, engine
from backend.app.main import app
from scripts.seed_database import _seed_ref_tables  # noqa: E402  (reuse ref-table seeding)

_seeded = False


def _fresh_db() -> None:
    """Drop and recreate tables, then seed the reference tables + dataset."""
    from backend.app import models  # noqa: F401
    from backend.app.database import Base, create_all
    from scripts import seed_database

    Base.metadata.drop_all(bind=engine)
    create_all()
    db = SessionLocal()
    try:
        _seed_ref_tables(db)
        details = seed_database.seed()
        if details.get("tickets_imported", 0) == 0:
            raise RuntimeError(f"test DB seeding failed: {details}")
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def _seeded_database():
    global _seeded
    if not _seeded:
        _fresh_db()
        _seeded = True
    yield


@pytest.fixture
def db():
    """Per-test session. Table state is reset between tests where requested."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fresh_db():
    """A pristine, freshly reseeded database for mutation-heavy tests."""
    _fresh_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c