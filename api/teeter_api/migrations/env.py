"""Alembic's entry point. Migrations run through Database.migrate() (or
'teeter-api migrate'), which hands over a connection already inside a
transaction and, on Postgres, holding an advisory lock; this file only
configures the context on it."""

from alembic import context

from teeter_api import models  # noqa: F401  registers the tables
from teeter_api.db import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("run migrations through teeter_api.db.Database.migrate() or 'teeter-api migrate'")

context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    render_as_batch=connection.dialect.name == "sqlite",   # SQLite alters tables by copying them
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
