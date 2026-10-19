import psycopg
import pytest

from safescale.api.limits import (
    Limits,
    check_analysis,
    check_explanation,
    hit,
    prune,
    visitor_key,
)


def test_visitor_key_is_salted_and_not_the_ip():
    a = visitor_key("203.0.113.7", "salt-1")
    assert a == visitor_key("203.0.113.7", "salt-1") != visitor_key("203.0.113.7", "salt-2")
    assert "203" not in a and len(a) == 32


def test_hit_counts_up_to_the_limit_then_refuses(migrated_conn):
    decisions = [hit(migrated_conn, "analyze:v", limit=3, unit="hour") for _ in range(5)]
    assert [d.allowed for d in decisions] == [True, True, True, False, False]
    assert 0 < decisions[-1].retry_after <= 3600
    hits = migrated_conn.execute("select hits from app_rate_limits").fetchone()[0]
    assert hits == 3  # refused requests don't increment


def test_buckets_are_independent(migrated_conn):
    hit(migrated_conn, "analyze:a", limit=1, unit="hour")
    assert hit(migrated_conn, "analyze:b", limit=1, unit="hour").allowed
    assert not hit(migrated_conn, "analyze:a", limit=1, unit="hour").allowed


def test_daily_cap_is_shared_and_only_counted_for_allowed_visitors(migrated_conn):
    limits = Limits(analyses_per_hour=30, explanations_per_hour=1, explanations_per_day=2)
    mine, everyone = check_explanation(migrated_conn, "v1", limits)
    assert mine.allowed and everyone.allowed
    mine, everyone = check_explanation(migrated_conn, "v1", limits)  # v1 over its hourly limit
    assert not mine.allowed and everyone is None
    assert check_explanation(migrated_conn, "v2", limits)[1].allowed  # global: 2 of 2
    mine, everyone = check_explanation(migrated_conn, "v3", limits)
    assert mine.allowed and not everyone.allowed  # cap reached for everyone


def test_check_analysis_uses_the_hourly_limit(migrated_conn):
    limits = Limits(analyses_per_hour=2)
    assert [check_analysis(migrated_conn, "v", limits).allowed for _ in range(3)] == [
        True,
        True,
        False,
    ]


def test_limits_from_env(monkeypatch):
    monkeypatch.setenv("LIMIT_EXPLANATIONS_PER_DAY", "5")
    assert Limits.from_env() == Limits(explanations_per_day=5)


def test_prune_removes_old_windows(migrated_conn):
    migrated_conn.execute(
        "insert into app_rate_limits values ('old', now() - interval '3 days', 1), "
        "('new', date_trunc('hour', now()), 1)"
    )
    assert prune(migrated_conn) == 1
    assert [r[0] for r in migrated_conn.execute("select bucket from app_rate_limits")] == ["new"]


def test_unknown_unit_is_rejected(migrated_conn):
    with pytest.raises(ValueError):
        hit(migrated_conn, "x", limit=1, unit="minute")


# --- the app role's privileges --------------------------------------------------------------


def as_app(conn, sql, params=None):
    """Run one statement as safescale_app, then roll back."""
    try:
        with conn.transaction():
            conn.execute("set local role safescale_app")
            rows = (
                conn.execute(sql, params).fetchall()
                if sql.lstrip().startswith(("select", "with"))
                else conn.execute(sql, params)
            )
            raise _Rollback(rows)
    except _Rollback as done:
        return done.rows


class _Rollback(Exception):
    def __init__(self, rows):
        self.rows = rows


def test_app_role_reads_what_analysis_needs(fixture_recalls):
    from safescale.analysis.terms import refresh_term_stats
    from safescale.taxonomy.store import classify_all

    classify_all(fixture_recalls)
    refresh_term_stats(fixture_recalls)
    for table in ("recalls", "recall_hazards", "hazard_categories", "recall_term_df"):
        assert as_app(fixture_recalls, f"select count(*) from {table}")[0][0] > 0, table
    assert as_app(fixture_recalls, "select * from search_recalls_keyword('battery fire', 3)")


@pytest.mark.parametrize(
    "sql",
    [
        "insert into recall_hazards values (1, 'burn', 'x', 'hazard', 1)",
        "update recalls set title = 'x'",
        "delete from recall_embeddings",
        "select * from ingest_runs",
        "select * from schema_migrations",
        "create table evil (id int)",
        "drop table app_rate_limits",
    ],
)
def test_app_role_cannot_write_data_or_change_the_schema(fixture_recalls, sql):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app(fixture_recalls, sql)


def test_app_role_can_use_the_rate_limit_table(migrated_conn):
    as_app(migrated_conn, "insert into app_rate_limits values ('b', now(), 1)")
