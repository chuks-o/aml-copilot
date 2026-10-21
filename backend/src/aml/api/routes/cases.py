"""Cases: list, create, get, status changes and decisions.

The stubs are stateless. Each write stub assumes the case state that makes its rules testable:
- ``PATCH .../status``: the case is ``OPEN`` at version 1.
- ``POST .../decisions``: the case is ``COMPLETE`` at version 1, with recommendation ``ESCALATE``.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Header, Query, Request, Response

from aml.api import placeholders
from aml.api.idempotency import StoredResponse
from aml.api.problems import ProblemError
from aml.api.schemas import (
    Action,
    ApproveDecision,
    Case,
    CaseCreate,
    CasePage,
    CaseStatus,
    CaseStatusChange,
    Cursor,
    Decision,
    DecisionCreate,
    ETagValue,
    IdempotencyKeyValue,
    Outcome,
    PageLimit,
    Typology,
)
from aml.api.unit_of_work import Work, idempotent

router = APIRouter(tags=["cases"])

IdempotencyKey = Annotated[IdempotencyKeyValue, Header(alias="Idempotency-Key")]
IfMatch = Annotated[ETagValue, Header(alias="If-Match")]

# PATCH may only make the non-final moves; ESCALATED and CLOSED need a decision (0017).
PATCH_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.OPEN: {CaseStatus.INVESTIGATING},
    CaseStatus.INVESTIGATING: {CaseStatus.COMPLETE, CaseStatus.NEEDS_HUMAN},
}
DECIDABLE = {CaseStatus.COMPLETE, CaseStatus.NEEDS_HUMAN}
OUTCOME_STATUS = {Outcome.ESCALATE: CaseStatus.ESCALATED, Outcome.CLOSE: CaseStatus.CLOSED}


def _etag(case: Case) -> str:
    return f'"{case.version}"'


def _check_version(if_match: str, current: Case) -> None:
    if if_match != _etag(current):
        raise ProblemError(412, f"Case is at version {current.version}; re-read it and retry.")


@router.get("/cases", operation_id="listCases")
def list_cases(
    status: Annotated[CaseStatus | None, Query()] = None,
    typology: Annotated[Typology | None, Query()] = None,
    limit: Annotated[PageLimit, Query()] = 50,
    cursor: Annotated[Cursor | None, Query()] = None,
) -> CasePage:
    item = placeholders.case(placeholders.ALERT_ID)
    matches = (status in (None, item.status)) and (typology in (None, item.typology))
    items = [item] if matches else []
    return CasePage(items=items[:limit], next_cursor=None, total_estimate=len(items))


@router.post("/cases", operation_id="createCase", status_code=201, response_model=Case)
def create_case(
    body: CaseCreate, request: Request, work: Work, idempotency_key: IdempotencyKey
) -> Response:
    def write() -> StoredResponse:  # placeholder body; idempotency is real (0025)
        case = placeholders.case(
            placeholders.id_for(idempotency_key, "case"),
            account_id=body.account_id,
            # A set (uniqueItems), so the client's order is gone: the opening alert is the
            # earliest created one, not position 0 (0019).
            alert_ids=sorted(body.alert_ids),
        )
        headers = {"Location": f"/cases/{case.id}", "ETag": _etag(case)}
        return StoredResponse.of(201, case, headers)

    return idempotent(work, idempotency_key, request, body, write)


@router.get("/cases/{case_id}", operation_id="getCase")
def get_case(case_id: UUID, response: Response) -> Case:
    case = placeholders.case(case_id)
    response.headers["ETag"] = _etag(case)
    return case


@router.patch("/cases/{case_id}/status", operation_id="changeCaseStatus")
def change_case_status(
    case_id: UUID, body: CaseStatusChange, response: Response, if_match: IfMatch
) -> Case:
    current = placeholders.case(case_id)
    _check_version(if_match, current)
    if body.status not in PATCH_TRANSITIONS.get(current.status, set()):
        raise ProblemError(409, f"Cannot move a case from {current.status} to {body.status}.")
    updated = current.model_copy(update={"status": body.status, "version": current.version + 1})
    response.headers["ETag"] = _etag(updated)
    return updated


@router.post("/cases/{case_id}/decisions", operation_id="createCaseDecision", response_model=Case)
def create_case_decision(
    case_id: UUID,
    body: Annotated[DecisionCreate, Body()],
    request: Request,
    work: Work,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
) -> Response:
    def write() -> StoredResponse:  # placeholder body; idempotency is real (0025)
        recommendation = placeholders.recommendation()
        current = placeholders.case(
            case_id, status=CaseStatus.COMPLETE, recommendation=recommendation
        )
        _check_version(if_match, current)
        if current.status not in DECIDABLE:
            raise ProblemError(409, f"A {current.status} case cannot be decided.")
        if isinstance(body, ApproveDecision):
            outcome = recommendation.outcome
        elif body.outcome == recommendation.outcome:
            raise ProblemError(409, "An override must choose a different outcome than recommended.")
        else:
            outcome = body.outcome
        decision = Decision(
            id=placeholders.id_for(idempotency_key, "decision"),
            case_id=case_id,
            action=Action(body.action),
            outcome=outcome,
            reason=body.reason,
            analyst_id=body.analyst_id,
            created_at=placeholders.UPDATED_AT,
        )
        updated = current.model_copy(
            update={
                "status": OUTCOME_STATUS[outcome],
                "version": current.version + 1,
                "decision": decision,
            }
        )
        return StoredResponse.of(200, updated, {"ETag": _etag(updated)})

    return idempotent(work, idempotency_key, request, body, write)
