import psycopg
import pytest
from tests_support import TEST_DATABASE_URL

from safescale import db


@pytest.fixture
def conn():
    """A connection to a freshly emptied test database (public schema dropped and recreated)."""
    try:
        connection = psycopg.connect(TEST_DATABASE_URL, autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.skip(f"test database unavailable: {exc}")
    with connection:
        connection.execute("drop schema public cascade")
        connection.execute("create schema public")
        yield connection


@pytest.fixture
def migrated_conn(conn):
    db.migrate(conn)
    return conn


@pytest.fixture
def fixture_recalls(migrated_conn):
    """Migrated test DB loaded with the 18 fixture recalls."""
    from pathlib import Path

    from safescale.ingest import run_ingest

    run_ingest(migrated_conn, snapshot=Path(__file__).parent / "fixtures" / "recalls_sample.json")
    return migrated_conn
