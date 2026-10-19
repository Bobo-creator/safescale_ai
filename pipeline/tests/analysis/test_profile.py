import json
from datetime import date

import pytest

from safescale.analysis.profile import build_profile, category_signal, overall_signal
from safescale.analysis.report import DISCLAIMER, RELEVANCE_FLOOR, HazardReport, Match
from safescale.taxonomy.classify import HazardLabel, StandardViolation

BASE = {"fire_overheating": 0.30, "burn": 0.17, "fall": 0.18, "other": 0.07, "choking": 0.12}


def match(recall_id, *categories, cosine=0.5):
    labels = [HazardLabel(c, f"evidence {c}", "hazard") for c in categories]
    return Match(
        recall_id,
        recall_id,
        cosine,
        cosine,
        f"T{recall_id}",
        f"https://x/{recall_id}",
        date(2020, 1, 1),
        labels,
        [],
        cosine >= RELEVANCE_FLOOR,
    )


@pytest.mark.parametrize(
    ("count", "share", "lift", "expected"),
    [
        (5, 0.40, 1.5, "HIGH"),
        (4, 0.80, 3.0, "MODERATE"),  # count just below HIGH
        (5, 0.39, 3.0, "MODERATE"),  # share just below HIGH
        (5, 0.60, 1.49, "MODERATE"),  # lift just below HIGH: common everywhere
        (3, 0.20, 0.5, "MODERATE"),
        (2, 0.50, 3.0, "LOW"),  # count just below MODERATE
        (3, 0.19, 3.0, "LOW"),  # share just below MODERATE
    ],
)
def test_category_signal_edges(count, share, lift, expected):
    assert category_signal(count, share, lift) == expected


def test_profile_counts_only_relevant_matches():
    matches = [match(i, "fire_overheating") for i in range(1, 6)] + [
        match(6, "burn"),
        match(7, "fire_overheating", cosine=RELEVANCE_FLOOR - 0.01),  # weak: listed, not counted
    ]
    profile = build_profile(matches, BASE)
    fire = next(s for s in profile if s.code == "fire_overheating")
    assert fire.count == 5 and fire.recall_ids == [1, 2, 3, 4, 5]
    assert fire.share == pytest.approx(5 / 6)
    assert fire.lift == pytest.approx((5 / 6) / 0.30)
    assert fire.signal == "HIGH"
    assert [s.code for s in profile] == ["fire_overheating", "burn"]  # strongest first


def test_categories_absent_from_matches_are_omitted():
    profile = build_profile([match(i, "fall") for i in range(5)], BASE)
    assert [s.code for s in profile] == ["fall"]


def test_overall_signal_and_drivers():
    matches = [match(i, "fire_overheating", "burn") for i in range(5)] + [match(9, "fall")] * 2
    signal, drivers, insufficient = overall_signal(build_profile(matches, BASE), relevant=7)
    assert (signal, drivers, insufficient) == ("HIGH", ["fire_overheating", "burn"], False)


def test_other_never_drives_the_signal():
    matches = [match(i, "other") for i in range(10)]
    profile = build_profile(matches, BASE)
    assert profile[0].code == "other" and profile[0].signal == "HIGH"
    assert overall_signal(profile, relevant=10) == ("LOW", [], False)


def test_few_relevant_matches_is_insufficient_evidence():
    matches = [match(i, "fire_overheating") for i in range(4)]
    assert overall_signal(build_profile(matches, BASE), relevant=4) == ("LOW", [], True)


def test_low_overall_has_no_drivers():
    matches = [
        match(i, c) for i, c in enumerate(["fire_overheating", "burn", "fall", "choking"] * 2)
    ]
    assert overall_signal(build_profile(matches, BASE), relevant=8) == ("LOW", [], False)


def test_report_to_dict_is_json_ready_with_disclaimer():
    m = match(1, "burn")
    m = Match(**{**m.__dict__, "violations": [StandardViolation("ASTM F2057", "e", "hazard")]})
    report = HazardReport(
        query="q",
        method="vector",
        k=1,
        matches=[m],
        relevant=1,
        relevance_floor=0.3,
        profile=build_profile([m], BASE),
        overall_signal="LOW",
        signal_drivers=[],
        insufficient_evidence=True,
        shared_terms=[],
        failure_terms=[],
        investigation_areas=[],
        standards=[],
        taxonomy_version=1,
    )
    data = json.loads(json.dumps(report.to_dict()))
    assert data["disclaimer"] == DISCLAIMER
    assert data["matches"][0]["recall_date"] == "2020-01-01"
    assert data["matches"][0]["relevant"] is True
    assert data["matches"][0]["violations"][0]["standard"] == "ASTM F2057"
