from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.alert import Alert
from ...models.problem import Problem
from typing import cast
from uuid import UUID


def _get_kwargs(
    alert_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/alerts/{alert_id}".format(
            alert_id=quote(str(alert_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Alert | Problem | None:
    if response.status_code == 200:
        response_200 = Alert.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = Problem.from_dict(response.json())

        return response_400

    if response.status_code == 404:
        response_404 = Problem.from_dict(response.json())

        return response_404

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
) -> Response[Alert | Problem]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    alert_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Alert | Problem]:
    """Get an alert

    Args:
        alert_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Alert | Problem]
    """

    kwargs = _get_kwargs(
        alert_id=alert_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    alert_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Alert | Problem | None:
    """Get an alert

    Args:
        alert_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Alert | Problem
    """

    return sync_detailed(
        alert_id=alert_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    alert_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Alert | Problem]:
    """Get an alert

    Args:
        alert_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Alert | Problem]
    """

    kwargs = _get_kwargs(
        alert_id=alert_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    alert_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Alert | Problem | None:
    """Get an alert

    Args:
        alert_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Alert | Problem
    """

    return (
        await asyncio_detailed(
            alert_id=alert_id,
            client=client,
        )
    ).parsed
