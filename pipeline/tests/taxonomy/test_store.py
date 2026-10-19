from safescale.cli import main
from safescale.taxonomy.categories import CATEGORIES
from safescale.taxonomy.rules import TAXONOMY_VERSION
from safescale.taxonomy.store import classify_all, labels_for

LITHIUM_RECALL_ID = 166


def _rows(conn):
    hazards = conn.execute(
        "select recall_id, category, evidence, source, taxonomy_version from recall_hazards "
        "order by 1, 2"
    ).fetchall()
    violations = conn.execute(
        "select recall_id, standard, evidence, source from recall_standard_violations order by 1, 2"
    ).fetchall()
    return hazards, violations


def test_category_seed_matches_code(migrated_conn):
    rows = migrated_conn.execute(
        "select code, label, description from hazard_categories order by sort_order"
    ).fetchall()
    assert rows == [(c.code, c.label, c.description) for c in CATEGORIES]


def test_every_recall_gets_a_label_and_rerun_is_identical(fixture_recalls):
    result = classify_all(fixture_recalls)
    assert result.recalls == 18
    first = _rows(fixture_recalls)
    unlabeled = fixture_recalls.execute(
        "select count(*) from recalls r where not exists "
        "(select 1 from recall_hazards h where h.recall_id = r.recall_id)"
    ).fetchone()[0]
    assert unlabeled == 0
    assert {row[4] for row in first[0]} == {TAXONOMY_VERSION}

    classify_all(fixture_recalls)
    assert _rows(fixture_recalls) == first


def test_evidence_appears_verbatim_in_its_source_field(fixture_recalls):
    classify_all(fixture_recalls)
    bad = fixture_recalls.execute(
        """
        select x.recall_id, x.evidence from (
          select recall_id, evidence, source from recall_hazards
          union all
          select recall_id, evidence, source from recall_standard_violations
        ) x join recalls r using (recall_id)
        where strpos(case x.source when 'hazard' then r.hazard_text when 'title' then r.title
                     else r.description end, x.evidence) = 0
        """
    ).fetchall()
    assert bad == []


def test_labels_for_reads_back_in_category_order(fixture_recalls):
    classify_all(fixture_recalls)
    ids = [row[0] for row in fixture_recalls.execute("select recall_id from recalls")]
    found = labels_for(fixture_recalls, ids + [999_999_999])
    assert set(found) == set(ids)
    assert found[LITHIUM_RECALL_ID].categories == ["fire_overheating"]
    order = [c.code for c in CATEGORIES]
    for result in found.values():
        assert result.categories == sorted(result.categories, key=order.index)


def test_labels_for_unclassified_recalls_is_empty(fixture_recalls):
    assert labels_for(fixture_recalls, [LITHIUM_RECALL_ID]) == {}


def test_cli_classify_and_hazards(fixture_recalls, monkeypatch, capsys):
    from tests_support import TEST_DATABASE_URL

    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    assert main(["classify"]) == 0
    assert "classified 18 recalls" in capsys.readouterr().out
    assert main(["hazards", str(LITHIUM_RECALL_ID)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("fire_overheating") and "posing a fire hazard" in out
    assert main(["hazards", "999999999"]) == 1
