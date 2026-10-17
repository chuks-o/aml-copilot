from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.account import Account
from ...models.problem import Problem
from typing import cast


def _get_kwargs(
    account_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/accounts/{account_id}".format(
            account_id=quote(str(account_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Account | Problem | None:
    if response.status_code == 200:
        response_200 = Account.from_dict(response.json())

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
) -> Response[Account | Problem]:
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
) -> Response[Account | Problem]:
    """Get an account's KYC profile

     Contains only what the dataset records about the account holder: bank, entity and
    entity type, plus an activity summary. There is no risk rating, occupation or expected
    activity, because the dataset doesn't have them.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Account | Problem]
    """

    kwargs = _get_kwargs(
        account_id=account_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Account | Problem | None:
    """Get an account's KYC profile

     Contains only what the dataset records about the account holder: bank, entity and
    entity type, plus an activity summary. There is no risk rating, occupation or expected
    activity, because the dataset doesn't have them.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Account | Problem
    """

    return sync_detailed(
        account_id=account_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[Account | Problem]:
    """Get an account's KYC profile

     Contains only what the dataset records about the account holder: bank, entity and
    entity type, plus an activity summary. There is no risk rating, occupation or expected
    activity, because the dataset doesn't have them.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Account | Problem]
    """

    kwargs = _get_kwargs(
        account_id=account_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Account | Problem | None:
    """Get an account's KYC profile

     Contains only what the dataset records about the account holder: bank, entity and
    entity type, plus an activity summary. There is no risk rating, occupation or expected
    activity, because the dataset doesn't have them.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Account | Problem
    """

    return (
        await asyncio_detailed(
            account_id=account_id,
            client=client,
        )
    ).parsed
