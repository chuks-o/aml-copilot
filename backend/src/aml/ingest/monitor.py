"""Runs the monitoring rules for the accounts each replayed batch touched, and raises alerts.

After a batch commits:

1. The touched accounts (minus ``is_high_volume`` hubs) and their new transactions, which
   are the triggers. Triggers at or after ``ANALYSIS_END`` are ignored: nothing may alert,
   label or split past it (0023).
2. Each account's full history up to the batch, from the database. Non-hub accounts have at
   most a few hundred transactions.
3. ``rules.scan`` per rule, starting after the account's last alert for that rule. That point
   is read once per account from ``alerts``, so it survives restarts.
4. ``POST /alerts`` through the generated client (async, bounded concurrency), with
   Idempotency-Key ``rule_id:account_id:window_start``. Hits are deterministic (rules.py),
   so a re-run replays the same keys and creates nothing new (0025).

Rationale: docs/decisions/0028-monitoring-rules.md.
"""

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg

from aml.clients import cases_api_client
from aml.clients.cases_api.api.alerts import create_alert
from aml.clients.cases_api.models import AlertFields
from aml.clients.cases_api.models import Typology as ApiTypology
from aml.ingest import rules

CONCURRENCY = 16
_API_WINDOW_PAD = timedelta(minutes=1)  # POST /alerts ends a window 1 min after its last tx

_HISTORY = """
    SELECT from_account AS account, id, ts, to_account AS counterparty, 'OUT' AS direction,
           amount_paid AS amount, currency_paid AS currency
    FROM transactions
    WHERE from_account = ANY(%(accounts)s) AND to_account <> from_account AND ts <= %(until)s
    UNION ALL
    SELECT to_account, id, ts, from_account, 'IN', amount_received, currency_received
    FROM transactions
    WHERE to_account = ANY(%(accounts)s) AND to_account <> from_account AND ts <= %(until)s
"""


@dataclass
class MonitorResult:
    alerts_by_rule: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    lags_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Monitor:
    def __init__(
        self,
        connection: psycopg.Connection[Any],
        config: rules.MonitorConfig,
        *,
        client: Callable[[], Any] = cases_api_client,
    ) -> None:
        self._db, self._config, self._client = connection, config, client
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM accounts WHERE is_high_volume")
            self._hubs = {row[0] for row in cursor.fetchall()} if config.skip_high_volume else set()
            cursor.execute("SELECT value FROM settings WHERE key = 'ANALYSIS_END'")
            row = cursor.fetchone()
        connection.commit()
        if row is None:
            raise RuntimeError("settings.ANALYSIS_END is missing: run `aml seed` first")
        self.analysis_end = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
        self._since: dict[tuple[str, str], datetime | None] = {}

    # ------------------------------------------------------------------ database reads

    def _triggers(self, ids: Sequence[int]) -> dict[str, list[int]]:
        """New transaction ids per touched, monitored account."""
        with self._db.cursor() as cursor:
            cursor.execute(
                "SELECT id, from_account, to_account FROM transactions "
                "WHERE id = ANY(%s) AND ts < %s AND from_account <> to_account",
                (list(ids), self.analysis_end),
            )
            rows = cursor.fetchall()
        touched: dict[str, list[int]] = defaultdict(list)
        for tx_id, src, dst in rows:
            for account in (src, dst):
                if account not in self._hubs:
                    touched[account].append(tx_id)
        return touched

    def _load_since(self, accounts: Sequence[str]) -> None:
        """Each account's last alert trigger per rule (from earlier runs, too)."""
        missing = [a for a in accounts if (rules.RULE_IDS[0], a) not in self._since]
        if not missing:
            return
        for account in missing:
            for rule_id in rules.RULE_IDS:
                self._since[(rule_id, account)] = None
        prefix = f"{self._config.version}:"
        with self._db.cursor() as cursor:
            cursor.execute(
                "SELECT account_id, substr(rule_id, %s), max(window_end) FROM alerts "
                "WHERE account_id = ANY(%s) AND rule_id LIKE %s GROUP BY 1, 2",
                (len(prefix) + 1, missing, prefix + "%"),
            )
            for account, rule_id, window_end in cursor.fetchall():
                self._since[(rule_id, account)] = window_end - _API_WINDOW_PAD

    def _history(self, accounts: Sequence[str], until: datetime) -> dict[str, list[rules.Tx]]:
        with self._db.cursor() as cursor:
            cursor.execute(_HISTORY, {"accounts": list(accounts), "until": until})
            rows = cursor.fetchall()
        history: dict[str, list[rules.Tx]] = defaultdict(list)
        for account, tx_id, ts, counterparty, direction, amount, currency in rows:
            history[account].append(
                rules.Tx(ts, int(tx_id), counterparty, direction, Decimal(amount), currency)
            )
        return history

    # -------------------------------------------------------------------- evaluation

    def hits(self, batch_ids: Sequence[int]) -> list[tuple[str, rules.Hit]]:
        """(account, hit) for every rule that fires on this batch's transactions."""
        touched = self._triggers(batch_ids)
        if not touched:
            self._db.commit()
            return []
        accounts = sorted(touched)
        self._load_since(accounts)
        history = self._history(accounts, self.analysis_end - timedelta(microseconds=1))
        self._db.commit()
        found: list[tuple[str, rules.Hit]] = []
        for account in accounts:
            txs = history.get(account, [])
            new_ids = set(touched[account])
            triggers = [t for t in txs if t.id in new_ids]
            for rule_id in rules.RULE_IDS:
                since = self._since[(rule_id, account)]
                for hit in rules.scan(rule_id, self._config.rules, txs, triggers, since):
                    found.append((account, hit))
                    self._since[(rule_id, account)] = hit.trigger.ts
        return found

    def evaluate(self, batch_ids: Sequence[int], committed_at: float) -> MonitorResult:
        """Find this batch's hits and POST them; lag is measured from ``committed_at``."""
        result = MonitorResult()
        found = self.hits(batch_ids)
        if found:
            asyncio.run(self._post(found, committed_at, result))
        return result

    async def _post(
        self, found: list[tuple[str, rules.Hit]], committed_at: float, result: MonitorResult
    ) -> None:
        limit = asyncio.Semaphore(CONCURRENCY)
        async with self._client() as client:

            async def send(account: str, hit: rules.Hit) -> None:
                body = AlertFields(
                    account_id=account,
                    score=hit.score,
                    reason=hit.reason,
                    transaction_ids=list(hit.cited),
                    model_version=f"{self._config.version}:{hit.rule_id}",
                    typology=ApiTypology(hit.typology) if hit.typology else None,
                )
                key = idempotency_key(hit, account)
                async with limit:
                    response = await create_alert.asyncio_detailed(
                        client=client, body=body, idempotency_key=key
                    )
                if response.status_code == 201:
                    result.alerts_by_rule[hit.rule_id] += 1
                    result.lags_ms.append((time.monotonic() - committed_at) * 1000)
                else:
                    result.errors.append(f"{key}: {response.status_code} {response.content!r}")

            await asyncio.gather(*(send(account, hit) for account, hit in found))


def idempotency_key(hit: rules.Hit, account: str) -> str:
    return f"{hit.rule_id}:{account}:{hit.window_start.isoformat()}"
