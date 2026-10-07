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


def test_rls_enabled_on_every_public_table(migrated_conn):
    rows = migrated_conn.execute(
        "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
    )
    assert [row[0] for row in rows] == []
