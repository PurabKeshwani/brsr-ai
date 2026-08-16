"""
Database session management.

Defaults to a local SQLite file (zero-config for development). Swapping to
Postgres for production later is a one-line change (set BRSR_DB_URL) — the
SQLAlchemy models in models.py are written to be database-agnostic (JSON
column type works on both SQLite 3.9+ and Postgres).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "brsr.db"
DB_URL = os.environ.get("BRSR_DB_URL", f"sqlite:///{DEFAULT_DB_PATH}")

DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_engine = create_engine(DB_URL, echo=False)
_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)


def init_db() -> None:
    """Creates all tables if they don't exist. Safe to call repeatedly."""
    Base.metadata.create_all(_engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Provides a transactional session — commits on success, rolls back
    and re-raises on any exception. Usage:

        with get_session() as session:
            session.add(some_object)
    """
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()