"""Schema v1 rules that matter beyond "the tables exist" (each test is rolled back)."""

from decimal import Decimal

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError, IntegrityError

ACCOUNT = "10:8000EBD30"
OTHER = "37861:80B779D80"


@pytest.fixture
def accounts(db: Connection) -> Connection:
    db.execute(
        text(
            "insert into accounts (id, bank_id, account_number, entity_type) values "
            "(:a, '10', '8000EBD30', 'CORPORATION'), (:b, '37861', '80B779D80', 'INDIVIDUAL')"
        ),
        {"a": ACCOUNT, "b": OTHER},
    )
    return db


def _insert_transaction(db: Connection, ts: str, **overrides: object) -> None:
    row = {
        "id": 1,
        "ts": ts,
        "from_account": ACCOUNT,
        "to_account": OTHER,
        "amount_paid": "3697.34",
        "currency_paid": "USD",
        "amount_received": "3697.34",
        "currency_received": "USD",
        "payment_format": "WIRE",
        "is_laundering": False,
        "pattern": None,
    } | overrides
    db.execute(
        text(
            "insert into transactions values (:id, :ts, :from_account, :to_account, :amount_paid, "
            ":currency_paid, :amount_received, :currency_received, :payment_format, "
            ":is_laundering, :pattern)"
        ),
        row,
    )


def test_rows_land_in_their_month_or_the_default_partition(accounts: Connection) -> None:
    _insert_transaction(accounts, "2022-09-05T12:00:00Z", id=1)
    _insert_transaction(accounts, "2023-01-01T00:00:00Z", id=2)

    placed = accounts.execute(
        text("select id, tableoid::regclass::text from transactions order by id")
    ).all()

    assert [tuple(r) for r in placed] == [(1, "transactions_2022_09"), (2, "transactions_default")]


def test_bitcoin_amounts_keep_their_six_decimals(accounts: Connection) -> None:
    _insert_transaction(
        accounts, "2022-09-05T12:00:00Z", amount_paid="0.000001", currency_paid="BTC"
    )

    assert accounts.scalar(text("select amount_paid from transactions")) == Decimal("0.000001")


@pytest.mark.parametrize(
    ("is_laundering", "pattern"), [(True, None), (False, "FAN_IN"), (True, "MADE_UP")]
)
def test_pattern_is_set_exactly_for_laundering_rows(
    accounts: Connection, is_laundering: bool, pattern: str | None
) -> None:
    with pytest.raises(IntegrityError), accounts.begin_nested():
        _insert_transaction(
            accounts, "2022-09-05T12:00:00Z", is_laundering=is_laundering, pattern=pattern
        )


def test_unlisted_marks_laundering_rows_missing_from_the_patterns_file(
    accounts: Connection,
) -> None:
    _insert_transaction(accounts, "2022-09-05T12:00:00Z", is_laundering=True, pattern="UNLISTED")

    assert accounts.scalar(text("select pattern from transactions")) == "UNLISTED"


def test_transactions_need_known_accounts(accounts: Connection) -> None:
    with pytest.raises(IntegrityError), accounts.begin_nested():
        _insert_transaction(accounts, "2022-09-05T12:00:00Z", to_account="99:ABC")


@pytest.mark.parametrize("account_id", ["010:8000EBD30", "10:8000ebd30", "10-8000EBD30"])
def test_account_ids_follow_decision_0015(db: Connection, account_id: str) -> None:
    bank, _, number = account_id.replace("-", ":").partition(":")
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "insert into accounts (id, bank_id, account_number, entity_type) "
                "values (:id, :bank, :number, 'CORPORATION')"
            ),
            {"id": account_id, "bank": bank, "number": number},
        )


def test_case_events_are_append_only(accounts: Connection) -> None:
    db = accounts
    alert = db.scalar(
        text(
            "insert into alerts (account_id, rule_id, triggered_at, window_start, window_end, "
            "reason, transaction_ids, idempotency_key) values (:a, 'rule', now(), "
            "now() - interval '1 hour', now(), 'r', '{1}', 'k-1') returning id"
        ),
        {"a": ACCOUNT},
    )
    case = db.scalar(text("insert into cases (alert_id) values (:a) returning id"), {"a": alert})
    db.execute(
        text("insert into case_events (case_id, type, actor) values (:c, 'OPENED', 'test')"),
        {"c": case},
    )

    for statement in ("update case_events set actor = 'x'", "delete from case_events"):
        with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
            db.execute(text(statement))
    assert db.scalar(text("select count(*) from case_events")) == 1


def test_one_case_per_alert_and_one_decision_per_case(accounts: Connection) -> None:
    db = accounts
    alert = db.scalar(
        text(
            "insert into alerts (account_id, rule_id, triggered_at, window_start, window_end, "
            "reason, transaction_ids, idempotency_key) values (:a, 'rule', now(), "
            "now() - interval '1 hour', now(), 'r', '{1}', 'k-2') returning id"
        ),
        {"a": ACCOUNT},
    )
    case = db.scalar(text("insert into cases (alert_id) values (:a) returning id"), {"a": alert})
    decide = text(
        "insert into analyst_decisions (case_id, action, outcome, reason, analyst_id) "
        "values (:c, 'APPROVE', 'ESCALATE', 'checked', 'analyst-07')"
    )
    db.execute(decide, {"c": case})

    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("insert into cases (alert_id) values (:a)"), {"a": alert})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(decide, {"c": case})


def test_typology_docs_store_1024_dimension_embeddings(db: Connection) -> None:
    vector = "[" + ",".join(["0.5"] * 1024) + "]"
    db.execute(
        text("insert into typology_docs (title, chunk, embedding) values ('Fan-in', 'c', :v)"),
        {"v": vector},
    )

    assert db.scalar(text("select embedding <=> :v from typology_docs"), {"v": vector}) == 0
    with pytest.raises(DBAPIError, match="expected 1024 dimensions"), db.begin_nested():
        db.execute(
            text("insert into typology_docs (title, chunk, embedding) values ('x', 'c', '[1,2]')")
        )
