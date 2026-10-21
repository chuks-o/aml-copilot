"""Account reads: keyset-paged transactions, bounded counts, counterparty edges.

An account appears on both sides of its transactions, so every query is the UNION ALL of
two index-ordered scans, ``from_account = A`` and ``to_account = A AND from_account <> A``
(the ``<>`` keeps self-transfers from appearing twice). Each half walks its own index,
``(from_account, ts, id)`` or ``(to_account, ts, id)``, from the cursor position and reads at
most ``limit`` entries, so a page costs the same at any depth. A single ``OR`` query would
make Postgres gather every row of the account and sort them, on every page.
Rationale: docs/decisions/0024-account-pagination.md.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import Connection, text

from aml.api.pagination import Position
from aml.api.schemas import (
    CounterpartyEdge,
    Direction,
    EdgeDirection,
    Money,
    PaymentFormat,
    Transaction,
)

EXACT_COUNT_LIMIT = 10_000  # above this, totals are the planner's estimate

_COLUMNS = (
    "id, ts, from_account, to_account, amount_paid, currency_paid, amount_received, "
    "currency_received, payment_format"
)


@dataclass(frozen=True)
class Window:
    """[start, end) in UTC; None means unbounded on that side."""

    start: datetime | None = None
    end: datetime | None = None


@dataclass(frozen=True)
class Count:
    total: int
    is_estimate: bool


class AccountsRepository(Protocol):
    def exists(self, account_id: str) -> bool: ...

    def transactions(
        self, account_id: str, window: Window, after: Position | None, limit: int
    ) -> list[Transaction]:
        """Up to ``limit`` transactions after ``after`` in (ts, id) order."""
        ...

    def count(self, account_id: str, window: Window) -> Count: ...

    def counterparties(
        self, account_id: str, window: Window, limit: int
    ) -> tuple[list[CounterpartyEdge], int]:
        """The top ``limit`` edges, and how many edges there are in total."""
        ...


def money_text(amount: Decimal) -> str:
    """numeric(26,8) as a Money amount: trailing zeros trimmed, but never below 2 decimals."""
    whole, _, fraction = format(amount, "f").partition(".")
    return f"{whole}.{fraction.rstrip('0').ljust(2, '0')}"


def _window_sql(window: Window, params: dict[str, Any]) -> str:
    clauses = []
    if window.start is not None:
        clauses.append("ts >= :start")
        params["start"] = window.start
    if window.end is not None:
        clauses.append("ts < :end")
        params["end"] = window.end
    return "".join(f" AND {c}" for c in clauses)


def _both_sides(select: str, where: str, tail: str) -> str:
    """The account's rows as two halves, each able to use its own (side, ts, id) index."""
    return (
        f"({select} FROM transactions WHERE from_account = :account{where}{tail}) "
        f"UNION ALL "
        f"({select} FROM transactions "
        f"WHERE to_account = :account AND from_account <> :account{where}{tail})"
    )


def transactions_query(
    account_id: str, window: Window, after: Position | None, limit: int
) -> tuple[str, dict[str, Any]]:
    """The page query and its parameters (also EXPLAINed by scripts/bench_pagination.py)."""
    params: dict[str, Any] = {"account": account_id, "limit": limit}
    where = _window_sql(window, params)
    if after is not None:
        where += " AND (ts, id) > (:after_ts, :after_id)"
        params |= {"after_ts": after.ts, "after_id": after.id}
    sql = (
        _both_sides(f"SELECT {_COLUMNS}", where, " ORDER BY ts, id LIMIT :limit")
        + " ORDER BY ts, id LIMIT :limit"
    )
    return sql, params


class SqlAccountsRepository:
    def __init__(self, connection: Connection) -> None:
        self._db = connection

    def exists(self, account_id: str) -> bool:
        found = self._db.scalar(text("SELECT 1 FROM accounts WHERE id = :id"), {"id": account_id})
        return found is not None

    def transactions(
        self, account_id: str, window: Window, after: Position | None, limit: int
    ) -> list[Transaction]:
        sql, params = transactions_query(account_id, window, after, limit)
        rows = self._db.execute(text(sql), params)
        return [_transaction(row._mapping, account_id) for row in rows]

    def count(self, account_id: str, window: Window) -> Count:
        params: dict[str, Any] = {"account": account_id, "cap": EXACT_COUNT_LIMIT + 1}
        where = _window_sql(window, params)
        bounded = _both_sides("SELECT 1", where, " LIMIT :cap")
        exact = self._db.scalar(text(f"SELECT count(*) FROM ({bounded}) AS t"), params) or 0
        if exact <= EXACT_COUNT_LIMIT:
            return Count(total=exact, is_estimate=False)
        # Too many to count on every page: use the planner's estimate of the full set.
        plan = self._db.scalar(
            text(f"EXPLAIN (FORMAT JSON) {_both_sides('SELECT 1', where, '')}"), params
        )
        estimated = int(plan[0]["Plan"]["Plan Rows"])  # psycopg decodes the JSON plan
        return Count(total=max(estimated, EXACT_COUNT_LIMIT + 1), is_estimate=True)

    def counterparties(
        self, account_id: str, window: Window, limit: int
    ) -> tuple[list[CounterpartyEdge], int]:
        params: dict[str, Any] = {"account": account_id, "limit": limit}
        where = _window_sql(window, params)
        sql = f"""
            WITH edges AS (
                SELECT to_account AS counterparty_id, 'OUT' AS direction,
                       currency_paid AS currency, amount_paid AS amount, ts
                FROM transactions
                WHERE from_account = :account AND to_account <> :account{where}
                UNION ALL
                SELECT from_account, 'IN', currency_received, amount_received, ts
                FROM transactions
                WHERE to_account = :account AND from_account <> :account{where}
            )
            SELECT counterparty_id, direction, currency, count(*) AS transaction_count,
                   sum(amount) AS total, min(ts) AS first_ts, max(ts) AS last_ts,
                   count(*) OVER () AS total_edges
            FROM edges
            GROUP BY counterparty_id, direction, currency
            ORDER BY transaction_count DESC, counterparty_id, direction, currency
            LIMIT :limit
        """
        rows = self._db.execute(text(sql), params).all()
        edges = [
            CounterpartyEdge(
                counterparty_id=row.counterparty_id,
                direction=EdgeDirection(row.direction),
                transaction_count=row.transaction_count,
                total=Money(amount=money_text(row.total), currency=row.currency),
                first_ts=row.first_ts,
                last_ts=row.last_ts,
            )
            for row in rows
        ]
        return edges, (rows[0].total_edges if rows else 0)


def _transaction(row: Any, account_id: str) -> Transaction:
    if row["from_account"] == row["to_account"]:
        direction = Direction.SELF
    elif row["from_account"] == account_id:
        direction = Direction.OUT
    else:
        direction = Direction.IN
    return Transaction(
        id=row["id"],
        ts=row["ts"],
        from_account_id=row["from_account"],
        to_account_id=row["to_account"],
        direction=direction,
        amount_paid=Money(amount=money_text(row["amount_paid"]), currency=row["currency_paid"]),
        amount_received=Money(
            amount=money_text(row["amount_received"]), currency=row["currency_received"]
        ),
        payment_format=PaymentFormat(row["payment_format"]),
    )
