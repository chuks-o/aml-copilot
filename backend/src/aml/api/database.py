"""The API's database engine and per-request connections.

Synchronous SQLAlchemy Core in plain ``def`` routes (FastAPI runs them in a thread pool):
each request is one or two indexed queries, so async adds machinery without a payoff yet
(docs/decisions/0024-account-pagination.md). The engine is created lazily, on first use, so
importing the app never connects.
"""

from collections.abc import Iterator
from functools import cache

from sqlalchemy import Connection, Engine, create_engine

from aml.common import get_settings


@cache
def engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def reset() -> None:
    """Forget the engine (tests that point settings at another database call this)."""
    if engine.cache_info().currsize:
        engine().dispose()
    engine.cache_clear()


def connection() -> Iterator[Connection]:
    """FastAPI dependency: one connection per request, returned to the pool afterwards."""
    with engine().connect() as conn:
        yield conn
