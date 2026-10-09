"""The database: one engine per process, one session per request.

Postgres in production. SQLite works for tests and a no-install dev mode; the
code avoids anything only one of them has, and the queue (queue.py) is correct
on both because a claim is a compare-and-swap, not a read-then-write.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    # stored naive, always UTC: SQLite has no time zones and mixing aware and
    # naive datetimes is a class of bug not worth having
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _):          # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = make_engine(url)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @property
    def is_postgres(self) -> bool:
        return self.engine.dialect.name == "postgresql"

    def create_all(self) -> None:
        from . import models  # noqa: F401  registers the tables
        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        """For FastAPI's dependency injection."""
        s = self.sessions()
        try:
            yield s
        finally:
            s.close()

    @contextmanager
    def scope(self) -> Iterator[Session]:
        """For code that opens its own session, in a worker thread say."""
        s = self.sessions()
        try:
            yield s
        finally:
            s.close()
