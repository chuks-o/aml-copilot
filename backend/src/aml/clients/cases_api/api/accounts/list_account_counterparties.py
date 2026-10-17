from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.counterparty_list import CounterpartyList
from ...models.problem import Problem
from ...models.validation_problem import ValidationProblem
from ...types import UNSET, Unset
from typing import cast
import datetime


def _get_kwargs(
    account_id: str,
    *,
    window_hours: int,
    as_of: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["window_hours"] = window_hours

    json_as_of: str | Unset = UNSET
    if not isinstance(as_of, Unset):
        json_as_of = as_of.isoformat()
    params["as_of"] = json_as_of

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/accounts/{account_id}/counterparties".format(
            account_id=quote(str(account_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CounterpartyList | Problem | ValidationProblem | None:
    if response.status_code == 200:
        response_200 = CounterpartyList.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = Problem.from_dict(response.json())

        return response_400

    if response.status_code == 404:
        response_404 = Problem.from_dict(response.json())

        return response_404

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
) -> Response[CounterpartyList | Problem | ValidationProblem]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
    window_hours: int,
    as_of: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
) -> Response[CounterpartyList | Problem | ValidationProblem]:
    """Aggregate an account's counterparties

     One edge per (counterparty, direction, currency) in the window
    `[as_of - window_hours, as_of)`.
    - Outgoing edges sum `amount_paid` and incoming edges sum `amount_received`, so each
      total is money this account actually sent or got.
    - Amounts in different currencies are never added together.
    - Self-transfers are excluded.
    - Edges are ordered by `transaction_count` descending, then `counterparty_id`.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        window_hours (int):
        as_of (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CounterpartyList | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        account_id=account_id,
        window_hours=window_hours,
        as_of=as_of,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
    window_hours: int,
    as_of: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
) -> CounterpartyList | Problem | ValidationProblem | None:
    """Aggregate an account's counterparties

     One edge per (counterparty, direction, currency) in the window
    `[as_of - window_hours, as_of)`.
    - Outgoing edges sum `amount_paid` and incoming edges sum `amount_received`, so each
      total is money this account actually sent or got.
    - Amounts in different currencies are never added together.
    - Self-transfers are excluded.
    - Edges are ordered by `transaction_count` descending, then `counterparty_id`.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        window_hours (int):
        as_of (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CounterpartyList | Problem | ValidationProblem
    """

    return sync_detailed(
        account_id=account_id,
        client=client,
        window_hours=window_hours,
        as_of=as_of,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
    window_hours: int,
    as_of: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
) -> Response[CounterpartyList | Problem | ValidationProblem]:
    """Aggregate an account's counterparties

     One edge per (counterparty, direction, currency) in the window
    `[as_of - window_hours, as_of)`.
    - Outgoing edges sum `amount_paid` and incoming edges sum `amount_received`, so each
      total is money this account actually sent or got.
    - Amounts in different currencies are never added together.
    - Self-transfers are excluded.
    - Edges are ordered by `transaction_count` descending, then `counterparty_id`.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        window_hours (int):
        as_of (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CounterpartyList | Problem | ValidationProblem]
    """

    kwargs = _get_kwargs(
        account_id=account_id,
        window_hours=window_hours,
        as_of=as_of,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
    window_hours: int,
    as_of: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
) -> CounterpartyList | Problem | ValidationProblem | None:
    """Aggregate an account's counterparties

     One edge per (counterparty, direction, currency) in the window
    `[as_of - window_hours, as_of)`.
    - Outgoing edges sum `amount_paid` and incoming edges sum `amount_received`, so each
      total is money this account actually sent or got.
    - Amounts in different currencies are never added together.
    - Self-transfers are excluded.
    - Edges are ordered by `transaction_count` descending, then `counterparty_id`.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        window_hours (int):
        as_of (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CounterpartyList | Problem | ValidationProblem
    """

    return (
        await asyncio_detailed(
            account_id=account_id,
            client=client,
            window_hours=window_hours,
            as_of=as_of,
            limit=limit,
        )
    ).parsed
