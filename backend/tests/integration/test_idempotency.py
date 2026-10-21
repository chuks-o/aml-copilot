"""Idempotency-Key against real Postgres (scratch database): replay, reuse, concurrency, expiry."""

import json
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from aml.api import database, idempotency
from aml.api.app import app
from aml.api.repositories.alerts import SqlAlertsRepository
from aml.api.schemas import Alert, AlertCreate
from aml.db import alembic_config
from tests.fixtures.postgres import MIGRATIONS

ACCOUNT, OTHER = "10:A00000001", "20:B00000002"
TS = datetime(2022, 9, 1, 0, 20, tzinfo=UTC)
ALERT = {
    "account_id": ACCOUNT,
    "score": 0.93,
    "typology": "FAN_IN",
    "reason": "Received from 14 accounts within 6 hours.",
    "transaction_ids": [1, 2],
    "model_version": "gbm-2026-10-01",
}


@pytest.fixture
def api(scratch_database: Engine) -> Iterator[TestClient]:
    command.upgrade(alembic_config(MIGRATIONS), "head")
    database.reset()
    with scratch_database.begin() as connection:
        for account in (ACCOUNT, OTHER):
            bank, number = account.split(":")
            connection.execute(
                text(
                    "insert into accounts (id, bank_id, account_number, entity_type) "
                    "values (:id, :bank, :number, 'CORPORATION')"
                ),
                {"id": account, "bank": bank, "number": number},
            )
        connection.execute(
            text(
                "insert into transactions values "
                "(1, :ts, :a, :b, 5, 'USD', 5, 'USD', 'WIRE', false, null), "
                "(2, :ts + interval '1 hour', :b, :a, 7, 'USD', 7, 'USD', 'WIRE', false, null), "
                "(3, :ts, :b, :b, 9, 'USD', 9, 'USD', 'WIRE', false, null)"
            ),
            {"ts": TS, "a": ACCOUNT, "b": OTHER},
        )
    yield TestClient(app)
    database.reset()


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return int(connection.scalar(text(f"select count(*) from {table}")) or 0)  # noqa: S608


def _post(client: TestClient, key: str, body: dict[str, Any]) -> httpx2.Response:
    return client.post("/alerts", json=body, headers={"Idempotency-Key": key})


def test_a_duplicate_post_replays_the_response_and_creates_one_row(
    api: TestClient, scratch_database: Engine
) -> None:
    first = _post(api, "key-1", ALERT)
    second = _post(api, "key-1", ALERT)

    assert first.status_code == second.status_code == 201
    assert first.content == second.content  # byte for byte
    assert first.headers["location"] == second.headers["location"]
    assert _count(scratch_database, "alerts") == 1
    assert _count(scratch_database, "idempotency_keys") == 1
    stored = api.get(first.headers["location"])
    assert (stored.status_code, stored.json()) == (200, first.json())


def test_key_order_and_whitespace_are_the_same_request(api: TestClient) -> None:
    first = _post(api, "key-1", ALERT)
    # Same request: keys reversed, ids reversed (a set), indented.
    same = {k: ALERT[k] for k in reversed(list(ALERT))} | {"transaction_ids": [2, 1]}
    reordered = api.post(
        "/alerts",
        content=json.dumps(same, indent=2),
        headers={"Idempotency-Key": "key-1", "content-type": "application/json"},
    )

    assert reordered.status_code == 201
    assert reordered.content == first.content


def test_the_same_key_with_a_different_body_is_422(
    api: TestClient, scratch_database: Engine
) -> None:
    _post(api, "key-1", ALERT)
    other = _post(api, "key-1", ALERT | {"score": 0.5})

    assert (other.status_code, other.headers["content-type"]) == (422, "application/problem+json")
    assert "different request" in other.json()["detail"]
    assert _count(scratch_database, "alerts") == 1


def test_two_concurrent_identical_requests_create_one_row(
    api: TestClient, scratch_database: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Hold the first request's transaction open after its insert, so the second provably
    # arrives while the key is claimed and has to wait on the row lock.
    original = SqlAlertsRepository.create
    first_inserted = threading.Event()

    def slow_create(self: SqlAlertsRepository, alert: AlertCreate, key: str) -> Alert:
        created = original(self, alert, key)
        if not first_inserted.is_set():
            first_inserted.set()
            time.sleep(1.0)
        return created

    monkeypatch.setattr(SqlAlertsRepository, "create", slow_create)
    responses: dict[str, httpx2.Response] = {}
    elapsed: dict[str, float] = {}

    def send(name: str) -> None:
        start = time.monotonic()
        with TestClient(app) as client:
            responses[name] = _post(client, "key-1", ALERT)
        elapsed[name] = time.monotonic() - start

    first = threading.Thread(target=send, args=("first",))
    first.start()
    assert first_inserted.wait(timeout=10)
    second = threading.Thread(target=send, args=("second",))
    second.start()
    first.join()
    second.join()

    assert responses["first"].status_code == responses["second"].status_code == 201
    assert responses["first"].content == responses["second"].content
    assert _count(scratch_database, "alerts") == 1
    assert elapsed["second"] > 0.5, "the second request should have waited for the first"


def test_a_duplicate_still_waiting_after_the_lock_timeout_is_409(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(idempotency, "LOCK_TIMEOUT", "200ms")
    original = SqlAlertsRepository.create
    first_inserted = threading.Event()

    def slow_create(self: SqlAlertsRepository, alert: AlertCreate, key: str) -> Alert:
        created = original(self, alert, key)
        if not first_inserted.is_set():
            first_inserted.set()
            time.sleep(1.5)
        return created

    monkeypatch.setattr(SqlAlertsRepository, "create", slow_create)
    responses: dict[str, httpx2.Response] = {}

    def send(name: str) -> None:
        with TestClient(app) as client:
            responses[name] = _post(client, "key-1", ALERT)

    first = threading.Thread(target=send, args=("first",))
    first.start()
    assert first_inserted.wait(timeout=10)
    send("second")
    first.join()

    assert responses["first"].status_code == 201
    assert (responses["second"].status_code, responses["second"].json()["status"]) == (409, 409)
    assert "still in progress" in responses["second"].json()["detail"]


def test_a_failed_write_is_not_stored_so_a_retry_runs_again(
    api: TestClient, scratch_database: Engine
) -> None:
    unknown = _post(api, "key-1", ALERT | {"transaction_ids": [1, 999]})
    not_involved = _post(api, "key-2", ALERT | {"transaction_ids": [3]})
    retried = _post(api, "key-1", ALERT | {"transaction_ids": [1, 999]})

    assert unknown.status_code == 422
    assert unknown.json()["errors"] == [
        {"location": "/body/transaction_ids/1", "message": "unknown transaction"}
    ]
    assert not_involved.json()["errors"][0]["message"] == "does not involve the account"
    assert retried.status_code == 422  # ran again (not replayed, not "key reused")
    assert _count(scratch_database, "idempotency_keys") == 0


def test_an_expired_key_can_be_reused_and_the_sweep_deletes_expired_keys(
    api: TestClient, scratch_database: Engine
) -> None:
    with scratch_database.begin() as connection:
        connection.execute(
            text(
                "insert into idempotency_keys (key, request_hash, response, status_code, "
                "created_at) values "
                "('old', 'other-request', '{}', 201, now() - interval '25 hours'), "
                "('stale', 'x', '{}', 201, now() - interval '25 hours'), "
                "('fresh', 'y', '{}', 201, now())"
            )
        )

    reused = _post(api, "old", ALERT)
    with scratch_database.begin() as connection:
        deleted = idempotency.sweep(connection)

    assert reused.status_code == 201  # not 422: the old key had expired
    assert deleted == 1  # 'stale' only: 'old' was re-armed, 'fresh' is within 24 h
    with scratch_database.connect() as connection:
        keys = set(connection.scalars(text("select key from idempotency_keys")))
    assert keys == {"old", "fresh"}


def test_case_writes_are_idempotent_too(api: TestClient, scratch_database: Engine) -> None:
    body = {"account_id": ACCOUNT, "alert_ids": ["0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b"]}
    headers = {"Idempotency-Key": "case-1"}

    first = api.post("/cases", json=body, headers=headers)
    again = api.post("/cases", json=body, headers=headers)
    reused = api.post("/cases", json=body | {"account_id": OTHER}, headers=headers)

    assert first.status_code == again.status_code == 201
    assert first.content == again.content
    assert first.headers["etag"] == again.headers["etag"]
    assert reused.status_code == 422
    assert _count(scratch_database, "idempotency_keys") == 1
