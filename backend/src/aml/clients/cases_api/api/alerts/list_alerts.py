from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.alert_page import AlertPage
from ...models.alert_status import AlertStatus
from ...models.problem import Problem
from ...models.validation_problem import ValidationProblem
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    status: AlertStatus | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_status: str | Unset = UNSET
    if not isinstance(status, Unset):
        json_status = status.value

    params["status"] = json_status

    params["limit"] = limit

    params["cursor"] = cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/alerts",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AlertPage | Problem | ValidationProblem | None:
    if response.status_code == 200:
        response_200 = AlertPage.from_dict(response.json())

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
) -> Response[AlertPage | Problem | ValidationProblem]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    status: AlertStatus | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: str | Unset = UNSET,
) -> Response[AlertPage | Problem | ValidationProblem]:
    """List alerts

     Newest first (`created_at` descending, then `id`).

    Args:
        status (AlertStatus | Unset): `OPEN` until grouped into a case (`IN_CASE`) or dismissed
            (`DISMISSED`).
        limit (int | Unset):  Default: 50.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AlertPage | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        status=status,
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
    status: AlertStatus | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: str | Unset = UNSET,
) -> AlertPage | Problem | ValidationProblem | None:
    """List alerts

     Newest first (`created_at` descending, then `id`).

    Args:
        status (AlertStatus | Unset): `OPEN` until grouped into a case (`IN_CASE`) or dismissed
            (`DISMISSED`).
        limit (int | Unset):  Default: 50.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AlertPage | Problem | ValidationProblem
    """

    return sync_detailed(
        client=client,
        status=status,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    status: AlertStatus | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: str | Unset = UNSET,
) -> Response[AlertPage | Problem | ValidationProblem]:
    """List alerts

     Newest first (`created_at` descending, then `id`).

    Args:
        status (AlertStatus | Unset): `OPEN` until grouped into a case (`IN_CASE`) or dismissed
            (`DISMISSED`).
        limit (int | Unset):  Default: 50.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AlertPage | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        status=status,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    status: AlertStatus | Unset = UNSET,
    limit: int | Unset = 50,
    cursor: str | Unset = UNSET,
) -> AlertPage | Problem | ValidationProblem | None:
    """List alerts

     Newest first (`created_at` descending, then `id`).

    Args:
        status (AlertStatus | Unset): `OPEN` until grouped into a case (`IN_CASE`) or dismissed
            (`DISMISSED`).
        limit (int | Unset):  Default: 50.
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AlertPage | Problem | ValidationProblem
    """

    return (
        await asyncio_detailed(
            client=client,
            status=status,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
