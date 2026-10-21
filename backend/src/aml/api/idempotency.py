"""Idempotency-Key handling for POST requests (IETF httpapi-idempotency-key draft, 0014).

A write request claims its key in ``idempotency_keys`` in the same transaction as the write,
and stores its response there before committing. So the key and the write commit together or
not at all.

Concurrency: the key is the table's primary key. A second request with the same key, while
the first is uncommitted, waits on that row (Postgres blocks the conflicting insert) and,
once the first commits, replays its stored response. If the first rolls back, the second
proceeds as if it were first. Only if the wait exceeds ``LOCK_TIMEOUT`` does it get 409.

Only 2xx responses are stored: a failed write rolls back, taking the claim with it, so a
retry runs again. Keys expire after ``TTL``. An expired key is re-armed on use, and
``sweep()`` deletes expired rows. Rationale: docs/decisions/0025-idempotency.md.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import Connection, text
from sqlalchemy.exc import OperationalError

TTL = timedelta(hours=24)
LOCK_TIMEOUT = "5s"  # how long a duplicate waits for the first request before 409
REPLAYED_HEADERS = ("Location", "ETag")
_LOCK_NOT_AVAILABLE = "55P03"  # SQLSTATE raised when lock_timeout expires


class KeyReusedError(Exception):
    """Same key, different request: 422."""


class InProgressError(Exception):
    """Same key, first request still running after LOCK_TIMEOUT: 409."""


@dataclass(frozen=True)
class StoredResponse:
    """A response kept as its exact bytes. Not as a JSON object: jsonb re-orders object keys
    (by length, then bytes), so a replay would differ from the original in key order."""

    status_code: int
    content: str  # the serialized JSON body, exactly as first sent
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def of(cls, status_code: int, body: BaseModel, headers: dict[str, str]) -> "StoredResponse":
        return cls(status_code, body.model_dump_json(), headers)

    def response(self) -> Response:
        return Response(
            self.content,
            status_code=self.status_code,
            headers=self.headers,
            media_type="application/json",
        )

    def to_json(self) -> dict[str, Any]:
        return {"content": self.content, "headers": self.headers}


def _canonical(value: Any) -> Any:
    """JSON-ready, order-independent form: dict keys and set members sorted."""
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, set | frozenset):
        return sorted((_canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    if isinstance(value, list | tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, Enum):
        return _canonical(value.value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID | Decimal):
        return str(value)
    return value


def fingerprint(method: str, path: str, body: Any) -> str:
    """What was asked: method, path and the validated body, independent of key order."""
    canonical = {"method": method.upper(), "path": path, "body": _canonical(body)}
    return hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()


class IdempotencyStore(Protocol):
    def claim(self, key: str, request_hash: str) -> StoredResponse | None:
        """None: the key is ours, so go ahead with the write. A response: replay it.

        Raises KeyReusedError or InProgressError.
        """
        ...

    def complete(self, key: str, response: StoredResponse) -> None: ...


class SqlIdempotencyStore:
    """Must be used inside the transaction that performs the write."""

    def __init__(self, connection: Connection) -> None:
        self._db = connection

    def claim(self, key: str, request_hash: str) -> StoredResponse | None:
        self._db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        try:
            claimed = self._db.scalar(
                text(
                    "INSERT INTO idempotency_keys (key, request_hash) VALUES (:key, :hash) "
                    "ON CONFLICT (key) DO UPDATE SET request_hash = EXCLUDED.request_hash, "
                    "response = NULL, status_code = NULL, created_at = now() "
                    # An expired key counts as absent: re-arm it in the same statement.
                    "WHERE idempotency_keys.created_at < now() - :ttl "
                    "RETURNING key"
                ),
                {"key": key, "hash": request_hash, "ttl": TTL},
            )
        except OperationalError as exc:
            if getattr(exc.orig, "sqlstate", None) == _LOCK_NOT_AVAILABLE:
                raise InProgressError(key) from exc
            raise
        if claimed is not None:
            return None
        row = self._db.execute(
            text("SELECT request_hash, status_code, response FROM idempotency_keys WHERE key = :k"),
            {"k": key},
        ).one()
        if row.request_hash != request_hash:
            raise KeyReusedError(key)
        if row.status_code is None:  # committed without a response: shouldn't happen
            raise InProgressError(key)
        return StoredResponse(row.status_code, row.response["content"], row.response["headers"])

    def complete(self, key: str, response: StoredResponse) -> None:
        self._db.execute(
            text(
                "UPDATE idempotency_keys "
                "SET status_code = :status, response = CAST(:response AS jsonb) WHERE key = :key"
            ),
            {
                "key": key,
                "status": response.status_code,
                "response": json.dumps(response.to_json()),
            },
        )


def sweep(connection: Connection) -> int:
    """Delete expired keys (no scheduler yet: run `aml sweep-idempotency-keys`)."""
    result = connection.execute(
        text("DELETE FROM idempotency_keys WHERE created_at < now() - :ttl"), {"ttl": TTL}
    )
    return result.rowcount
