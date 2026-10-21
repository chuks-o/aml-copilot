"""Benchmark keyset pagination on the deepest history in the seeded dataset.

Run against the `make up` database after `make seed`:  make bench-pagination

The median account has 4 transactions, so only the bank-70 hubs have histories deep enough
to show the difference between keyset and OFFSET. This picks the largest hub, then compares
p95 latency of page 1 with the last page of its full history: by keyset (what the API does)
and, for contrast, by OFFSET. It prints EXPLAIN (ANALYZE, BUFFERS) of the deep keyset page.
Rationale: docs/decisions/0024-account-pagination.md.
"""

import statistics
import time
from collections.abc import Callable

from sqlalchemy import Connection, text

from aml.api.database import engine
from aml.api.pagination import Position
from aml.api.repositories.accounts import SqlAccountsRepository, Window, transactions_query

PAGE = 100
RUNS = 50
OFFSET_RUNS = 10

BOTH_SIDES_COUNT = """
    SELECT (SELECT count(*) FROM transactions WHERE from_account = :a)
         + (SELECT count(*) FROM transactions WHERE to_account = :a AND from_account <> :a)
"""
ROW_AT = """
    SELECT ts, id FROM (
        (SELECT ts, id FROM transactions WHERE from_account = :a)
        UNION ALL
        (SELECT ts, id FROM transactions WHERE to_account = :a AND from_account <> :a)
    ) t ORDER BY ts, id OFFSET :n LIMIT 1
"""
OFFSET_PAGE = """
    SELECT * FROM (
        (SELECT id, ts FROM transactions WHERE from_account = :a)
        UNION ALL
        (SELECT id, ts FROM transactions WHERE to_account = :a AND from_account <> :a)
    ) t ORDER BY ts, id OFFSET :n LIMIT :limit
"""


def p95_ms(run: Callable[[], object], runs: int) -> float:
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        run()
        timings.append((time.perf_counter() - start) * 1000)
    return statistics.quantiles(timings, n=20)[18]  # the 95th percentile


def largest_hub(db: Connection) -> tuple[str, int]:
    hubs = db.scalars(
        text("SELECT id FROM accounts WHERE is_high_volume AND bank_id = '70' ORDER BY id")
    ).all()
    if not hubs:
        raise SystemExit("No bank-70 high-volume accounts: run `make seed` first.")
    sizes = {hub: int(db.scalar(text(BOTH_SIDES_COUNT), {"a": hub}) or 0) for hub in hubs}
    hub = max(sizes, key=lambda h: sizes[h])
    return hub, sizes[hub]


def main() -> None:
    with engine().connect() as db:
        db.execute(text("ANALYZE transactions"))  # fresh statistics for the planner
        repository = SqlAccountsRepository(db)
        hub, rows = largest_hub(db)
        print(f"account {hub}: {rows:,} transactions (sent + received)")

        # The last page starts after the row at position rows - PAGE - 1 (0-based).
        ts, row_id = db.execute(text(ROW_AT), {"a": hub, "n": rows - PAGE - 1}).one()
        last = Position(ts=ts, id=row_id)
        everything = Window()

        first_ms = p95_ms(lambda: repository.transactions(hub, everything, None, PAGE + 1), RUNS)
        deep_ms = p95_ms(lambda: repository.transactions(hub, everything, last, PAGE + 1), RUNS)
        deep_page = repository.transactions(hub, everything, last, PAGE + 1)
        if len(deep_page) != PAGE:
            raise RuntimeError(f"expected the last {PAGE} rows, got {len(deep_page)}")
        offset_ms = p95_ms(
            lambda: db.execute(
                text(OFFSET_PAGE), {"a": hub, "n": rows - PAGE, "limit": PAGE}
            ).all(),
            OFFSET_RUNS,
        )
        count_ms = p95_ms(lambda: repository.count(hub, everything), RUNS)
        count = repository.count(hub, everything)

        print(f"\np95 over {RUNS} runs, {PAGE} rows per page:")
        print(f"  keyset, page 1                {first_ms:8.2f} ms")
        print(f"  keyset, last page             {deep_ms:8.2f} ms")
        print(f"  OFFSET {rows - PAGE:,}, last page   {offset_ms:8.2f} ms   ({OFFSET_RUNS} runs)")
        print(
            f"  total ({'estimate' if count.is_estimate else 'exact'}: {count.total:,})"
            f"      {count_ms:8.2f} ms"
        )

        sql, params = transactions_query(hub, everything, last, PAGE + 1)
        plan = db.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"), params).scalars().all()
        print("\nEXPLAIN (ANALYZE, BUFFERS) of the last keyset page:")
        for line in plan:
            print(f"  {line}")


if __name__ == "__main__":
    main()
