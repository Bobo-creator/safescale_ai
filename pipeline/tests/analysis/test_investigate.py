import re
from datetime import date

import pytest

from safescale.analysis.investigate import CATALOG, cited_standards, investigation_areas
from safescale.analysis.report import Match
from safescale.taxonomy.categories import CATEGORY_CODES
from safescale.taxonomy.classify import HazardLabel, StandardViolation

BANNED = re.compile(
    r"\bsafe\b|\bunsafe\b|complian|certif|guarante|\brequired\b|\bmust\b|\bensures?\b", re.I
)


def match(recall_id, categories, title="Product", hazard_text=None, standards=(), relevant=True):
    labels = [HazardLabel(c, f"posing a {c} hazard", "hazard") for c in categories]
    violations = [StandardViolation(s, "violates", "hazard") for s in standards]
    return Match(
        recall_id,
        recall_id,
        0.5,
        0.5,
        title,
        "https://x",
        date(2020, 1, 1),
        labels,
        violations,
        relevant,
        hazard_text,
    )


def test_catalog_is_well_formed():
    ids = [e.id for e in CATALOG]
    assert len(ids) == len(set(ids)) == 21
    for entry in CATALOG:
        assert entry.categories <= set(CATEGORY_CODES) - {"other"}
        assert entry.checks
        for pattern in entry.terms.values():
            re.compile(pattern)


@pytest.mark.parametrize(
    "text", [e.title for e in CATALOG] + [c for e in CATALOG for c in e.checks]
)
def test_catalog_wording_is_advisory(text):
    assert not BANNED.search(text), text


def test_area_needs_category_and_trigger_term_in_two_matches():
    matches = [
        match(1, ["fire_overheating"], "Lithium-ion Battery Packs Recalled"),
        match(2, ["fire_overheating"], hazard_text="The battery can overheat."),
        match(3, ["fire_overheating"], hazard_text="The heater can ignite."),  # no battery term
        match(4, ["fall"], hazard_text="The battery holder can break."),  # wrong category
    ]
    areas = {a.id: a for a in investigation_areas(matches)}
    battery = areas["battery_thermal"]
    assert battery.support == 2 and battery.recall_ids == [1, 2]
    assert battery.terms == ["battery", "lithium"]


def test_one_supporting_match_is_not_enough():
    matches = [match(1, ["fire_overheating"], "Lithium-ion Battery Packs Recalled")]
    assert investigation_areas(matches) == []


def test_weak_matches_never_support_an_area():
    matches = [match(i, ["drowning"], relevant=False) for i in range(5)]
    assert investigation_areas(matches) == []


def test_category_only_areas_and_ranking():
    matches = [match(i, ["crash_loss_of_control"]) for i in range(3)] + [
        match(10, ["drowning"]),
        match(11, ["drowning"]),
    ]
    areas = investigation_areas(matches)
    assert [(a.id, a.support) for a in areas] == [("brakes_steering", 3), ("water_use", 2)]


def test_cited_standards_need_two_relevant_matches():
    matches = [
        match(1, ["fall"], standards=["STURDY Act (furniture tip-over)"]),
        match(2, ["fall"], standards=["STURDY Act (furniture tip-over)", "ASTM F2057"]),
        match(3, ["fall"], standards=["ASTM F2057"], relevant=False),
        match(4, ["fall"], standards=[None]),
    ]
    stats = cited_standards(matches)
    assert [(s.standard, s.count, s.recall_ids) for s in stats] == [
        ("STURDY Act (furniture tip-over)", 2, [1, 2])
    ]


def test_chemical_burns_do_not_trigger_chemical_content():
    text = "Swallowed coin batteries can cause internal chemical burns."
    matches = [match(i, ["poisoning"], hazard_text=text) for i in range(3)]
    assert "chemical_content" not in {a.id for a in investigation_areas(matches)}
    lead = [match(i, ["poisoning"], hazard_text="The paint contains a chemical.") for i in range(2)]
    assert "chemical_content" in {a.id for a in investigation_areas(lead)}
