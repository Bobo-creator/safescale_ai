"""Postgres connection and a minimal, ordered SQL migration runner."""

import logging
from pathlib import Path

import psycopg

from safescale import config

log = logging.getLogger(__name__)

_CREATE_MIGRATIONS_TABLE = """
create table if not exists schema_migrations (
  filename   text primary key,
  applied_at timestamptz not null default now()
)
"""


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or config.database_url())


def migrate(conn: psycopg.Connection, migrations_dir: Path = config.MIGRATIONS_DIR) -> list[str]:
    """Apply pending *.sql files in filename order, each in its own transaction.

    Returns the filenames applied by this call (empty when already up to date).
    """
    with conn.transaction():
        conn.execute(_CREATE_MIGRATIONS_TABLE)
        applied = {row[0] for row in conn.execute("select filename from schema_migrations")}

    newly_applied = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in applied:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute("insert into schema_migrations (filename) values (%s)", (path.name,))
        log.info("applied migration %s", path.name)
        newly_applied.append(path.name)
    return newly_applied
