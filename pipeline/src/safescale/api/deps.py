"""Shared resources for the API: a small connection pool and the model clients.

Each is created lazily once per process (a warm serverless instance reuses them) and can be
replaced in tests through FastAPI's dependency_overrides.
"""

import logging
import os
import secrets
from collections.abc import Iterator
from functools import cache

import psycopg
from psycopg_pool import ConnectionPool

from safescale import config
from safescale.analysis.report import RELEVANCE_FLOOR
from safescale.api.limits import Limits
from safescale.explain.explainer import Explainer, OpenAIExplainer
from safescale.retrieval.embedder import Embedder, OpenAIEmbedder

log = logging.getLogger(__name__)


def database_url() -> str:
    """The app role's URL in production; the pipeline's URL for local development."""
    config.load_dotenv()
    return os.environ.get("APP_DATABASE_URL") or config.database_url()


@cache
def pool() -> ConnectionPool:
    # prepare_threshold=None: Supabase's transaction pooler can't keep prepared statements.
    return ConnectionPool(
        database_url(),
        min_size=0,
        max_size=int(os.environ.get("DB_POOL_SIZE", "4")),
        kwargs={"prepare_threshold": None},
        open=True,
        check=ConnectionPool.check_connection,
    )


def get_conn() -> Iterator[psycopg.Connection]:
    with pool().connection() as conn:
        yield conn


@cache
def get_embedder() -> Embedder:
    return OpenAIEmbedder()


@cache
def get_explainer() -> Explainer:
    return OpenAIExplainer()


def get_relevance_floor() -> float:
    return RELEVANCE_FLOOR  # overridden in tests, where the fake embedder scores lower


@cache
def get_limits() -> Limits:
    return Limits.from_env()


@cache
def get_salt() -> str:
    salt = os.environ.get("RATE_LIMIT_SALT")
    if not salt:
        log.warning("RATE_LIMIT_SALT is not set; using a per-process random salt")
        salt = secrets.token_hex(16)
    return salt
