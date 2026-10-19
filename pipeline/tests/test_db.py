from safescale import db


def _tables(conn) -> set[str]:
    rows = conn.execute("select tablename from pg_tables where schemaname = 'public'")
    return {row[0] for row in rows}


def test_migrate_creates_tables(conn):
    applied = db.migrate(conn)
    assert applied == [
        "001_recalls.sql",
        "002_retrieval.sql",
        "003_vector_search_plan.sql",
        "004_hazard_taxonomy.sql",
        "005_vector_search_ef_search.sql",
        "006_term_stats.sql",
    ]
    assert {
        "recalls",
        "ingest_runs",
        "schema_migrations",
        "recall_embeddings",
        "hazard_categories",
        "recall_hazards",
        "recall_standard_violations",
    } <= _tables(conn)


def test_migrate_is_idempotent(conn):
    db.migrate(conn)
    assert db.migrate(conn) == []


def test_rls_enabled_on_every_public_table(migrated_conn):
    rows = migrated_conn.execute(
        "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
    )
    assert [row[0] for row in rows] == []


def test_term_views_hidden_from_data_api_roles(migrated_conn):
    """Materialized views can't use RLS; on Supabase the API roles must have no access."""
    roles = [
        r[0]
        for r in migrated_conn.execute(
            "select rolname from pg_roles where rolname in ('anon', 'authenticated')"
        )
    ]
    for role in roles:
        for view in ("recall_term_df", "recall_hazard_term_df"):
            row = migrated_conn.execute(
                "select has_table_privilege(%s, %s, 'select')", (role, view)
            ).fetchone()
            assert row[0] is False, f"{role} can read {view}"
