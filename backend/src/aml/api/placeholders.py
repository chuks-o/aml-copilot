"""Schema-valid placeholder data for the stub routes, until the database exists (T10).

Everything is built from the generated models in ``aml.api.schemas``, so a placeholder that
broke the contract would fail on construction. Values are fixed, except ids, which echo the
request or are derived from the ``Idempotency-Key`` (the same key gives the same id, as a
replay would).
"""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from aml.api.schemas import (
    Alert,
    AlertCreate,
    AlertStatus,
    Case,
    CaseStatus,
    Outcome,
    Recommendation,
    Typology,
)

ACCOUNT_ID = "10:8000EBD30"
CREATED_AT = datetime(2022, 9, 1, 0, 20, tzinfo=UTC)
UPDATED_AT = datetime(2022, 9, 1, 6, 0, tzinfo=UTC)
ALERT_ID = UUID("6f0b7c4e-2a1d-4b8e-9c3f-5d7a1e2b4c6d")
TRANSACTION_ID = 1048576


def id_for(idempotency_key: str, kind: str) -> UUID:
    """A stable id per (kind, key): retrying with the same key yields the same resource id."""
    return uuid5(NAMESPACE_URL, f"aml-copilot:{kind}:{idempotency_key}")


def alert(alert_id: UUID = ALERT_ID, *, create: AlertCreate | None = None) -> Alert:
    fields = (
        create.model_dump()
        if create is not None
        else {
            "account_id": ACCOUNT_ID,
            "score": 0.93,
            "typology": Typology.FAN_IN,
            "reason": "Received from 14 accounts within 6 hours, then sent out within 2 hours.",
            "transaction_ids": {TRANSACTION_ID},
            "model_version": "placeholder",
        }
    )
    fields.setdefault("typology", None)
    return Alert(
        **fields,
        id=alert_id,
        status=AlertStatus.OPEN,
        case_id=None,
        created_at=CREATED_AT,
        triggered_at=CREATED_AT,
        window_start=CREATED_AT,
        window_end=CREATED_AT + timedelta(minutes=1),
    )


def case(
    case_id: UUID,
    *,
    status: CaseStatus = CaseStatus.OPEN,
    version: int = 1,
    account_id: str = ACCOUNT_ID,
    alert_ids: list[UUID] | None = None,
    recommendation: Recommendation | None = None,
) -> Case:
    return Case(
        id=case_id,
        version=version,
        status=status,
        typology=None,
        account_id=account_id,
        alert_ids=alert_ids or [ALERT_ID],
        recommendation=recommendation,
        decision=None,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def recommendation() -> Recommendation:
    return Recommendation(
        outcome=Outcome.ESCALATE,
        summary="Funds from 14 unrelated accounts consolidated and forwarded within 8 hours.",
        created_at=UPDATED_AT,
    )
