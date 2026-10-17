"""Accounts: profile, transactions, counterparties."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Path, Query

from aml.api import placeholders
from aml.api.problems import ProblemError
from aml.api.schemas import (
    Account,
    AccountId,
    CounterpartyLimit,
    CounterpartyList,
    Cursor,
    Error,
    PageLimit,
    Timestamp,
    TransactionPage,
    WindowHours,
)

router = APIRouter(tags=["accounts"])

AccountPath = Annotated[AccountId, Path()]


@router.get("/accounts/{account_id}", operation_id="getAccount")
def get_account(account_id: AccountPath) -> Account:
    return placeholders.account(account_id)


@router.get("/accounts/{account_id}/transactions", operation_id="listAccountTransactions")
def list_account_transactions(
    account_id: AccountPath,
    from_: Annotated[Timestamp | None, Query(alias="from")] = None,
    to: Annotated[Timestamp | None, Query()] = None,
    limit: Annotated[PageLimit, Query()] = 50,
    cursor: Annotated[Cursor | None, Query()] = None,
) -> TransactionPage:
    if from_ is not None and to is not None and to <= from_:
        raise ProblemError(
            422,
            "`to` must be after `from`.",
            errors=[Error(location="/query/to", message="must be after `from`")],
        )
    tx = placeholders.transaction(account_id)
    in_window = (from_ is None or tx.ts >= from_) and (to is None or tx.ts < to)
    items = [tx] if in_window else []
    return TransactionPage(items=items[:limit], next_cursor=None, total=len(items))


@router.get("/accounts/{account_id}/counterparties", operation_id="listAccountCounterparties")
def list_account_counterparties(
    account_id: AccountPath,
    window_hours: Annotated[WindowHours, Query()],
    as_of: Annotated[Timestamp | None, Query()] = None,
    limit: Annotated[CounterpartyLimit, Query()] = 100,
) -> CounterpartyList:
    window_end = as_of or placeholders.UPDATED_AT
    window_start = window_end - timedelta(hours=window_hours)
    edge = placeholders.counterparty_edge()
    items = [edge] if window_start <= edge.first_ts < window_end else []
    return CounterpartyList(
        account_id=account_id,
        window_start=window_start,
        window_end=window_end,
        items=items[:limit],
        total_edges=len(items),
    )
