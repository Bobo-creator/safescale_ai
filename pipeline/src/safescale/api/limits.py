"""Rate limits for the public API, enforced in Postgres before any paid call.

Visitors are identified by a salted hash of their IP address. The table stores only
(bucket, window, hits): no IPs and no product descriptions.
"""

import hashlib
import os
from dataclasses import dataclass

import psycopg

_HIT = """
insert into app_rate_limits as l (bucket, window_start, hits)
values (%(bucket)s, date_trunc(%(unit)s, now()), 1)
on conflict (bucket, window_start) do update set hits = l.hits + 1
  where l.hits < %(limit)s
returning hits, extract(epoch from (date_trunc(%(unit)s, now()) + ('1 ' || %(unit)s)::interval
                                     - now()))::int
"""
_RETRY_AFTER = """
select extract(epoch from (date_trunc(%(unit)s, now()) + ('1 ' || %(unit)s)::interval - now()))::int
"""


@dataclass(frozen=True)
class Limits:
    analyses_per_hour: int = 30
    explanations_per_hour: int = 10
    explanations_per_day: int = 300  # all visitors together: the OpenAI spend guard

    @classmethod
    def from_env(cls) -> "Limits":
        defaults = cls()
        return cls(
            int(os.environ.get("LIMIT_ANALYSES_PER_HOUR", defaults.analyses_per_hour)),
            int(os.environ.get("LIMIT_EXPLANATIONS_PER_HOUR", defaults.explanations_per_hour)),
            int(os.environ.get("LIMIT_EXPLANATIONS_PER_DAY", defaults.explanations_per_day)),
        )


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int = 0  # seconds until the window resets (when not allowed)


def visitor_key(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


def hit(conn: psycopg.Connection, bucket: str, *, limit: int, unit: str) -> Decision:
    """Count one request in the current hour/day window; refuse once the limit is reached.

    Atomic: the upsert only increments while under the limit, so concurrent requests can't
    overshoot it.
    """
    if unit not in ("hour", "day"):
        raise ValueError(f"unit must be 'hour' or 'day', not {unit!r}")
    params = {"bucket": bucket, "unit": unit, "limit": limit}
    with conn.transaction():
        row = conn.execute(_HIT, params).fetchone()
        if row is not None:
            return Decision(True)
        return Decision(False, conn.execute(_RETRY_AFTER, params).fetchone()[0])


def check_analysis(conn, visitor: str, limits: Limits) -> Decision:
    return hit(conn, f"analyze:{visitor}", limit=limits.analyses_per_hour, unit="hour")


def check_explanation(conn, visitor: str, limits: Limits) -> tuple[Decision, Decision | None]:
    """(visitor decision, global decision). The global cap is only counted if the visitor is
    allowed, so one visitor's refused requests don't use up everyone's daily budget."""
    mine = hit(conn, f"explain:{visitor}", limit=limits.explanations_per_hour, unit="hour")
    if not mine.allowed:
        return mine, None
    return mine, hit(conn, "global:explain", limit=limits.explanations_per_day, unit="day")


def prune(conn: psycopg.Connection) -> int:
    """Delete windows older than two days; returns rows removed."""
    with conn.transaction():
        cur = conn.execute(
            "delete from app_rate_limits where window_start < now() - interval '2 days'"
        )
        return cur.rowcount
