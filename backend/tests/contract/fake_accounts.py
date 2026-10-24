"""In-memory AccountsRepository for the contract test, which has no database (0024).

Every well-formed account id "exists" and has the same 7 transactions, so Schemathesis reaches
the 200 responses; the window, cursor position and limit are honoured like the SQL version.
"""

from datetime import UTC, date, datetime, timedelta

from aml.api.pagination import Position
from aml.api.repositories.accounts import Count, Window
from aml.api.schemas import (
    Account,
    ActivitySummary,
    CounterpartyEdge,
    Direction,
    EdgeDirection,
    EntityType,
    KycProfile,
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

    def get(self, account_id: str) -> Account | None:
        bank_id, account_number = account_id.split(":", 1)
        rows = _rows(account_id)
        return Account(
            id=account_id,
            bank_id=bank_id,
            bank_name="Fake Bank #1",
            account_number=account_number,
            entity_id="800C998A0",
            entity_name="Corporation #33520",
            entity_type=EntityType.CORPORATION,
            activity=ActivitySummary(
                first_seen=rows[0].ts,
                last_seen=rows[-1].ts,
                sent_count=sum(r.direction is Direction.OUT for r in rows),
                received_count=sum(r.direction is Direction.IN for r in rows),
            ),
            kyc=KycProfile(
                country="NG",
                business_type="Construction",
                expected_monthly_volume_band="1000-9999",
                onboarded_at=date(2018, 6, 7),
                synthetic=[
                    "business_type",
                    "country",
                    "expected_monthly_volume_band",
                    "onboarded_at",
                ],
            ),
        )

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
