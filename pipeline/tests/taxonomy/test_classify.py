import re

from safescale.taxonomy.classify import MAX_EVIDENCE, classify, evidence


def test_hazard_text_and_title_both_count():
    result = classify(
        title="Acme Recalls Heaters Due to Fire Hazard",
        hazard_text="The heater's surface can get hot, posing a burn hazard.",
        description="Three people were burned.",
    )
    assert result.categories == ["fire_overheating", "burn"]
    by_cat = {label.category: label for label in result.labels}
    assert by_cat["fire_overheating"].source == "title"
    assert by_cat["burn"].source == "hazard"


def test_hazard_text_wins_over_title_for_the_same_category():
    result = classify(title="Recall Due to Fire Hazard", hazard_text="Fire", description=None)
    assert [(lbl.category, lbl.source) for lbl in result.labels] == [("fire_overheating", "hazard")]


def test_description_used_only_when_hazard_and_title_name_nothing():
    unused = classify(
        title="Recall of Chairs",
        hazard_text="The chair can tip over.",
        description="One child suffered a laceration.",
    )
    assert unused.categories == ["fall"]

    used = classify(title="Recall of Mowers", hazard_text=None, description="Blades can cut users.")
    assert [(lbl.category, lbl.source) for lbl in used.labels] == [("laceration", "description")]


def test_other_when_nothing_matches_with_evidence_from_first_nonempty_field():
    result = classify(title="Recall of Snow Boots", hazard_text=None, description=None)
    assert [(lbl.category, lbl.source, lbl.evidence) for lbl in result.labels] == [
        ("other", "title", "Recall of Snow Boots")
    ]
    hazard = classify(title="T", hazard_text="Posing an injury hazard.", description="D")
    assert hazard.labels[0].source == "hazard"
    assert hazard.labels[0].evidence == "Posing an injury hazard."


def test_always_at_least_one_label_even_with_no_text():
    result = classify(title="", hazard_text=None, description=None)
    assert result.categories == ["other"] and result.labels[0].evidence


def test_evidence_is_the_matching_sentence():
    text = "The handle can break. This exposes the wiring, posing a shock hazard. Stop using it."
    result = classify(title="", hazard_text=text, description=None)
    assert result.labels[0].evidence == "This exposes the wiring, posing a shock hazard."


def test_long_evidence_is_trimmed_verbatim_around_the_match():
    text = ("word " * 60) + "posing a fire hazard " + ("word " * 60)
    match = re.search("fire", text)
    fragment = evidence(text, match)
    assert len(fragment) <= MAX_EVIDENCE
    assert "fire" in fragment and fragment in text


def test_labels_come_in_category_order():
    result = classify(title="", hazard_text="Drowning, laceration and fire.", description=None)
    assert result.categories == ["fire_overheating", "laceration", "drowning"]
