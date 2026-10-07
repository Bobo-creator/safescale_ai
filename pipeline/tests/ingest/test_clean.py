import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from safescale.ingest.clean import clean_list, clean_text, to_clean_recall
from safescale.ingest.models import RawRecall

FIXTURES = json.loads((Path(__file__).parents[1] / "fixtures" / "recalls_sample.json").read_text())
BY_ID = {record["RecallID"]: record for record in FIXTURES}


def clean(recall_id: int):
    return to_clean_recall(BY_ID[recall_id])


# --- clean_text -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("None", None),
        ("n/a", None),
        ("None reported", "None reported"),  # meaningful value, not a placeholder
        ("Tom &amp; Jerry", "Tom & Jerry"),
        ("line one<br />line two", "line one line two"),
        ("<p>Hello</p><td>world</td>", "Hello world"),
        ("a b", "a b"),
        ("  lots \n\t of   space  ", "lots of space"),
        ("&lt;b&gt;kept as text&lt;/b&gt;", "<b>kept as text</b>"),  # escaped markup is text
    ],
)
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


def test_clean_list_drops_empties_and_dedupes_in_order():
    assert clean_list(["B", "", " a ", "B", None, "None", "a"]) == ["B", "a"]


# --- parsing ----------------------------------------------------------------------------------


def test_every_fixture_parses():
    for record in FIXTURES:
        RawRecall.model_validate(record)


def test_malformed_record_names_the_bad_field():
    bad = {**BY_ID[1], "RecallDate": "not a date"}
    with pytest.raises(ValidationError, match="RecallDate"):
        RawRecall.model_validate(bad)


def test_blank_title_is_rejected():
    with pytest.raises(ValidationError, match="Title"):
        RawRecall.model_validate({**BY_ID[1], "Title": "  "})


# --- to_clean_recall: fixture edge cases --------------------------------------------------------


def test_basic_fields_and_dates():
    recall = clean(9491)
    assert recall.recall_id == 9491
    assert isinstance(recall.recall_date, date)
    assert recall.url.startswith("https://www.cpsc.gov/")
    assert recall.raw == BY_ID[9491]  # original kept unmodified


def test_no_hazards_gives_null_hazard_text():
    assert clean(3722).hazard_text is None


def test_no_description_gives_null():
    assert clean(2574).description is None


def test_html_is_stripped_everywhere():
    recall = clean(205)
    for value in (recall.title, recall.description, recall.hazard_text, recall.remedy_text):
        assert value is None or "<" not in value


def test_entities_are_unescaped():
    cleaned = {k: v for k, v in clean(9237).__dict__.items() if k != "raw"}  # raw stays verbatim
    assert "&amp;" not in json.dumps(cleaned, default=str)


def test_multiple_products_and_hazards_are_kept():
    assert len(clean(3724).product_names) > 2
    assert ";" in clean(3760).hazard_text


def test_duplicate_and_empty_product_names_are_removed():
    names = clean(4670).product_names
    assert len(names) == len(set(names))
    assert "" not in clean(3730).product_names


def test_recent_record_has_no_product_types():
    assert clean(9491).product_types == []


def test_old_record_keeps_product_types():
    assert clean(4).product_types != []


def test_whitespace_is_normalized():
    description = clean(9294).description
    assert " " not in description
    assert "  " not in description
