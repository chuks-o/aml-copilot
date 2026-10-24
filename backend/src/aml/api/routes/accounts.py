"""Accounts: profile, transactions and counterparties (from the database)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Connection

from aml.api import pagination
from aml.api.database import connection
from aml.api.problems import ProblemError
from aml.api.repositories.accounts import AccountsRepository, SqlAccountsRepository, Window
from aml.api.schemas import (
    Account,
    AccountId,
    CounterpartyLimit,
    CounterpartyList,
    Cursor,
    Error,
    Timestamp,
    TransactionLimit,
    TransactionPage,
    WindowHours,
)

router = APIRouter(tags=["accounts"])

AccountPath = Annotated[AccountId, Path()]


def accounts_repository(conn: Annotated[Connection, Depends(connection)]) -> AccountsRepository:
    """Overridden in the contract test with an in-memory fake (no database there)."""
    return SqlAccountsRepository(conn)


Repository = Annotated[AccountsRepository, Depends(accounts_repository)]


def _require(repository: AccountsRepository, account_id: str) -> None:
    if not repository.exists(account_id):
        raise ProblemError(404, f"Account {account_id} does not exist.")


@router.get("/accounts/{account_id}", operation_id="getAccount")
def get_account(account_id: AccountPath, repository: Repository) -> Account:
    account = repository.get(account_id)
    if account is None:
        raise ProblemError(404, f"Account {account_id} does not exist.")
    return account


@router.get("/accounts/{account_id}/transactions", operation_id="listAccountTransactions")
def list_account_transactions(
    account_id: AccountPath,
    repository: Repository,
    from_: Annotated[Timestamp | None, Query(alias="from")] = None,
    to: Annotated[Timestamp | None, Query()] = None,
    limit: Annotated[TransactionLimit, Query()] = 100,
    cursor: Annotated[Cursor | None, Query()] = None,
) -> TransactionPage:
    if from_ is not None and to is not None and to <= from_:
        raise ProblemError(
            422,
            "`to` must be after `from`.",
            errors=[Error(location="/query/to", message="must be after `from`")],
        )
    filters = pagination.filter_hash(account=account_id, start=from_, end=to)
    try:
        after = pagination.decode(cursor, filters) if cursor is not None else None
    except pagination.CursorError as exc:
        raise ProblemError(400, f"Invalid cursor: {exc}.") from exc
    _require(repository, account_id)

    window = Window(start=from_, end=to)
    # One extra row tells us whether there is a next page without a second query.
    rows = repository.transactions(account_id, window, after, limit + 1)
    page, more = rows[:limit], len(rows) > limit
    next_cursor = (
        pagination.encode(pagination.Position(ts=page[-1].ts, id=page[-1].id), filters)
        if more
        else None
    )
    count = repository.count(account_id, window)
    return TransactionPage(
        items=page,
        next_cursor=next_cursor,
        total=count.total,
        total_is_estimate=count.is_estimate,
    )


@router.get("/accounts/{account_id}/counterparties", operation_id="listAccountCounterparties")
def list_account_counterparties(
    account_id: AccountPath,
    repository: Repository,
    window_hours: Annotated[WindowHours, Query()],
    as_of: Annotated[Timestamp | None, Query()] = None,
    limit: Annotated[CounterpartyLimit, Query()] = 100,
) -> CounterpartyList:
    _require(repository, account_id)
    window_end = as_of or datetime.now(UTC)
    window_start = window_end - timedelta(hours=window_hours)
    edges, total_edges = repository.counterparties(
        account_id, Window(start=window_start, end=window_end), limit
    )
    return CounterpartyList(
        account_id=account_id,
        window_start=window_start,
        window_end=window_end,
        items=edges,
        total_edges=total_edges,
    )
