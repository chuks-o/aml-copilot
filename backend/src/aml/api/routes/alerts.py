"""Alerts: /alerts (list still a placeholder), POST /alerts and /alerts/{alert_id} (database)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response

from aml.api import placeholders
from aml.api.idempotency import StoredResponse
from aml.api.problems import ProblemError
from aml.api.schemas import (
    Alert,
    AlertCreate,
    AlertPage,
    AlertStatus,
    Cursor,
    IdempotencyKeyValue,
    PageLimit,
)
from aml.api.unit_of_work import Work, idempotent

router = APIRouter(tags=["alerts"])


@router.get("/alerts", operation_id="listAlerts")
def list_alerts(
    status: Annotated[AlertStatus | None, Query()] = None,
    limit: Annotated[PageLimit, Query()] = 50,
    cursor: Annotated[Cursor | None, Query()] = None,
) -> AlertPage:
    items = [placeholders.alert()] if status in (None, AlertStatus.OPEN) else []
    return AlertPage(items=items[:limit], next_cursor=None, total_estimate=len(items))


@router.post("/alerts", operation_id="createAlert", status_code=201, response_model=Alert)
def create_alert(
    body: AlertCreate,
    request: Request,
    work: Work,
    idempotency_key: Annotated[IdempotencyKeyValue, Header(alias="Idempotency-Key")],
) -> Response:
    def write() -> StoredResponse:
        alert = work.alerts.create(body, idempotency_key)
        return StoredResponse.of(201, alert, {"Location": f"/alerts/{alert.id}"})

    return idempotent(work, idempotency_key, request, body, write)


@router.get("/alerts/{alert_id}", operation_id="getAlert")
def get_alert(alert_id: UUID, work: Work) -> Alert:
    alert = work.alerts.get(alert_id)
    if alert is None:
        raise ProblemError(404, f"Alert {alert_id} does not exist.")
    return alert
