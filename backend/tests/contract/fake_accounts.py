"""In-memory AccountsRepository for the contract test, which has no database (0024).

Every well-formed account id "exists" and has the same 7 transactions, so Schemathesis reaches
the 200 responses; the window, cursor position and limit are honoured like the SQL version.
"""

from datetime import UTC, datetime, timedelta

from aml.api.pagination import Position
from aml.api.repositories.accounts import Count, Window
from aml.api.schemas import (
    CounterpartyEdge,
    Direction,
    EdgeDirection,
    Money,
    PaymentFormat,
    Transaction,
)

COUNTERPARTY = "37861:80B779D80"
START = datetime(2022, 9, 1, tzinfo=UTC)


def _rows(account_id: str) -> list[Transaction]:
    usd = Money(amount="3697.34", currency="USD")
    rows = []
    for n in range(1, 8):
        outgoing = n % 2 == 1
        rows.append(
            Transaction(
                id=n,
                ts=START + timedelta(hours=n // 2),  # pairs share a timestamp: ties on ts
                from_account_id=account_id if outgoing else COUNTERPARTY,
                to_account_id=COUNTERPARTY if outgoing else account_id,
                direction=Direction.OUT if outgoing else Direction.IN,
                amount_paid=usd,
                amount_received=usd,
                payment_format=PaymentFormat.WIRE,
            )
        )
    return rows


def _in(window: Window, ts: datetime) -> bool:
    return (window.start is None or ts >= window.start) and (window.end is None or ts < window.end)


class FakeAccountsRepository:
    def exists(self, account_id: str) -> bool:
        return True

    def transactions(
        self, account_id: str, window: Window, after: Position | None, limit: int
    ) -> list[Transaction]:
        rows = [r for r in _rows(account_id) if _in(window, r.ts)]
        if after is not None:
            rows = [r for r in rows if (r.ts, r.id) > (after.ts, after.id)]
        return rows[:limit]

    def count(self, account_id: str, window: Window) -> Count:
        return Count(total=sum(_in(window, r.ts) for r in _rows(account_id)), is_estimate=False)

    def counterparties(
        self, account_id: str, window: Window, limit: int
    ) -> tuple[list[CounterpartyEdge], int]:
        edges = []
        for direction in (EdgeDirection.OUT, EdgeDirection.IN):
            rows = [
                r
                for r in _rows(account_id)
                if _in(window, r.ts) and r.direction.value == direction.value
            ]
            if rows:
                edges.append(
                    CounterpartyEdge(
                        counterparty_id=COUNTERPARTY,
                        direction=direction,
                        transaction_count=len(rows),
                        total=Money(amount=f"{3697.34 * len(rows):.2f}", currency="USD"),
                        first_ts=rows[0].ts,
                        last_ts=rows[-1].ts,
                    )
                )
        return edges[:limit], len(edges)
