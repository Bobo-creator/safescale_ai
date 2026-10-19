import pytest

from safescale.explain.schema import (
    ExplanationDraft,
    HazardParagraph,
    InvestigationNote,
    MatchReason,
    Sentence,
)
from safescale.explain.validate import Grounding, normalize_number, numbers_in, validate

G = Grounding(
    match_ids={1, 2, 3, 4},
    category_ids={"fire_overheating": {1, 2}, "burn": {2, 3}},
    area_ids={"battery_thermal": {1, 2}},
    numbers={"14", "25", "56", "1.9", "2000"},
)
OK = Sentence(text="14 of 25 similar recalls involved fire, 1.9× their usual share.", citations=[1])


def draft(summary=(OK,), hazards=(), reasons=(), notes=()):
    return ExplanationDraft(
        summary=list(summary),
        hazards=list(hazards),
        match_reasons=list(reasons),
        investigation_notes=list(notes),
    )


def reasons_of(result):
    return [(d.where, d.reason) for d in result.dropped]


def test_numbers_are_normalized():
    assert normalize_number("1,250") == "1250" and normalize_number("1.90") == "1.9"
    assert numbers_in("56% of 25 (1.9×), 2,000 mAh") == {"56", "25", "1.9", "2000"}


def test_valid_draft_passes_untouched():
    d = draft(
        hazards=[HazardParagraph(category="fire_overheating", sentences=[OK])],
        reasons=[MatchReason(recall_id=2, shared=["lithium-ion battery"], different=["a lamp"])],
        notes=[InvestigationNote(area_id="battery_thermal", sentence=OK)],
    )
    result = validate(d, G)
    assert result.dropped == [] and result.draft == d and not result.needs_retry


@pytest.mark.parametrize(
    ("sentence", "reason"),
    [
        (Sentence(text="Fire recurs.", citations=[]), "no citation"),
        (Sentence(text="Fire recurs.", citations=[99]), "not in the evidence: [99]"),
        (
            Sentence(text="Fire was in 80% of them.", citations=[1]),
            "numbers not in the evidence: 80",
        ),
        (
            Sentence(text="The product is safe to ship.", citations=[1]),
            "non-advisory wording 'safe'",
        ),
        (
            Sentence(text="It is compliant with ASTM.", citations=[1]),
            "non-advisory wording 'complian'",
        ),
        (Sentence(text="Units will fail when charged.", citations=[1]), "'will fail'"),
        (Sentence(text="   ", citations=[1]), "empty sentence"),
    ],
)
def test_bad_summary_sentences_are_dropped(sentence, reason):
    result = validate(draft(summary=[OK, sentence]), G)
    assert result.draft.summary == [OK]
    (dropped,) = result.dropped
    assert dropped.where == "summary[1]" and reason in dropped.reason


def test_multiplier_from_the_packet_is_allowed_but_not_an_invented_one():
    fine = Sentence(text="Burns appear 1.9x as often.", citations=[1])
    wrong = Sentence(text="Burns appear 3x as often.", citations=[1])
    result = validate(draft(summary=[fine, wrong]), G)
    assert result.draft.summary == [fine] and "3" in result.dropped[0].reason


def test_hazard_paragraph_may_only_cite_recalls_with_that_category():
    off = Sentence(text="Burns recur.", citations=[1])  # recall 1 has fire, not burn
    on = Sentence(text="Burns recur.", citations=[2, 3])
    result = validate(draft(hazards=[HazardParagraph(category="burn", sentences=[off, on])]), G)
    assert result.draft.hazards == [HazardParagraph(category="burn", sentences=[on])]
    assert reasons_of(result) == [
        ("hazards[burn][0]", "cites recalls that don't support this claim: [1]")
    ]


def test_hazard_category_must_be_in_the_report_and_unique():
    s = Sentence(text="Shocks recur.", citations=[1])
    result = validate(
        draft(
            hazards=[
                HazardParagraph(category="electrical_shock", sentences=[s]),
                HazardParagraph(category="fire_overheating", sentences=[OK]),
                HazardParagraph(category="fire_overheating", sentences=[OK]),
            ]
        ),
        G,
    )
    assert [p.category for p in result.draft.hazards] == ["fire_overheating"]
    assert [r for _, r in reasons_of(result)] == ["category not in report", "duplicate category"]


def test_paragraph_with_no_valid_sentence_disappears():
    bad = Sentence(text="Fire recurs.", citations=[3])  # 3 has burn only
    result = validate(
        draft(hazards=[HazardParagraph(category="fire_overheating", sentences=[bad])]), G
    )
    assert result.draft.hazards == []


def test_size_limits():
    result = validate(
        draft(
            summary=[OK] * 5,
            hazards=[HazardParagraph(category="fire_overheating", sentences=[OK] * 4)],
        ),
        G,
    )
    assert len(result.draft.summary) == 4 and len(result.draft.hazards[0].sentences) == 3
    assert {r for _, r in reasons_of(result)} == {
        "more than 4 summary sentences",
        "more than 3 sentences",
    }


def test_match_reasons():
    good = MatchReason(recall_id=1, shared=["2000 mAh battery"], different=[])
    result = validate(
        draft(
            reasons=[
                good,
                MatchReason(recall_id=1, shared=["battery"], different=[]),  # duplicate
                MatchReason(recall_id=99, shared=["battery"], different=[]),  # not in evidence
                MatchReason(recall_id=2, shared=[], different=["a lamp"]),  # nothing shared
                MatchReason(recall_id=3, shared=["a safe design"], different=[]),  # wording
            ]
        ),
        G,
    )
    assert result.draft.match_reasons == [good]
    assert [r for _, r in reasons_of(result)] == [
        "duplicate recall",
        "recall 99 is not in the evidence",
        "no shared features",
        "uses non-advisory wording 'safe'",
    ]


def test_investigation_notes():
    on = Sentence(text="Cells overheated while charging.", citations=[1, 2])
    off = Sentence(text="Cells overheated.", citations=[3])
    result = validate(
        draft(
            notes=[
                InvestigationNote(area_id="battery_thermal", sentence=off),
                InvestigationNote(area_id="battery_thermal", sentence=on),
                InvestigationNote(area_id="battery_thermal", sentence=on),
                InvestigationNote(area_id="magnets", sentence=on),
            ]
        ),
        G,
    )
    assert result.draft.investigation_notes == [
        InvestigationNote(area_id="battery_thermal", sentence=on)
    ]
    assert [r for _, r in reasons_of(result)] == [
        "cites recalls that don't support this claim: [3]",
        "duplicate area",
        "area not in report",
    ]


def test_needs_retry_when_summary_lost_or_too_much_dropped():
    lost = validate(draft(summary=[Sentence(text="x", citations=[99])]), G)
    assert lost.draft.summary == [] and lost.needs_retry
    bad = Sentence(text="Fire.", citations=[99])
    mostly_bad = validate(draft(summary=[OK, bad, bad]), G)
    assert mostly_bad.needs_retry  # 2 of 3 dropped
    one_bad = validate(draft(summary=[OK, OK, OK, bad]), G)
    assert not one_bad.needs_retry  # exactly 25% is tolerated
    assert one_bad.feedback() == ["summary[3]: cites recalls that are not in the evidence: [99]"]
