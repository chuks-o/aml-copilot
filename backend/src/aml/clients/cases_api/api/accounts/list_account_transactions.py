from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.problem import Problem
from ...models.transaction_page import TransactionPage
from ...models.validation_problem import ValidationProblem
from ...types import UNSET, Unset
from typing import cast
import datetime


def _get_kwargs(
    account_id: str,
    *,
    from_: datetime.datetime | Unset = UNSET,
    to: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_from_: str | Unset = UNSET
    if not isinstance(from_, Unset):
        json_from_ = from_.isoformat()
    params["from"] = json_from_

    json_to: str | Unset = UNSET
    if not isinstance(to, Unset):
        json_to = to.isoformat()
    params["to"] = json_to

    params["limit"] = limit

    params["cursor"] = cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/accounts/{account_id}/transactions".format(
            account_id=quote(str(account_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Problem | TransactionPage | ValidationProblem | None:
    if response.status_code == 200:
        response_200 = TransactionPage.from_dict(response.json())

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
) -> Response[Problem | TransactionPage | ValidationProblem]:
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
    from_: datetime.datetime | Unset = UNSET,
    to: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> Response[Problem | TransactionPage | ValidationProblem]:
    """List an account's transactions

     Transactions where the account is the payer or the payee, oldest first (`ts`
    ascending, then `id`). Paginated by keyset on `(ts, id)`: every page costs the same,
    however deep, and rows inserted while paging never cause duplicates or gaps among rows
    that already existed.
    - `total` is the number of transactions in the window, across all pages: exact up to
      10,000, estimated above that (`total_is_estimate: true`).
    - A cursor is bound to the account and window it was issued for. Reusing it with a
      different account, `from` or `to` returns 400. `limit` may change between pages.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        from_ (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        to (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Problem | TransactionPage | ValidationProblem]
    """

    kwargs = _get_kwargs(
        account_id=account_id,
        from_=from_,
        to=to,
        limit=limit,
        cursor=cursor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.datetime | Unset = UNSET,
    to: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> Problem | TransactionPage | ValidationProblem | None:
    """List an account's transactions

     Transactions where the account is the payer or the payee, oldest first (`ts`
    ascending, then `id`). Paginated by keyset on `(ts, id)`: every page costs the same,
    however deep, and rows inserted while paging never cause duplicates or gaps among rows
    that already existed.
    - `total` is the number of transactions in the window, across all pages: exact up to
      10,000, estimated above that (`total_is_estimate: true`).
    - A cursor is bound to the account and window it was issued for. Reusing it with a
      different account, `from` or `to` returns 400. `limit` may change between pages.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        from_ (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        to (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Problem | TransactionPage | ValidationProblem
    """

    return sync_detailed(
        account_id=account_id,
        client=client,
        from_=from_,
        to=to,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.datetime | Unset = UNSET,
    to: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> Response[Problem | TransactionPage | ValidationProblem]:
    """List an account's transactions

     Transactions where the account is the payer or the payee, oldest first (`ts`
    ascending, then `id`). Paginated by keyset on `(ts, id)`: every page costs the same,
    however deep, and rows inserted while paging never cause duplicates or gaps among rows
    that already existed.
    - `total` is the number of transactions in the window, across all pages: exact up to
      10,000, estimated above that (`total_is_estimate: true`).
    - A cursor is bound to the account and window it was issued for. Reusing it with a
      different account, `from` or `to` returns 400. `limit` may change between pages.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        from_ (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        to (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Problem | TransactionPage | ValidationProblem]
    """

    kwargs = _get_kwargs(
        account_id=account_id,
        from_=from_,
        to=to,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    account_id: str,
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.datetime | Unset = UNSET,
    to: datetime.datetime | Unset = UNSET,
    limit: int | Unset = UNSET,
    cursor: str | Unset = UNSET,
) -> Problem | TransactionPage | ValidationProblem | None:
    """List an account's transactions

     Transactions where the account is the payer or the payee, oldest first (`ts`
    ascending, then `id`). Paginated by keyset on `(ts, id)`: every page costs the same,
    however deep, and rows inserted while paging never cause duplicates or gaps among rows
    that already existed.
    - `total` is the number of transactions in the window, across all pages: exact up to
      10,000, estimated above that (`total_is_estimate: true`).
    - A cursor is bound to the account and window it was issued for. Reusing it with a
      different account, `from` or `to` returns 400. `limit` may change between pages.

    Args:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account
            number is
            upper-case hex.
             Example: 10:8000EBD30.
        from_ (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        to (datetime.datetime | Unset):  Example: 2022-09-01T00:20:00Z.
        limit (int | Unset):
        cursor (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Problem | TransactionPage | ValidationProblem
    """

    return (
        await asyncio_detailed(
            account_id=account_id,
            client=client,
            from_=from_,
            to=to,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
