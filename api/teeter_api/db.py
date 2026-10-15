"""The database: one engine per process, one session per request.

Postgres in production. SQLite works for tests and a no-install dev mode; the
code avoids anything only one of them has, and the queue (queue.py) is correct
on both because a claim is a compare-and-swap, not a read-then-write.

The schema is owned by Alembic (migrations/). ``migrate()`` brings a database
to the latest revision and is what every deployment runs; ``create_all()``
builds the same tables directly and is kept for tests, where it is faster,
and tests/test_migrations.py fails if the two ever describe different schemas.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    # stored naive, always UTC: SQLite has no time zones and mixing aware and
    # naive datetimes is a class of bug not worth having
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_engine(url: str, *, pool_size: int = 10) -> Engine:
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
    # prepare_threshold=None: no server-side prepared statements, which a
    # connection pooler in transaction mode (Neon's, PgBouncer) can hand to the
    # wrong backend. pool_recycle: poolers and serverless hosts drop idle
    # connections; recycle them before they go stale.
    return create_engine(url, pool_pre_ping=True, pool_size=pool_size, max_overflow=pool_size * 2,
                         pool_recycle=300, connect_args={"prepare_threshold": None})


class Database:
    def __init__(self, url: str, *, pool_size: int = 10, direct_url: str | None = None) -> None:
        self.url = url
        self.direct_url = direct_url or url
        self.engine = make_engine(url, pool_size=pool_size)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @property
    def is_postgres(self) -> bool:
        return self.engine.dialect.name == "postgresql"

    def create_all(self) -> None:
        from . import models  # noqa: F401  registers the tables
        Base.metadata.create_all(self.engine)

    def migrate(self) -> str:
        """Upgrade to the latest revision; returns it. On Postgres the upgrade
        holds an advisory lock, so two deployments starting together do not
        both run it."""
        from alembic import command
        from alembic.config import Config

        cfg = Config()
        cfg.set_main_option("script_location", str(MIGRATIONS))
        if self.revision() is None:
            from sqlalchemy import inspect
            if inspect(self.engine).has_table("workspaces"):
                raise RuntimeError(
                    "this database has tables but no migration history: it was made before the schema "
                    "was migrated. For a development database, delete it (.teeter/dev.sqlite) and start again")
        url = self.direct_url
        engine = self.engine if url == self.url else make_engine(url, pool_size=1)
        try:
            with engine.begin() as conn:
                if conn.dialect.name == "postgresql":
                    conn.exec_driver_sql("SELECT pg_advisory_xact_lock(7457334)")   # 'teet'
                cfg.attributes["connection"] = conn
                command.upgrade(cfg, "head")
        finally:
            if engine is not self.engine:
                engine.dispose()
        return self.revision() or ""

    def revision(self) -> str | None:
        """The revision the database is at, or None if it has never been migrated."""
        from alembic.runtime.migration import MigrationContext
        with self.engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()

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
