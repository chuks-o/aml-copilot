"""Alerts: /alerts, /alerts/{alert_id}."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from aml.api import placeholders
from aml.api.schemas import (
    Alert,
    AlertCreate,
    AlertPage,
    AlertStatus,
    Cursor,
    IdempotencyKeyValue,
    PageLimit,
)

router = APIRouter(tags=["alerts"])


@router.get("/alerts", operation_id="listAlerts")
def list_alerts(
    status: Annotated[AlertStatus | None, Query()] = None,
    limit: Annotated[PageLimit, Query()] = 50,
    cursor: Annotated[Cursor | None, Query()] = None,
) -> AlertPage:
    items = [placeholders.alert()] if status in (None, AlertStatus.OPEN) else []
    return AlertPage(items=items[:limit], next_cursor=None, total_estimate=len(items))


@router.post("/alerts", operation_id="createAlert", status_code=201)
def create_alert(
    body: AlertCreate,
    response: Response,
    idempotency_key: Annotated[IdempotencyKeyValue, Header(alias="Idempotency-Key")],
) -> Alert:
    alert = placeholders.alert(placeholders.id_for(idempotency_key, "alert"), create=body)
    response.headers["Location"] = f"/alerts/{alert.id}"
    return alert


@router.get("/alerts/{alert_id}", operation_id="getAlert")
def get_alert(alert_id: UUID) -> Alert:
    return placeholders.alert(alert_id)
