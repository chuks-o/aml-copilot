from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.case_page import CasePage
from ...models.case_status import CaseStatus
from ...models.problem import Problem
from ...models.typology import Typology
from ...models.validation_problem import ValidationProblem
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    status: CaseStatus | Unset = UNSET,
    typology: Typology | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_status: str | Unset = UNSET
    if not isinstance(status, Unset):
        json_status = status.value

    params["status"] = json_status

    json_typology: str | Unset = UNSET
    if not isinstance(typology, Unset):
        json_typology = typology.value

    params["typology"] = json_typology

    params["limit"] = limit

    params["cursor"] = cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/cases",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CasePage | Problem | ValidationProblem | None:
    if response.status_code == 200:
        response_200 = CasePage.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = Problem.from_dict(response.json())

        return response_400

    if response.status_code == 422:
        response_422 = ValidationProblem.from_dict(response.json())

        return response_422

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
) -> Response[CasePage | Problem | ValidationProblem]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    status: CaseStatus | Unset = UNSET,
    typology: Typology | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> Response[CasePage | Problem | ValidationProblem]:
    """List cases

     Newest first (`created_at` descending, then `id`).

    Args:
        status (CaseStatus | Unset): See `PATCH /cases/{case_id}/status` for the allowed
            transitions.
        typology (Typology | Unset): Laundering pattern, as named in the HI-Small patterns file.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CasePage | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        status=status,
        typology=typology,
        limit=limit,
        cursor=cursor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    status: CaseStatus | Unset = UNSET,
    typology: Typology | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> CasePage | Problem | ValidationProblem | None:
    """List cases

     Newest first (`created_at` descending, then `id`).

    Args:
        status (CaseStatus | Unset): See `PATCH /cases/{case_id}/status` for the allowed
            transitions.
        typology (Typology | Unset): Laundering pattern, as named in the HI-Small patterns file.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CasePage | Problem | ValidationProblem
    """

    return sync_detailed(
        client=client,
        status=status,
        typology=typology,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    status: CaseStatus | Unset = UNSET,
    typology: Typology | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> Response[CasePage | Problem | ValidationProblem]:
    """List cases

     Newest first (`created_at` descending, then `id`).

    Args:
        status (CaseStatus | Unset): See `PATCH /cases/{case_id}/status` for the allowed
            transitions.
        typology (Typology | Unset): Laundering pattern, as named in the HI-Small patterns file.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CasePage | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        status=status,
        typology=typology,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    status: CaseStatus | Unset = UNSET,
    typology: Typology | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> CasePage | Problem | ValidationProblem | None:
    """List cases

     Newest first (`created_at` descending, then `id`).

    Args:
        status (CaseStatus | Unset): See `PATCH /cases/{case_id}/status` for the allowed
            transitions.
        typology (Typology | Unset): Laundering pattern, as named in the HI-Small patterns file.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CasePage | Problem | ValidationProblem
    """

    return (
        await asyncio_detailed(
            client=client,
            status=status,
            typology=typology,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
