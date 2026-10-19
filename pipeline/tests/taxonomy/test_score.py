import pytest

from safescale.cli import main
from safescale.taxonomy.labeling.gold import GoldItem, GoldSet, save_gold
from safescale.taxonomy.score import Counts, format_score, score


def _item(recall_id, hazard_text, labels, violates=False):
    return GoldItem(
        recall_id,
        "Title",
        hazard_text,
        None,
        f"https://x/{recall_id}",
        None,
        labels=labels,
        violates_standard=violates,
    )


@pytest.fixture
def gold():
    items = [
        _item(1, "The heater can overheat, posing a fire hazard.", ["fire_overheating"]),
        # classifier says fire + burn; human says burn only -> one false positive
        _item(2, "Posing fire and burn hazards.", ["burn"]),
        # classifier says fall; human adds entrapment -> one false negative
        _item(3, "The chair can tip over.", ["fall", "entrapment"]),
        _item(4, "The paint violates the federal lead paint standard.", ["poisoning"], True),
        _item(5, "Not labeled yet.", []),
    ]
    return GoldSet(seed=1, items=items, created_at="2026-10-19T00:00:00+00:00")


def test_counts_metrics():
    c = Counts(tp=3, fp=1, fn=2)
    assert c.precision == 0.75 and c.recall == 0.6
    assert c.f1 == pytest.approx(2 * 0.75 * 0.6 / 1.35)
    assert Counts().precision is None and Counts().f1 is None


def test_score_counts_per_category_and_micro(gold):
    s = score(gold)
    assert (s.scored, s.skipped) == (4, 1)
    assert s.per_category["fire_overheating"] == Counts(tp=1, fp=1, fn=0)
    assert s.per_category["burn"] == Counts(tp=1, fp=0, fn=0)
    assert s.per_category["entrapment"] == Counts(tp=0, fp=0, fn=1)
    assert s.micro == Counts(tp=4, fp=1, fn=1)
    assert s.exact_match == 2
    assert s.violation == Counts(tp=1, fp=0, fn=0)
    assert [(m.recall_id, m.missed, m.extra) for m in s.mismatches] == [
        (2, [], ["fire_overheating"]),
        (3, ["entrapment"], []),
    ]


def test_format_score_mentions_everything(gold):
    text = format_score(score(gold))
    assert "scored 4 labeled recalls (1 not labeled yet)" in text
    assert "micro (all labels)" in text and "exact match (whole label set): 2/4" in text
    assert "3: missed entrapment / extra -" in text


def test_cli_score_hazards(gold, tmp_path, capsys):
    path = tmp_path / "gold.json"
    assert main(["score-hazards", "--gold", str(path)]) == 1
    save_gold(gold, path)
    assert main(["score-hazards", "--gold", str(path)]) == 0
    assert "micro (all labels)" in capsys.readouterr().out
