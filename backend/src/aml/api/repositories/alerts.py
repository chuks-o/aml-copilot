"""Alerts: create (POST /alerts) and read back (GET /alerts/{id}).

The alerts table needs a window (``window_start``/``window_end``) that POST /alerts doesn't send;
it is derived from the cited transactions: [earliest ts, latest ts + 1 minute).
Rationale: docs/decisions/0025-idempotency.md.
"""

from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import Connection, text

from aml.api.problems import ProblemError
from aml.api.schemas import Alert, AlertCreate, AlertStatus, Error, Typology

_SELECT = """
    SELECT a.id, a.account_id, a.score, a.typology, a.reason, a.transaction_ids,
           a.rule_id AS model_version, a.status, a.triggered_at AS created_at, c.id AS case_id
    FROM alerts a LEFT JOIN cases c ON c.alert_id = a.id
"""


class AlertsRepository(Protocol):
    def create(self, alert: AlertCreate, idempotency_key: str) -> Alert:
        """Raises ProblemError(422) for an unknown account or transactions."""
        ...

    def get(self, alert_id: UUID) -> Alert | None: ...


class SqlAlertsRepository:
    def __init__(self, connection: Connection) -> None:
        self._db = connection

    def create(self, alert: AlertCreate, idempotency_key: str) -> Alert:
        known = self._db.scalar(
            text("SELECT 1 FROM accounts WHERE id = :id"), {"id": alert.account_id}
        )
        if known is None:
            raise ProblemError(
                422,
                f"Account {alert.account_id} does not exist.",
                errors=[Error(location="/body/account_id", message="unknown account")],
            )
        ids = sorted(alert.transaction_ids)
        cited = self._db.execute(
            text("SELECT id, ts, from_account, to_account FROM transactions WHERE id = ANY(:ids)"),
            {"ids": ids},
        ).all()
        found = {row.id: row for row in cited}
        problems = [
            Error(location=f"/body/transaction_ids/{n}", message="unknown transaction")
            for n, tx_id in enumerate(ids)
            if tx_id not in found
        ] + [
            Error(location=f"/body/transaction_ids/{n}", message="does not involve the account")
            for n, tx_id in enumerate(ids)
            if tx_id in found
            and alert.account_id not in (found[tx_id].from_account, found[tx_id].to_account)
        ]
        if problems:
            raise ProblemError(422, "Cited transactions are invalid.", errors=problems)
        times = [row.ts for row in cited]
        alert_id = self._db.scalar(
            text(
                "INSERT INTO alerts (account_id, rule_id, triggered_at, window_start, window_end, "
                "score, status, reason, transaction_ids, typology, idempotency_key) "
                "VALUES (:account, :rule, now(), :start, :end, :score, 'OPEN', :reason, :ids, "
                ":typology, :key) RETURNING id"
            ),
            {
                "account": alert.account_id,
                "rule": alert.model_version,
                "start": min(times),
                "end": max(times) + timedelta(minutes=1),
                "score": alert.score,
                "reason": alert.reason,
                "ids": ids,
                "typology": alert.typology.value if alert.typology else None,
                "key": idempotency_key,
            },
        )
        created = self.get(alert_id)
        if created is None:  # pragma: no cover - just inserted in this transaction
            raise RuntimeError(f"alert {alert_id} vanished")
        return created

    def get(self, alert_id: UUID) -> Alert | None:
        row = self._db.execute(text(f"{_SELECT} WHERE a.id = :id"), {"id": alert_id}).first()
        return _alert(row._mapping) if row is not None else None


def _alert(row: Any) -> Alert:
    return Alert(
        id=row["id"],
        account_id=row["account_id"],
        score=float(row["score"]),
        typology=Typology(row["typology"]) if row["typology"] else None,
        reason=row["reason"],
        transaction_ids=set(row["transaction_ids"]),
        model_version=row["model_version"],
        status=AlertStatus(row["status"]),
        case_id=row["case_id"],
        created_at=row["created_at"],
    )
