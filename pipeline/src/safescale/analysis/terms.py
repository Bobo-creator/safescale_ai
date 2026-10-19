"""Terms the matches share with the description, and recurring failure terms in their hazard text.

Both use Postgres full-text lexemes (the same English stemming as keyword search) and rank terms by
(matches containing the term / relevant matches) x idf, so words common to every recall sink.
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import psycopg

from safescale.analysis.report import Match, Term

MAX_TERMS = 8
MIN_SHARED_MATCHES = 2
MIN_FAILURE_MATCHES = 3

# Token kinds worth showing: words and hyphenated words (not numbers, not URLs).
_WORD_ALIASES = {
    "asciiword",
    "word",
    "asciihword",
    "hword",
    "numhword",
    "hword_asciipart",
    "hword_part",
    "hword_numpart",
}
_PART_ALIASES = {"hword_asciipart", "hword_part", "hword_numpart"}

# Recall boilerplate that says nothing about the failure (stems, as Postgres produces them).
STOPLIST = {
    "recal",
    "recall",
    "consum",
    "product",
    "pose",
    "hazard",
    "risk",
    "injuri",
    "serious",
    "death",
    "children",
    "child",
    "young",
    "user",
    "can",
    "could",
    "result",
    "caus",
    "unit",
    "firm",
    "cpsc",
    "use",
    "may",
    "sold",
    "contact",
    "report",
    "incid",
    "includ",
}


@dataclass
class TermEvidence:
    """Which matches contain a lexeme, and how it is usually written."""

    recall_ids: set[int] = field(default_factory=set)
    surfaces: Counter = field(default_factory=Counter)
    is_part: bool = True  # only ever seen as part of a hyphenated word


def rank_terms(
    evidence: dict[str, TermEvidence],
    df: dict[str, int],
    n_docs: int,
    relevant: int,
    *,
    min_matches: int,
    exclude: set[str] = frozenset(),
) -> list[Term]:
    """Score, filter and order terms; drop word parts their whole hyphenated word covers."""
    scored = []
    for lexeme, ev in evidence.items():
        if lexeme in exclude or lexeme in STOPLIST or len(ev.recall_ids) < min_matches:
            continue
        if not any(ch.isalpha() for ch in lexeme) or len(lexeme) < 2:
            continue
        idf = math.log((n_docs + 1) / (df.get(lexeme, 0) + 1))
        scored.append((len(ev.recall_ids) / max(relevant, 1) * idf, lexeme, ev))
    scored.sort(key=lambda item: (-item[0], item[1]))

    kept: list[tuple[str, TermEvidence]] = []
    for _, lexeme, ev in scored:
        covered = any(
            ev.is_part
            and "-" in other
            and lexeme in other.split("-")
            and ev.recall_ids <= other_ev.recall_ids
            for other, other_ev in kept
        )
        if not covered:
            kept.append((lexeme, ev))
        if len(kept) == MAX_TERMS:
            break
    return [
        Term(
            term=ev.surfaces.most_common(1)[0][0],
            matches=len(ev.recall_ids),
            recall_ids=sorted(ev.recall_ids),
        )
        for _, ev in kept
    ]


def _query_lexemes(conn: psycopg.Connection, query: str) -> dict[str, tuple[str, bool]]:
    """lexeme -> (the user's own word, is_part), in query order."""
    out: dict[str, tuple[str, bool]] = {}
    for alias, token, lexemes in conn.execute(
        "select alias, token, lexemes from ts_debug('english', %s)", (query,)
    ):
        if alias in _WORD_ALIASES and lexemes:
            out.setdefault(lexemes[0], (token, alias in _PART_ALIASES))
    return out


def shared_terms(conn: psycopg.Connection, query: str, matches: list[Match]) -> list[Term]:
    ids = [m.recall_id for m in matches if m.relevant]
    if not ids:
        return []
    wanted = _query_lexemes(conn, query)
    rows = conn.execute(
        """
        select r.recall_id, t.lexeme
        from recalls r cross join lateral unnest(r.search_tsv) as t
        where r.recall_id = any(%s) and t.lexeme = any(%s)
        """,
        (ids, list(wanted)),
    ).fetchall()
    evidence: dict[str, TermEvidence] = defaultdict(TermEvidence)
    for recall_id, lexeme in rows:
        ev = evidence[lexeme]
        ev.recall_ids.add(recall_id)
        token, is_part = wanted[lexeme]
        ev.surfaces[token] += 1
        ev.is_part = is_part
    df, n_docs = _df(conn, "recall_term_df", list(evidence), "select count(*) from recalls")
    return rank_terms(evidence, df, n_docs, len(ids), min_matches=MIN_SHARED_MATCHES)


def failure_terms(conn: psycopg.Connection, query: str, matches: list[Match]) -> list[Term]:
    ids = [m.recall_id for m in matches if m.relevant]
    if not ids:
        return []
    rows = conn.execute(
        """
        select r.recall_id, d.alias, d.token, d.lexemes[1]
        from recalls r cross join lateral ts_debug('english', r.hazard_text) as d
        where r.recall_id = any(%s) and r.hazard_text is not null and d.lexemes <> '{}'
        """,
        (ids,),
    ).fetchall()
    evidence: dict[str, TermEvidence] = defaultdict(TermEvidence)
    for recall_id, alias, token, lexeme in rows:
        if alias not in _WORD_ALIASES:
            continue
        ev = evidence[lexeme]
        ev.recall_ids.add(recall_id)
        ev.surfaces[token.lower()] += 1
        ev.is_part = ev.is_part and alias in _PART_ALIASES
    df, n_docs = _df(
        conn,
        "recall_hazard_term_df",
        list(evidence),
        "select count(*) from recalls where hazard_text is not null",
    )
    exclude = set(_query_lexemes(conn, query))
    return rank_terms(
        evidence, df, n_docs, len(ids), min_matches=MIN_FAILURE_MATCHES, exclude=exclude
    )


def _df(conn, view: str, lexemes: list[str], count_sql: str) -> tuple[dict[str, int], int]:
    df = dict(conn.execute(f"select lexeme, ndoc from {view} where lexeme = any(%s)", (lexemes,)))
    return df, conn.execute(count_sql).fetchone()[0]


def refresh_term_stats(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("refresh materialized view recall_term_df")
        conn.execute("refresh materialized view recall_hazard_term_df")
