from safescale import db


def _tables(conn) -> set[str]:
    rows = conn.execute("select tablename from pg_tables where schemaname = 'public'")
    return {row[0] for row in rows}


def test_migrate_creates_tables(conn):
    applied = db.migrate(conn)
    assert applied == ["001_recalls.sql"]
    assert {"recalls", "ingest_runs", "schema_migrations"} <= _tables(conn)


def test_migrate_is_idempotent(conn):
    db.migrate(conn)
    assert db.migrate(conn) == []


def test_rls_enabled_on_data_tables(migrated_conn):
    rows = migrated_conn.execute(
        "select relname from pg_class where relname in ('recalls', 'ingest_runs') "
        "and relrowsecurity"
    )
    assert {row[0] for row in rows} == {"recalls", "ingest_runs"}
