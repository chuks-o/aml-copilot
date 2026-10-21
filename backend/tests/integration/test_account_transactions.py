"""GET /accounts/{id}/transactions and /counterparties against real Postgres (scratch database).

The key property of keyset pagination: rows inserted while a client pages never cause a
duplicate, and never hide a row that existed when paging started.
"""

import random
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from aml.api import database
from aml.api.app import app
from aml.db import alembic_config
from tests.fixtures.postgres import MIGRATIONS

A, B, C = "10:A00000001", "20:B00000002", "30:C00000003"
START = datetime(2022, 9, 1, tzinfo=UTC)
ORIGINAL = 5_000


@pytest.fixture
def api(scratch_database: Engine) -> Iterator[TestClient]:
    """The app wired to a fresh, migrated scratch database holding three accounts."""
    command.upgrade(alembic_config(MIGRATIONS), "head")
    database.reset()
    with scratch_database.begin() as connection:
        for account in (A, B, C):
            bank, number = account.split(":")
            connection.execute(
                text(
                    "insert into accounts (id, bank_id, account_number, entity_type) "
                    "values (:id, :bank, :number, 'CORPORATION')"
                ),
                {"id": account, "bank": bank, "number": number},
            )
    yield TestClient(app)
    database.reset()


def _insert(engine: Engine, rows: list[dict[str, Any]]) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into transactions (id, ts, from_account, to_account, amount_paid, "
                "currency_paid, amount_received, currency_received, payment_format, "
                "is_laundering) values (coalesce(:id, nextval('transactions_id_seq')), :ts, "
                ":src, :dst, :amount, :currency, :amount, :currency, 'WIRE', false)"
            ),
            rows,
        )


def _row(ts: datetime, src: str, dst: str, row_id: int | None = None, **kw: Any) -> dict[str, Any]:
    return {
        "id": row_id,
        "ts": ts,
        "src": src,
        "dst": dst,
        "amount": "10.00",
        "currency": "USD",
    } | kw


def _original_rows() -> list[dict[str, Any]]:
    """5,000 rows touching A: out to B, in from B, and self-transfers; 3 rows per minute so
    timestamps tie and (ts, id) ordering is exercised."""
    sides = [(A, B), (B, A), (A, A)]
    return [
        _row(START + timedelta(minutes=n // 3), *sides[n % 3], row_id=n + 1)
        for n in range(ORIGINAL)
    ]


def _all_pages(
    api: TestClient, limit: int, pause: float = 0.0, **params: str
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        query = {"limit": str(limit), **params} | ({"cursor": cursor} if cursor else {})
        response = api.get(f"/accounts/{A}/transactions", params=query)
        assert response.status_code == 200, response.text
        page = response.json()
        items += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            return items
        time.sleep(pause)


def test_paging_while_rows_are_inserted_has_no_duplicates_and_no_gaps(
    api: TestClient, scratch_database: Engine
) -> None:
    _insert(scratch_database, _original_rows())
    with scratch_database.begin() as connection:
        connection.execute(text(f"select setval('transactions_id_seq', {ORIGINAL})"))
    window_end = START + timedelta(minutes=ORIGINAL // 3 + 1)
    inserted_at: list[float] = []
    stop = threading.Event()

    def insert_concurrently() -> None:
        rng = random.Random(7)  # noqa: S311  (picks test timestamps, not secrets)
        while not stop.is_set() and len(inserted_at) < 1_000:
            ts = START + timedelta(seconds=rng.randrange(int((window_end - START).total_seconds())))
            _insert(scratch_database, [_row(ts, A, B), _row(ts, C, A)])
            inserted_at.append(time.monotonic())

    inserter = threading.Thread(target=insert_concurrently)
    paging_started = time.monotonic()
    inserter.start()
    items = _all_pages(api, limit=100, pause=0.01, to=window_end.isoformat())
    paging_ended = time.monotonic()
    stop.set()
    inserter.join()

    ids = [item["id"] for item in items]
    keys = [(item["ts"], item["id"]) for item in items]
    assert inserted_at and inserted_at[0] < paging_ended and inserted_at[-1] > paging_started
    assert len(ids) == len(set(ids)), "a row appeared twice"
    assert set(range(1, ORIGINAL + 1)) <= set(ids), "a row that existed at the start was skipped"
    assert keys == sorted(keys), "pages are not in (ts, id) order"
    assert {item["direction"] for item in items[:3]} == {"OUT", "IN", "SELF"}


def test_a_cursor_reused_with_another_window_is_rejected(
    api: TestClient, scratch_database: Engine
) -> None:
    _insert(scratch_database, _original_rows()[:300])
    first = api.get(f"/accounts/{A}/transactions", params={"limit": "100"}).json()

    reused = api.get(
        f"/accounts/{A}/transactions",
        params={"cursor": first["next_cursor"], "from": START.isoformat()},
    )
    malformed = api.get(f"/accounts/{A}/transactions", params={"cursor": "bm9wZQ"})

    assert (reused.status_code, reused.headers["content-type"]) == (400, "application/problem+json")
    assert "different account or time window" in reused.json()["detail"]
    assert malformed.status_code == 400


def test_limit_defaults_to_100_and_caps_at_500(api: TestClient, scratch_database: Engine) -> None:
    _insert(scratch_database, _original_rows()[:700])

    default = api.get(f"/accounts/{A}/transactions").json()
    too_big = api.get(f"/accounts/{A}/transactions", params={"limit": "501"})

    assert len(default["items"]) == 100
    assert default["total"] == 700
    assert default["total_is_estimate"] is False
    assert too_big.status_code == 422


def test_totals_above_10000_are_estimates_and_say_so(
    api: TestClient, scratch_database: Engine
) -> None:
    with scratch_database.begin() as connection:
        connection.execute(
            text(
                "insert into transactions select n, :start + (n || ' seconds')::interval, :a, :b, "
                "1, 'USD', 1, 'USD', 'WIRE', false from generate_series(1, 12000) n"
            ),
            {"start": START, "a": A, "b": B},
        )
        connection.execute(text("analyze transactions"))

    everything = api.get(f"/accounts/{A}/transactions").json()
    small_window = api.get(
        f"/accounts/{A}/transactions",
        params={"to": (START + timedelta(seconds=500)).isoformat()},
    ).json()

    assert everything["total_is_estimate"] is True
    assert everything["total"] > 10_000
    assert (small_window["total"], small_window["total_is_estimate"]) == (499, False)


def test_unknown_accounts_are_404(api: TestClient) -> None:
    for path in ("transactions", "counterparties?window_hours=24"):
        response = api.get(f"/accounts/99:ABCDEF/{path}")
        assert response.status_code == 404, path


def test_counterparties_aggregate_each_direction_and_currency(
    api: TestClient, scratch_database: Engine
) -> None:
    t = START + timedelta(hours=1)
    _insert(
        scratch_database,
        [
            _row(t, A, B, row_id=1, amount="100.50"),
            _row(t + timedelta(minutes=5), A, B, row_id=2, amount="0.25"),
            _row(t + timedelta(minutes=6), A, B, row_id=3, amount="7.00", currency="EUR"),
            _row(t + timedelta(minutes=7), C, A, row_id=4, amount="3.00"),
            _row(t + timedelta(minutes=8), A, A, row_id=5),  # self-transfer: not an edge
            _row(START - timedelta(days=2), A, C, row_id=6),  # outside the window
        ],
    )
    params = {"window_hours": "24", "as_of": (START + timedelta(days=1)).isoformat()}

    body = api.get(f"/accounts/{A}/counterparties", params=params).json()
    top_one = api.get(f"/accounts/{A}/counterparties", params=params | {"limit": "1"}).json()

    edges = {
        (e["counterparty_id"], e["direction"], e["total"]["currency"]): e for e in body["items"]
    }
    assert set(edges) == {(B, "OUT", "USD"), (B, "OUT", "EUR"), (C, "IN", "USD")}
    usd = edges[(B, "OUT", "USD")]
    assert (usd["transaction_count"], usd["total"]["amount"]) == (2, "100.75")
    assert usd["first_ts"] < usd["last_ts"]
    assert body["total_edges"] == 3
    assert (len(top_one["items"]), top_one["total_edges"]) == (1, 3)
    assert top_one["items"][0]["transaction_count"] == 2
