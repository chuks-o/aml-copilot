"""Alert volume per threshold on the DEV period only, using the replay's own rule code.

Run against the seeded `make up` database (`make seed`):  make tune-rules

Reads only transactions in rules.yaml's dev_period. Test-period rows and labels are never
read, so nothing here can leak the test period into a threshold. For fan_in and fan_out it
sweeps the minimum counterparty count; the other rules run at their configured values. For
each setting it reports alerts, alerts per day, distinct accounts, and the share of alerts
citing at least one dev-period laundering transaction (dev labels: allowed for tuning).
Rationale and method: docs/decisions/0028-monitoring-rules.md.
"""

import time
from collections import defaultdict
from decimal import Decimal

from aml import db
from aml.ingest import rules

SWEEP = range(3, 11)
GROUP = 2_000  # accounts per query

_DEV = """
    SELECT from_account AS account, id, ts, to_account AS counterparty, 'OUT' AS direction,
           amount_paid AS amount, currency_paid AS currency, is_laundering
    FROM transactions
    WHERE from_account = ANY(%(accounts)s) AND to_account <> from_account
      AND ts >= %(start)s AND ts < %(end)s
    UNION ALL
    SELECT to_account, id, ts, from_account, 'IN', amount_received, currency_received,
           is_laundering
    FROM transactions
    WHERE to_account = ANY(%(accounts)s) AND to_account <> from_account
      AND ts >= %(start)s AND ts < %(end)s
"""


def _variants(config: rules.RulesConfig) -> list[tuple[str, str, rules.RulesConfig]]:
    """(label, rule_id, config) for every setting to evaluate."""
    out: list[tuple[str, str, rules.RulesConfig]] = []
    for rule_id in ("fan_in", "fan_out"):
        for n in SWEEP:
            changed = getattr(config, rule_id).model_copy(update={"min_counterparties": n})
            out.append((f"{rule_id} N={n}", rule_id, config.model_copy(update={rule_id: changed})))
    for rule_id in ("pass_through", "structuring", "new_counterparty_burst"):
        out.append((f"{rule_id} (configured)", rule_id, config))
    return out


def main() -> None:
    monitor_config = rules.load_config()
    period = monitor_config.dev_period
    days = (period.end - period.start).total_seconds() / 86_400
    variants = _variants(monitor_config.rules)
    alerts: dict[str, int] = defaultdict(int)
    accounts_hit: dict[str, set[str]] = defaultdict(set)
    laundering_hits: dict[str, int] = defaultdict(int)
    started = time.monotonic()
    with db.connect() as connection:
        accounts_sql = (
            "SELECT id FROM accounts WHERE NOT is_high_volume ORDER BY id"
            if monitor_config.skip_high_volume
            else "SELECT id FROM accounts ORDER BY id"
        )
        ids = [r[0] for r in connection.execute(accounts_sql)]
        for start in range(0, len(ids), GROUP):
            group = ids[start : start + GROUP]
            rows = connection.execute(
                _DEV, {"accounts": group, "start": period.start, "end": period.end}
            ).fetchall()
            history: dict[str, list[rules.Tx]] = defaultdict(list)
            laundering: set[int] = set()
            for account, tx_id, ts, counterparty, direction, amount, currency, label in rows:
                history[account].append(
                    rules.Tx(ts, int(tx_id), counterparty, direction, Decimal(amount), currency)
                )
                if label:
                    laundering.add(int(tx_id))
            for account, txs in history.items():
                for label, rule_id, config in variants:
                    for hit in rules.scan(rule_id, config, txs, txs, since=None):
                        alerts[label] += 1
                        accounts_hit[label].add(account)
                        if laundering.intersection(hit.cited):
                            laundering_hits[label] += 1
            if start // GROUP % 50 == 0:
                print(f"  {start + len(group):,} / {len(ids):,} accounts", flush=True)
    print(
        f"\nDEV period {period.start:%Y-%m-%d} to {period.end:%Y-%m-%d} ({days:g} days), "
        f"{len(ids):,} monitored accounts, {time.monotonic() - started:.0f} s\n"
    )
    print(f"{'setting':<34}{'alerts':>9}{'per day':>9}{'accounts':>10}{'laundering':>12}")
    for label, _, _ in variants:
        count = alerts[label]
        share = f"{laundering_hits[label] / count:.1%}" if count else "-"
        print(
            f"{label:<34}{count:>9,}{count / days:>9,.0f}{len(accounts_hit[label]):>10,}{share:>12}"
        )


if __name__ == "__main__":
    main()
