import pytest
from fake_embedder import FakeEmbedder
from tests_support import TEST_DATABASE_URL

from safescale import cli


@pytest.fixture
def cli_env(fixture_recalls, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(cli, "make_embedder", FakeEmbedder)
    return fixture_recalls


def test_embed_then_search_prints_ranked_results(cli_env, capsys):
    assert cli.main(["embed"]) == 0
    assert "embedded 18 recall(s) with fake-bow" in capsys.readouterr().out

    cli.main(["search", "lithium-ion battery fire", "--k", "3", "--method", "hybrid"])
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("  1. [")
    assert out.count("https://www.cpsc.gov/") == 3


def test_keyword_search_needs_no_embedder(cli_env, capsys, monkeypatch):
    def fail():
        raise AssertionError("keyword search must not build an embedder")

    monkeypatch.setattr(cli, "make_embedder", fail)
    cli.main(["search", "zzzz-no-such-word", "--method", "keyword"])
    assert capsys.readouterr().out.strip() == "no matching recalls"
