from datetime import date

import pytest

from safescale.analysis.report import Match
from safescale.analysis.terms import (
    TermEvidence,
    failure_terms,
    query_lexemes,
    rank_terms,
    refresh_term_stats,
    shared_terms,
)
from safescale.taxonomy.store import classify_all


def ev(ids, surface, is_part=False):
    e = TermEvidence(set(ids), is_part=is_part)
    e.surfaces[surface] += 1
    return e


def test_rank_prefers_distinctive_terms_and_applies_minimum():
    evidence = {
        "batteri": ev([1, 2, 3], "battery"),
        "charg": ev([1, 2, 3], "charging"),  # same support, but far more common in the corpus
        "lamp": ev([1], "lamp"),  # below the minimum
    }
    df = {"batteri": 50, "charg": 900, "lamp": 10}
    terms = rank_terms(evidence, df, 10_000, relevant=5, min_matches=2)
    assert [t.term for t in terms] == ["battery", "charging"]
    assert terms[0].matches == 3 and terms[0].recall_ids == [1, 2, 3]


def test_rank_drops_stoplist_numbers_and_excluded():
    evidence = {
        "hazard": ev([1, 2, 3], "hazard"),
        "2000": ev([1, 2, 3], "2000"),
        "overheat": ev([1, 2, 3], "overheat"),
        "batteri": ev([1, 2, 3], "battery"),
    }
    terms = rank_terms(evidence, {}, 100, relevant=3, min_matches=2, exclude={"batteri"})
    assert [t.term for t in terms] == ["overheat"]


def test_word_parts_covered_by_their_hyphenated_word_are_dropped():
    evidence = {
        "lithium-ion": ev([1, 2, 3], "lithium-ion"),
        "lithium": ev([1, 2], "lithium", is_part=True),  # covered: same recalls, part of it
        "ion": ev([1, 2, 3, 4], "ion", is_part=True),  # not covered: appears in recall 4 too
    }
    terms = rank_terms(evidence, {}, 100, relevant=4, min_matches=2)
    assert {t.term for t in terms} == {"lithium-ion", "ion"}


def _matches(conn, ids, relevant=True):
    rows = conn.execute(
        "select recall_id, title, url, recall_date from recalls where recall_id = any(%s)", (ids,)
    ).fetchall()
    return [
        Match(rid, i + 1, 0.5, 0.5, title, url, d or date(2000, 1, 1), [], [], relevant)
        for i, (rid, title, url, d) in enumerate(rows)
    ]


@pytest.fixture
def stats(fixture_recalls):
    classify_all(fixture_recalls)
    refresh_term_stats(fixture_recalls)
    return fixture_recalls


def test_shared_terms_use_the_users_wording(stats):
    ids = [r[0] for r in stats.execute("select recall_id from recalls")]
    terms = shared_terms(
        stats, query_lexemes(stats, "Rechargeable lithium-ion BATTERY packs"), _matches(stats, ids)
    )
    words = {t.term for t in terms}
    assert "BATTERY" in words  # the user's spelling, not the stem 'batteri'
    assert all(t.matches >= 2 for t in terms)
    assert all(set(t.recall_ids) <= set(ids) for t in terms)


def test_failure_terms_exclude_query_words_and_need_three_matches(stats):
    ids = [r[0] for r in stats.execute("select recall_id from recalls")]
    terms = failure_terms(stats, query_lexemes(stats, "fire"), _matches(stats, ids))
    assert terms and all(t.matches >= 3 for t in terms)
    assert "fire" not in {t.term for t in terms}
    assert all(t.term == t.term.lower() for t in terms)


def test_no_relevant_matches_means_no_terms(stats):
    ids = [r[0] for r in stats.execute("select recall_id from recalls")]
    weak = _matches(stats, ids, relevant=False)
    words = query_lexemes(stats, "battery")
    assert shared_terms(stats, words, weak) == [] and failure_terms(stats, words, weak) == []
