import os

import psycopg
import pytest

from safescale import config, db

config.load_dotenv()
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost/safescale_test")


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
