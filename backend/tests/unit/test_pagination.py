import base64
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aml.api import pagination
from aml.api.repositories.accounts import money_text

TS = datetime(2022, 9, 1, 0, 20, tzinfo=UTC)
FILTERS = pagination.filter_hash(account="10:8000EBD30", start=None, end=None)


def _raw(body: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(body).encode()).rstrip(b"=").decode()


def test_round_trip() -> None:
    cursor = pagination.encode(pagination.Position(ts=TS, id=42), FILTERS)

    assert pagination.decode(cursor, FILTERS) == pagination.Position(ts=TS, id=42)
    assert "=" not in cursor  # base64url, unpadded: safe in a query string as-is


def test_a_cursor_reused_with_other_filters_is_rejected() -> None:
    cursor = pagination.encode(pagination.Position(ts=TS, id=42), FILTERS)
    other_window = pagination.filter_hash(account="10:8000EBD30", start=TS, end=None)
    other_account = pagination.filter_hash(account="20:8000EBD30", start=None, end=None)

    for filters in (other_window, other_account):
        with pytest.raises(pagination.CursorError, match="different account or time window"):
            pagination.decode(cursor, filters)


@pytest.mark.parametrize(
    "cursor",
    [
        "not base64 !",
        _raw([1, 2]),
        _raw({"v": 2, "ts": TS.isoformat(), "id": 1, "f": FILTERS}),
        _raw({"v": 1, "ts": "2022-09-01T00:20:00", "id": 1, "f": FILTERS}),  # no timezone
        _raw({"v": 1, "ts": TS.isoformat(), "id": 0, "f": FILTERS}),
        _raw({"v": 1, "ts": TS.isoformat(), "id": True, "f": FILTERS}),
        _raw({"v": 1, "id": 1, "f": FILTERS}),
    ],
)
def test_malformed_cursors_are_rejected(cursor: str) -> None:
    with pytest.raises(pagination.CursorError):
        pagination.decode(cursor, FILTERS)


def test_filter_hash_ignores_argument_order_but_not_values() -> None:
    assert pagination.filter_hash(a="x", b=None) == pagination.filter_hash(b=None, a="x")
    assert pagination.filter_hash(a="x") != pagination.filter_hash(a="y")


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        ("3697.34000000", "3697.34"),
        ("100.00000000", "100.00"),
        ("0.00000100", "0.000001"),
        ("1046302363293.48000000", "1046302363293.48"),
        ("5.10000000", "5.10"),
    ],
)
def test_money_text_trims_to_at_least_two_decimals(stored: str, shown: str) -> None:
    assert money_text(Decimal(stored)) == shown
