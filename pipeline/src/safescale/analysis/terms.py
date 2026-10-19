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

# Recall and regulatory boilerplate that says nothing about how the product failed (stems, as
# Postgres produces them).
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
    # regulatory wording
    "violat",
    "mandatori",
    "standard",
    "requir",
    "law",
    "rees",
    "feder",
    "compli",
    "complianc",
    "addit",
    "also",
    "meet",
    "regul",
    "act",
    "warn",
    "label",
    "packag",
    "easili",
    "access",
    "contain",
    "fail",
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


def query_lexemes(conn: psycopg.Connection, query: str) -> dict[str, tuple[str, bool]]:
    """lexeme -> (the user's own word, is_part), in query order."""
    out: dict[str, tuple[str, bool]] = {}
    for alias, token, lexemes in conn.execute(
        "select alias, token, lexemes from ts_debug('english', %s)", (query,)
    ):
        if alias in _WORD_ALIASES and lexemes:
            out.setdefault(lexemes[0], (token, alias in _PART_ALIASES))
    return out


def shared_terms(
    conn: psycopg.Connection, query_words: dict[str, tuple[str, bool]], matches: list[Match]
) -> list[Term]:
    """`query_words` comes from query_lexemes(); one query fetches matches and frequencies."""
    ids = [m.recall_id for m in matches if m.relevant]
    if not ids or not query_words:
        return []
    rows = conn.execute(
        """
        select r.recall_id, t.lexeme, df.ndoc, (select count(*) from recalls)
        from recalls r
        cross join lateral unnest(r.search_tsv) as t
        left join recall_term_df df on df.lexeme = t.lexeme
        where r.recall_id = any(%s) and t.lexeme = any(%s)
        """,
        (ids, list(query_words)),
    ).fetchall()
    evidence: dict[str, TermEvidence] = defaultdict(TermEvidence)
    df: dict[str, int] = {}
    n_docs = 0
    for recall_id, lexeme, ndoc, total in rows:
        ev = evidence[lexeme]
        ev.recall_ids.add(recall_id)
        token, is_part = query_words[lexeme]
        ev.surfaces[token] += 1
        ev.is_part = is_part
        df[lexeme], n_docs = ndoc or 0, total
    return rank_terms(evidence, df, n_docs, len(ids), min_matches=MIN_SHARED_MATCHES)


def failure_terms(
    conn: psycopg.Connection, query_words: dict[str, tuple[str, bool]], matches: list[Match]
) -> list[Term]:
    """Recurring words in the matches' hazard text that the description doesn't mention."""
    ids = [m.recall_id for m in matches if m.relevant]
    if not ids:
        return []
    rows = conn.execute(
        """
        select d.recall_id, d.alias, d.token, d.lexeme, df.ndoc,
               (select count(*) from recalls where hazard_text is not null)
        from (
          select r.recall_id, t.alias, t.token, t.lexemes[1] as lexeme
          from recalls r cross join lateral ts_debug('english', r.hazard_text) as t
          where r.recall_id = any(%s) and r.hazard_text is not null and t.lexemes <> '{}'
        ) d
        left join recall_hazard_term_df df on df.lexeme = d.lexeme
        """,
        (ids,),
    ).fetchall()
    evidence: dict[str, TermEvidence] = defaultdict(TermEvidence)
    df: dict[str, int] = {}
    n_docs = 0
    for recall_id, alias, token, lexeme, ndoc, total in rows:
        if alias not in _WORD_ALIASES:
            continue
        ev = evidence[lexeme]
        ev.recall_ids.add(recall_id)
        ev.surfaces[token.lower()] += 1
        ev.is_part = ev.is_part and alias in _PART_ALIASES
        df[lexeme], n_docs = ndoc or 0, total
    return rank_terms(
        evidence, df, n_docs, len(ids), min_matches=MIN_FAILURE_MATCHES, exclude=set(query_words)
    )


def refresh_term_stats(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("refresh materialized view recall_term_df")
        conn.execute("refresh materialized view recall_hazard_term_df")
