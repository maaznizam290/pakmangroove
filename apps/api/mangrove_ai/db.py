"""Thin SQLAlchemy engine/session wrapper. Raw SQL is used freely elsewhere
in this package (via `text()`) since most queries are PostGIS-specific —
this module just owns the connection lifecycle."""

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from mangrove_ai.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
