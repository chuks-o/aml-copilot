from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.approve_decision import ApproveDecision
from ...models.case import Case
from ...models.override_decision import OverrideDecision
from ...models.problem import Problem
from ...models.validation_problem import ValidationProblem
from typing import cast
from uuid import UUID


def _get_kwargs(
    case_id: UUID,
    *,
    body: ApproveDecision | OverrideDecision,
    if_match: str,
    idempotency_key: str,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["If-Match"] = if_match

    headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/cases/{case_id}/decisions".format(
            case_id=quote(str(case_id), safe=""),
        ),
    }

    if isinstance(body, ApproveDecision):
        _kwargs["json"] = body.to_dict()
    else:
        _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Case | Problem | ValidationProblem | None:
    if response.status_code == 200:
        response_200 = Case.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = Problem.from_dict(response.json())

        return response_400

    if response.status_code == 404:
        response_404 = Problem.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = Problem.from_dict(response.json())

        return response_409

    if response.status_code == 412:
        response_412 = Problem.from_dict(response.json())

        return response_412

    if response.status_code == 422:
        response_422 = ValidationProblem.from_dict(response.json())

        return response_422

    if response.status_code == 428:
        response_428 = Problem.from_dict(response.json())

        return response_428

    if response.status_code == 429:
        response_429 = Problem.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = Problem.from_dict(response.json())

        return response_500

    if response.status_code == 503:
        response_503 = Problem.from_dict(response.json())

        return response_503

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Case | Problem | ValidationProblem]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    case_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ApproveDecision | OverrideDecision,
    if_match: str,
    idempotency_key: str,
) -> Response[Case | Problem | ValidationProblem]:
    """Decide a case

     The analyst approves the copilot's recommendation, or overrides it with a different
    outcome. A reason is always required.

    In one transaction this records the decision and moves the case to `ESCALATED`
    (outcome `ESCALATE`) or `CLOSED` (outcome `CLOSE`). `version` goes up by one. Either
    both happen or neither does.
    - Allowed only when the case is `COMPLETE` or `NEEDS_HUMAN`; otherwise, including a
      case already decided, 409.
    - `APPROVE` needs a recommendation on the case, and `OVERRIDE` must choose a different
      outcome from it; otherwise 409.
    - Missing `If-Match` returns 428. A stale version returns 412.

    Args:
        case_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        if_match (str): A strong ETag holding a case version, e.g. `"3"`.
        idempotency_key (str):
        body (ApproveDecision | OverrideDecision): `APPROVE` takes the recommendation's outcome;
            `OVERRIDE` states a different one.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Case | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        case_id=case_id,
        body=body,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    case_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ApproveDecision | OverrideDecision,
    if_match: str,
    idempotency_key: str,
) -> Case | Problem | ValidationProblem | None:
    """Decide a case

     The analyst approves the copilot's recommendation, or overrides it with a different
    outcome. A reason is always required.

    In one transaction this records the decision and moves the case to `ESCALATED`
    (outcome `ESCALATE`) or `CLOSED` (outcome `CLOSE`). `version` goes up by one. Either
    both happen or neither does.
    - Allowed only when the case is `COMPLETE` or `NEEDS_HUMAN`; otherwise, including a
      case already decided, 409.
    - `APPROVE` needs a recommendation on the case, and `OVERRIDE` must choose a different
      outcome from it; otherwise 409.
    - Missing `If-Match` returns 428. A stale version returns 412.

    Args:
        case_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        if_match (str): A strong ETag holding a case version, e.g. `"3"`.
        idempotency_key (str):
        body (ApproveDecision | OverrideDecision): `APPROVE` takes the recommendation's outcome;
            `OVERRIDE` states a different one.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Case | Problem | ValidationProblem
    """

    return sync_detailed(
        case_id=case_id,
        client=client,
        body=body,
        if_match=if_match,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    case_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ApproveDecision | OverrideDecision,
    if_match: str,
    idempotency_key: str,
) -> Response[Case | Problem | ValidationProblem]:
    """Decide a case

     The analyst approves the copilot's recommendation, or overrides it with a different
    outcome. A reason is always required.

    In one transaction this records the decision and moves the case to `ESCALATED`
    (outcome `ESCALATE`) or `CLOSED` (outcome `CLOSE`). `version` goes up by one. Either
    both happen or neither does.
    - Allowed only when the case is `COMPLETE` or `NEEDS_HUMAN`; otherwise, including a
      case already decided, 409.
    - `APPROVE` needs a recommendation on the case, and `OVERRIDE` must choose a different
      outcome from it; otherwise 409.
    - Missing `If-Match` returns 428. A stale version returns 412.

    Args:
        case_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        if_match (str): A strong ETag holding a case version, e.g. `"3"`.
        idempotency_key (str):
        body (ApproveDecision | OverrideDecision): `APPROVE` takes the recommendation's outcome;
            `OVERRIDE` states a different one.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Case | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        case_id=case_id,
        body=body,
        if_match=if_match,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    case_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ApproveDecision | OverrideDecision,
    if_match: str,
    idempotency_key: str,
) -> Case | Problem | ValidationProblem | None:
    """Decide a case

     The analyst approves the copilot's recommendation, or overrides it with a different
    outcome. A reason is always required.

    In one transaction this records the decision and moves the case to `ESCALATED`
    (outcome `ESCALATE`) or `CLOSED` (outcome `CLOSE`). `version` goes up by one. Either
    both happen or neither does.
    - Allowed only when the case is `COMPLETE` or `NEEDS_HUMAN`; otherwise, including a
      case already decided, 409.
    - `APPROVE` needs a recommendation on the case, and `OVERRIDE` must choose a different
      outcome from it; otherwise 409.
    - Missing `If-Match` returns 428. A stale version returns 412.

    Args:
        case_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        if_match (str): A strong ETag holding a case version, e.g. `"3"`.
        idempotency_key (str):
        body (ApproveDecision | OverrideDecision): `APPROVE` takes the recommendation's outcome;
            `OVERRIDE` states a different one.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Case | Problem | ValidationProblem
    """

    return (
        await asyncio_detailed(
            case_id=case_id,
            client=client,
            body=body,
            if_match=if_match,
            idempotency_key=idempotency_key,
        )
    ).parsed
