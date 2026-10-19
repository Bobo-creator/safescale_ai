import logging

import psycopg
import pytest
from fake_embedder import FakeEmbedder
from fake_explainer import ExplainerError, ScriptedExplainer, grounded_draft
from fastapi.testclient import TestClient

from safescale.analysis.report import DISCLAIMER
from safescale.analysis.terms import refresh_term_stats
from safescale.api import deps
from safescale.api.app import DAILY_LIMIT_NOTICE, MODEL_ERROR_MESSAGE, app
from safescale.api.limits import Limits
from safescale.retrieval.index import embed_recalls
from safescale.taxonomy.store import classify_all

QUERY = "lithium-ion battery pack overheating fire"
SECRET_QUERY = "Confidential prototype: lithium-ion battery pack with overheating fire risk"


@pytest.fixture
def ready(fixture_recalls):
    classify_all(fixture_recalls)
    refresh_term_stats(fixture_recalls)
    embed_recalls(fixture_recalls, FakeEmbedder())
    return fixture_recalls


@pytest.fixture
def client(ready):
    explainers = []

    def conn():
        yield ready

    def explainer():
        e = ScriptedExplainer(*([grounded_draft] * 20))
        explainers.append(e)
        return e

    app.dependency_overrides.update(
        {
            deps.get_conn: conn,
            deps.get_embedder: FakeEmbedder,
            deps.get_explainer: explainer,
            deps.get_relevance_floor: lambda: 0.0,
            deps.get_limits: lambda: Limits(),
            deps.get_salt: lambda: "test-salt",
        }
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        c.explainers = explainers
        yield c
    app.dependency_overrides.clear()


def test_analyze_returns_the_report(client):
    r = client.post("/api/analyze", json={"query": QUERY, "k": 25, "method": "hybrid"})
    assert r.status_code == 200
    data = r.json()
    assert data["k"] == 25 and data["method"] == "hybrid" and data["disclaimer"] == DISCLAIMER
    assert data["matches"] and data["overall_signal"] in {"LOW", "MODERATE", "HIGH"}


def test_explain_returns_report_and_validated_explanation(client):
    r = client.post("/api/explain", json={"query": QUERY})
    assert r.status_code == 200
    data = r.json()
    assert data["notice"] is None and data["report"]["query"] == QUERY
    exp = data["explanation"]
    assert exp["generated"] and exp["summary"][0]["citations"] and exp["disclaimer"] == DISCLAIMER


@pytest.mark.parametrize(
    "body",
    [
        {"query": "too short"},
        {"query": "x" * 1001},
        {"query": "   " + "a" * 5 + "   "},
        {"query": QUERY, "k": 10},
        {"query": QUERY, "method": "bm25"},
        {"query": QUERY, "extra": True},
        {},
    ],
)
def test_bad_input_is_a_422(client, body):
    assert client.post("/api/analyze", json=body).status_code == 422


def test_query_is_trimmed(client):
    r = client.post("/api/analyze", json={"query": f"   {QUERY}   "})
    assert r.status_code == 200 and r.json()["query"] == QUERY


def test_analysis_rate_limit_gives_429_with_retry_after(client):
    app.dependency_overrides[deps.get_limits] = lambda: Limits(analyses_per_hour=2)
    codes = [client.post("/api/analyze", json={"query": QUERY}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    r = client.post("/api/analyze", json={"query": QUERY})
    assert int(r.headers["Retry-After"]) > 0 and "Try again in" in r.json()["detail"]


@pytest.fixture
def on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")


def test_visitors_are_limited_separately(client, on_vercel):
    app.dependency_overrides[deps.get_limits] = lambda: Limits(analyses_per_hour=1)
    a = {"x-forwarded-for": "203.0.113.1, 10.0.0.1"}
    b = {"x-forwarded-for": "203.0.113.2"}
    assert client.post("/api/analyze", json={"query": QUERY}, headers=a).status_code == 200
    assert client.post("/api/analyze", json={"query": QUERY}, headers=a).status_code == 429
    assert client.post("/api/analyze", json={"query": QUERY}, headers=b).status_code == 200


def test_forged_forwarded_for_is_ignored_outside_vercel(client, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    app.dependency_overrides[deps.get_limits] = lambda: Limits(analyses_per_hour=1)
    codes = [
        client.post(
            "/api/analyze", json={"query": QUERY}, headers={"x-forwarded-for": f"10.0.0.{i}"}
        ).status_code
        for i in range(3)
    ]
    assert codes == [200, 429, 429]  # a new fake IP per request doesn't buy a new bucket


def test_vercel_header_is_preferred_on_vercel(client, on_vercel):
    from safescale.api.app import client_ip

    class Req:
        headers = {"x-vercel-forwarded-for": "203.0.113.5", "x-forwarded-for": "198.51.100.1"}
        client = None

    assert client_ip(Req()) == "203.0.113.5"


def test_explanation_limits(client, on_vercel):
    app.dependency_overrides[deps.get_limits] = lambda: Limits(
        explanations_per_hour=1, explanations_per_day=1
    )
    first = client.post(
        "/api/explain", json={"query": QUERY}, headers={"x-forwarded-for": "1.1.1.1"}
    )
    assert first.status_code == 200 and first.json()["explanation"]
    again = client.post(
        "/api/explain", json={"query": QUERY}, headers={"x-forwarded-for": "1.1.1.1"}
    )
    assert again.status_code == 429
    other = client.post(
        "/api/explain", json={"query": QUERY}, headers={"x-forwarded-for": "2.2.2.2"}
    )
    assert other.status_code == 200  # daily cap reached: the analysis still comes back
    assert other.json()["explanation"] is None and other.json()["notice"] == DAILY_LIMIT_NOTICE
    assert other.json()["report"]["matches"]


def test_rate_limit_table_holds_no_ips_or_descriptions(client, ready, on_vercel):
    client.post(
        "/api/explain", json={"query": SECRET_QUERY}, headers={"x-forwarded-for": "198.51.100.9"}
    )
    rows = " ".join(str(r) for r in ready.execute("select * from app_rate_limits").fetchall())
    assert "198.51.100.9" not in rows and "Confidential" not in rows


def test_openai_failure_still_returns_report_and_fallback(client):
    app.dependency_overrides[deps.get_explainer] = lambda: ScriptedExplainer(
        ExplainerError("upstream timeout")
    )
    data = client.post("/api/explain", json={"query": QUERY}).json()
    assert data["report"]["matches"] and data["explanation"]["summary"]
    assert data["explanation"]["generated"] is False
    # The upstream error text never reaches the browser.
    assert data["explanation"]["validation"]["error"] == MODEL_ERROR_MESSAGE
    assert "upstream timeout" not in str(data)


def test_database_failure_is_a_503_without_details(client):
    def broken():
        raise psycopg.OperationalError("connection to server at 10.1.2.3 failed: secret")
        yield  # pragma: no cover

    app.dependency_overrides[deps.get_conn] = broken
    r = client.post("/api/analyze", json={"query": QUERY})
    assert r.status_code == 503 and "10.1.2.3" not in r.text and "secret" not in r.text


def test_unexpected_error_is_a_generic_500(client):
    app.dependency_overrides[deps.get_embedder] = lambda: None  # breaks inside analyze()
    r = client.post("/api/analyze", json={"query": QUERY})
    assert r.status_code == 500 and r.json() == {"detail": "Something went wrong on our side."}


def test_descriptions_never_reach_the_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    client.post("/api/analyze", json={"query": SECRET_QUERY})
    client.post("/api/explain", json={"query": SECRET_QUERY})
    app.dependency_overrides[deps.get_embedder] = lambda: None
    client.post("/api/analyze", json={"query": SECRET_QUERY})  # error path logs too
    assert "Confidential" not in caplog.text


def test_health(client):
    health = client.get("/api/health").json()
    assert health["ok"] is True and health["db_ms"] >= 0 and health["pruned"] == 0


def test_api_docs_are_off_on_vercel(monkeypatch):
    import importlib

    import safescale.api.app as module

    monkeypatch.setenv("VERCEL", "1")
    prod = importlib.reload(module)
    try:
        with TestClient(prod.app) as c:
            assert c.get("/api/docs").status_code == 404
            assert c.get("/api/openapi.json").status_code == 404
    finally:
        monkeypatch.delenv("VERCEL")
        importlib.reload(module)
