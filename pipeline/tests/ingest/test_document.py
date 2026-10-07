import json
from pathlib import Path

import pytest

from safescale.ingest.clean import to_clean_recall
from safescale.ingest.document import _NO_INJURIES, build_document, content_hash

FIXTURES = json.loads((Path(__file__).parents[1] / "fixtures" / "recalls_sample.json").read_text())
RECALLS = {record["RecallID"]: to_clean_recall(record) for record in FIXTURES}


def test_every_fixture_produces_a_titled_document():
    for recall in RECALLS.values():
        document = build_document(recall)
        assert document.startswith(f"Title: {recall.title}")


def test_sections_appear_in_canonical_order():
    document = build_document(RECALLS[4])
    labels = [line.split(":", 1)[0] for line in document.splitlines()]
    order = ["Title", "Products", "Product types", "Hazard", "Description", "Injuries"]
    assert labels == [label for label in order if label in labels]


def test_empty_sections_are_omitted():
    no_hazard = build_document(RECALLS[3722])
    assert "\nHazard:" not in no_hazard
    assert "\nDescription:" not in build_document(RECALLS[2574])
    assert "\nProduct types:" not in build_document(RECALLS[9491])


def test_no_injury_placeholders_are_left_out():
    # "None reported" is in every other record and would only add noise to retrieval.
    assert RECALLS[2].injuries_text.startswith("None reported")
    assert "\nInjuries:" not in build_document(RECALLS[2])


@pytest.mark.parametrize(
    "text",
    ["None reported.", "No incidents have been reported.", "There were no injuries reported."],
)
def test_no_injury_phrasings_match(text):
    assert _NO_INJURIES.match(text)


def test_reported_injuries_are_included():
    assert "\nInjuries:" in build_document(RECALLS[20])


def test_hash_is_deterministic_sha256_hex():
    document = build_document(RECALLS[166])
    assert content_hash(document) == content_hash(build_document(to_clean_recall(FIXTURES[14])))
    assert len(content_hash(document)) == 64
    assert content_hash(document) != content_hash(document + " ")
