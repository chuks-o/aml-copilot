"""What a write route needs, on one connection: a transaction, the idempotency store, repos.

Routes depend on the ``UnitOfWork`` protocol; tests without a database override
``unit_of_work`` with an in-memory one (tests/fixtures/fakes.py).
Rationale: docs/decisions/0025-idempotency.md.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Annotated, Protocol

from fastapi import Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import Connection

from aml.api.database import connection
from aml.api.idempotency import (
    IdempotencyStore,
    InProgressError,
    KeyReusedError,
    SqlIdempotencyStore,
    StoredResponse,
    fingerprint,
)
from aml.api.problems import ProblemError
from aml.api.repositories.alerts import AlertsRepository, SqlAlertsRepository


class UnitOfWork(Protocol):
    idempotency: IdempotencyStore
    alerts: AlertsRepository

    def transaction(self) -> AbstractContextManager[object]:
        """Commit on success, roll back on any exception (the idempotency claim with it)."""
        ...


class SqlUnitOfWork:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self.idempotency: IdempotencyStore = SqlIdempotencyStore(conn)
        self.alerts: AlertsRepository = SqlAlertsRepository(conn)

    def transaction(self) -> AbstractContextManager[object]:
        return self._conn.begin()


def unit_of_work(conn: Annotated[Connection, Depends(connection)]) -> UnitOfWork:
    return SqlUnitOfWork(conn)


Work = Annotated[UnitOfWork, Depends(unit_of_work)]


def idempotent(
    work: UnitOfWork,
    key: str,
    request: Request,
    body: BaseModel,
    write: Callable[[], StoredResponse],
) -> Response:
    """Run ``write`` once per Idempotency-Key, in one transaction with the key's record.

    A repeated key with the same request replays the stored response; with a different request
    it is 422; while the first request still holds the key after LOCK_TIMEOUT, it is 409.
    """
    request_hash = fingerprint(request.method, request.url.path, body.model_dump())
    try:
        with work.transaction():
            replay = work.idempotency.claim(key, request_hash)
            if replay is not None:
                return replay.response()
            stored = write()
            work.idempotency.complete(key, stored)
    except KeyReusedError as exc:
        raise ProblemError(
            422, "This Idempotency-Key was already used for a different request."
        ) from exc
    except InProgressError as exc:
        raise ProblemError(
            409, "A request with this Idempotency-Key is still in progress; retry shortly."
        ) from exc
    return stored.response()
