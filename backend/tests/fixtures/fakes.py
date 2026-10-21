"""In-memory stand-ins for the write path, for tests without a database (unit, contract).

They follow the SQL versions' rules (claim/replay/reuse, rollback on error) but not their
locking or expiry, which tests/integration covers.
"""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI

from aml.api.app import app
from aml.api.idempotency import IdempotencyStore, KeyReusedError, StoredResponse
from aml.api.repositories.alerts import AlertsRepository
from aml.api.schemas import Alert, AlertCreate, AlertStatus
from aml.api.unit_of_work import unit_of_work


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self.keys: dict[str, tuple[str, StoredResponse | None]] = {}

    def claim(self, key: str, request_hash: str) -> StoredResponse | None:
        if key not in self.keys:
            self.keys[key] = (request_hash, None)
            return None
        stored_hash, response = self.keys[key]
        if stored_hash != request_hash:
            raise KeyReusedError(key)
        return response

    def complete(self, key: str, response: StoredResponse) -> None:
        self.keys[key] = (self.keys[key][0], response)


class MemoryAlertsRepository:
    def __init__(self) -> None:
        self.alerts: dict[UUID, Alert] = {}

    def create(self, alert: AlertCreate, idempotency_key: str) -> Alert:
        created = Alert(
            **alert.model_dump(),
            id=uuid4(),
            status=AlertStatus.OPEN,
            case_id=None,
            created_at=datetime.now(UTC),
        )
        self.alerts[created.id] = created
        return created

    def get(self, alert_id: UUID) -> Alert | None:
        return self.alerts.get(alert_id)


class MemoryUnitOfWork:
    def __init__(self) -> None:
        self._keys = MemoryIdempotencyStore()
        self._alerts = MemoryAlertsRepository()
        self.idempotency: IdempotencyStore = self._keys
        self.alerts: AlertsRepository = self._alerts

    def transaction(self) -> AbstractContextManager[object]:
        @contextmanager
        def scope() -> Iterator[object]:
            # Shallow snapshots are enough: stored values are never mutated, only replaced.
            keys, alerts = dict(self._keys.keys), dict(self._alerts.alerts)
            try:
                yield self
            except BaseException:
                self._keys.keys, self._alerts.alerts = keys, alerts  # roll back
                raise

        return scope()


@contextmanager
def in_memory_writes(app: FastAPI) -> Iterator[MemoryUnitOfWork]:
    """Route every write through one in-memory unit of work while the block runs."""
    work = MemoryUnitOfWork()
    app.dependency_overrides[unit_of_work] = lambda: work
    try:
        yield work
    finally:
        app.dependency_overrides.pop(unit_of_work, None)


@pytest.fixture
def memory_writes() -> Iterator[MemoryUnitOfWork]:
    with in_memory_writes(app) as work:
        yield work
