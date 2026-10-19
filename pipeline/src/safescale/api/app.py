"""FastAPI app for the dashboard: /api/analyze, /api/explain, /api/examples, /api/health.

Request bodies (product descriptions) are never logged or stored.
"""

import logging
import os
import time
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from safescale.analysis.analyze import analyze
from safescale.api import deps
from safescale.api.limits import Decision, Limits, check_analysis, check_explanation, prune
from safescale.api.limits import visitor_key as hash_visitor
from safescale.explain.explain import explain
from safescale.explain.explainer import Explainer
from safescale.retrieval.embedder import Embedder

log = logging.getLogger(__name__)

EXAMPLES = [
    {
        "label": "Children's night light",
        "text": "Rechargeable children's night light using a "
        "2000 mAh lithium-ion battery, USB-C charging, ABS plastic housing, and LED lighting.",
    },
    {
        "label": "Baby crib",
        "text": "Wooden baby crib with adjustable mattress height and a drop-down side rail.",
    },
    {
        "label": "Child's dresser",
        "text": "Six-drawer wooden dresser for a child's bedroom, 48 inches tall.",
    },
    {
        "label": "Folding e-bike",
        "text": "Folding electric bicycle with a 48 V lithium battery "
        "pack and hydraulic disc brakes.",
    },
    {
        "label": "Space heater",
        "text": "Electric space heater, 1500 W ceramic element, tip-over switch, for bedrooms.",
    },
    {
        "label": "Magnetic tiles",
        "text": "Magnetic building tiles toy set for ages 3 and up, with small neodymium magnets.",
    },
]
DAILY_LIMIT_NOTICE = (
    "Today's limit for explanations has been reached. The hazard analysis above is complete; "
    "please come back tomorrow for the written explanation."
)

ON_VERCEL = bool(os.environ.get("VERCEL"))
MODEL_ERROR_MESSAGE = (
    "The explanation model was unavailable; showing a summary built from the data."
)

# Interactive API docs only outside production.
app = FastAPI(
    title="SafeScale AI",
    docs_url=None if ON_VERCEL else "/api/docs",
    redoc_url=None,
    openapi_url=None if ON_VERCEL else "/api/openapi.json",
)

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Query
    k: Literal[25, 50, 100] = 25
    method: Literal["vector", "keyword", "hybrid"] = "vector"


class TooManyRequests(Exception):
    def __init__(self, decision: Decision, what: str):
        self.decision, self.what = decision, what


@app.exception_handler(TooManyRequests)
def _too_many(_: Request, exc: TooManyRequests) -> JSONResponse:
    minutes = max(1, round(exc.decision.retry_after / 60))
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(exc.decision.retry_after)},
        content={
            "detail": f"Too many {exc.what} from your network. Try again in {minutes} minute(s).",
            "retry_after": exc.decision.retry_after,
        },
    )


@app.exception_handler(psycopg.OperationalError)
def _db_down(_: Request, exc: psycopg.OperationalError) -> JSONResponse:
    log.error("database unavailable: %s", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "30"},
        content={
            "detail": "The recall database is unavailable right now. Please try again in a minute."
        },
    )


@app.exception_handler(Exception)
def _unexpected(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side."})


def client_ip(request: Request) -> str:
    """The client's IP address, from a source the client can't forge.

    On Vercel the platform overwrites X-Forwarded-For (and sets x-vercel-forwarded-for) with the
    real client IP, so those headers are trusted there only. Anywhere else they are ignored and the
    socket's peer address is used, so a client can't pick a fresh rate-limit bucket per request.
    """
    if deps.trust_proxy_headers():
        for header in ("x-vercel-forwarded-for", "x-forwarded-for", "x-real-ip"):
            value = request.headers.get(header, "").split(",")[0].strip()
            if value:
                return value
    return request.client.host if request.client else "unknown"


def visitor(request: Request, salt: Annotated[str, Depends(deps.get_salt)]) -> str:
    """Salted hash of the client IP; the IP itself is never stored."""
    return hash_visitor(client_ip(request), salt)


Conn = Annotated[psycopg.Connection, Depends(deps.get_conn)]
EmbedderDep = Annotated[Embedder, Depends(deps.get_embedder)]
ExplainerDep = Annotated[Explainer, Depends(deps.get_explainer)]
LimitsDep = Annotated[Limits, Depends(deps.get_limits)]
Visitor = Annotated[str, Depends(visitor)]
Floor = Annotated[float, Depends(deps.get_relevance_floor)]


@app.post("/api/analyze")
def post_analyze(
    body: AnalyzeRequest,
    conn: Conn,
    embedder: EmbedderDep,
    limits: LimitsDep,
    who: Visitor,
    floor: Floor,
) -> dict:
    decision = check_analysis(conn, who, limits)
    if not decision.allowed:
        raise TooManyRequests(decision, "analyses")
    report = analyze(
        conn, body.query, embedder=embedder, k=body.k, method=body.method, relevance_floor=floor
    )
    return report.to_dict()


@app.post("/api/explain")
def post_explain(
    body: AnalyzeRequest,
    conn: Conn,
    embedder: EmbedderDep,
    explainer: ExplainerDep,
    limits: LimitsDep,
    who: Visitor,
    floor: Floor,
) -> dict:
    mine, everyone = check_explanation(conn, who, limits)
    if not mine.allowed:
        raise TooManyRequests(mine, "explanations")
    # Recomputed here so the explanation is always grounded in a report the server built.
    report = analyze(
        conn, body.query, embedder=embedder, k=body.k, method=body.method, relevance_floor=floor
    )
    if not everyone.allowed:
        return {"report": report.to_dict(), "explanation": None, "notice": DAILY_LIMIT_NOTICE}
    explanation = explain(conn, report, explainer=explainer).to_dict()
    if explanation["validation"]["error"]:
        # Upstream error text can include request details; it stays in the server log.
        explanation["validation"]["error"] = MODEL_ERROR_MESSAGE
    return {"report": report.to_dict(), "explanation": explanation, "notice": None}


@app.get("/api/examples")
def get_examples() -> list[dict]:
    return EXAMPLES


@app.get("/api/health")
def get_health(conn: Conn) -> dict:
    """Database round trip; also the daily keep-alive (Vercel cron) and limit-table cleanup."""
    started = time.perf_counter()
    conn.execute("select 1").fetchone()
    db_ms = round(1000 * (time.perf_counter() - started), 1)
    pruned = prune(conn)
    return {"ok": True, "db_ms": db_ms, "pruned": pruned}
