"""Monitoring rules end to end: replay -> rules -> POST /alerts on a live API -> alerts table."""

import csv
import threading
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import uvicorn
from alembic import command
from sqlalchemy import Engine, text

from aml.api import database
from aml.api.app import app
from aml.common import get_settings
from aml.data import dataset
from aml.db import alembic_config
from aml.ingest.replayer import ReplayConfig, replay
from aml.ingest.rules import load_config
from tests.fixtures.postgres import MIGRATIONS

FAN_TARGET = ("010", "8000000A1")  # receives from 6 senders within 2 h
PASS_THROUGH = ("010", "8000000B2")  # in 1,000, out 980 an hour later
HUB = ("070", "8000000C3")  # is_high_volume: skipped
LATE = ("010", "8000000D4")  # same fan-in, but after ANALYSIS_END
SENDERS = [("020", f"80000010{n}") for n in range(6)]
OTHERS = [("030", f"8000002{n:02d}") for n in range(20)]
ANALYSIS_END = datetime(2022, 9, 10)
VERSION = load_config().version


def _id(account: tuple[str, str]) -> str:
    return f"{account[0].lstrip('0')}:{account[1]}"


def _write_dataset(directory: Path) -> None:
    rows: list[list[str]] = []

    def pay(ts: datetime, src: tuple[str, str], dst: tuple[str, str], amount: str) -> None:
        rows.append([ts.strftime("%Y/%m/%d %H:%M"), *src, *dst, amount, "US Dollar", amount,
                     "US Dollar", "ACH", "0"])  # fmt: skip

    start = datetime(2022, 9, 2, 9, 0)
    for n, sender in enumerate(SENDERS):
        pay(start + timedelta(minutes=20 * n), sender, FAN_TARGET, "250.00")
        pay(start + timedelta(minutes=20 * n + 1), sender, HUB, "250.00")
        pay(ANALYSIS_END + timedelta(hours=2, minutes=20 * n), sender, LATE, "250.00")
    pay(start + timedelta(hours=5), OTHERS[0], PASS_THROUGH, "1000.00")
    pay(start + timedelta(hours=6), PASS_THROUGH, OTHERS[1], "980.00")
    for n in range(40):  # background that triggers nothing: amounts >= 20% apart (no pass-through)
        amount = f"{10 * 1.2**n:.2f}"
        pay(start + timedelta(hours=8, minutes=n), OTHERS[n % 20], OTHERS[(n + 7) % 20], amount)
    rows.reverse()  # out of time order, like the real file
    with (directory / dataset.TRANSACTIONS_FILE).open("w", newline="") as f:
        csv.writer(f).writerows([list(dataset.TRANSACTION_HEADER), *rows])
    (directory / dataset.PATTERNS_FILE).write_text("")


@pytest.fixture
def stack(
    scratch_database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Migrated scratch database with accounts and ANALYSIS_END, and a live API serving it."""
    command.upgrade(alembic_config(MIGRATIONS), "head")
    with scratch_database.begin() as connection:
        for account in [FAN_TARGET, PASS_THROUGH, HUB, LATE, *SENDERS, *OTHERS]:
            bank, number = _id(account).split(":")
            connection.execute(
                text(
                    "insert into accounts (id, bank_id, account_number, entity_type, "
                    "is_high_volume) values (:id, :bank, :number, 'CORPORATION', :hub)"
                ),
                {"id": _id(account), "bank": bank, "number": number, "hub": account == HUB},
            )
        connection.execute(
            text("insert into settings values ('ANALYSIS_END', '\"2022-09-10T00:00:00Z\"')")
        )
    database.reset()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_config=None, access_log=False)
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    monkeypatch.setenv("AML_CASES_API_URL", f"http://127.0.0.1:{port}")
    get_settings.cache_clear()
    _write_dataset(tmp_path)
    yield tmp_path
    server.should_exit = True
    thread.join(timeout=10)
    database.reset()


def _alerts(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("select rule_id, account_id from alerts order by rule_id, account_id")
        ).all()
    return [(r.rule_id, r.account_id) for r in rows]


def test_rules_raise_alerts_through_the_api(stack: Path, scratch_database: Engine) -> None:
    report = replay(stack, ReplayConfig(rate=0, rules=load_config()), echo=lambda _: None)

    assert report.alert_errors == []
    assert _alerts(scratch_database) == [
        (f"{VERSION}:fan_in", _id(FAN_TARGET)),
        (f"{VERSION}:new_counterparty_burst", _id(FAN_TARGET)),
        (f"{VERSION}:pass_through", _id(PASS_THROUGH)),
    ]
    assert report.alerts_by_rule == {"fan_in": 1, "new_counterparty_burst": 1, "pass_through": 1}
    assert report.alert_lag_p95_ms() is not None
    with scratch_database.connect() as connection:
        fan = connection.execute(
            text(
                "select reason, typology, score, cardinality(transaction_ids) as n from alerts "
                "where rule_id = :rule"
            ),
            {"rule": f"{VERSION}:fan_in"},
        ).one()
        keys = set(connection.scalars(text("select key from idempotency_keys")))
    assert (fan.reason, fan.typology, fan.n) == (
        "Received from 5 distinct senders within 24 h.",
        "FAN_IN",
        5,
    )
    assert f"fan_in:{_id(FAN_TARGET)}:2022-09-01T10:20:00+00:00" in keys


def test_hubs_and_anything_after_analysis_end_never_alert(
    stack: Path, scratch_database: Engine
) -> None:
    replay(stack, ReplayConfig(rate=0, rules=load_config()), echo=lambda _: None)

    alerted = {account for _, account in _alerts(scratch_database)}
    assert _id(HUB) not in alerted
    assert _id(LATE) not in alerted


def test_replaying_again_creates_no_new_alerts(stack: Path, scratch_database: Engine) -> None:
    first = replay(stack, ReplayConfig(rate=0, rules=load_config()), echo=lambda _: None)
    before = _alerts(scratch_database)

    again = replay(
        stack, ReplayConfig(rate=0, rules=load_config(), from_start=True), echo=lambda _: None
    )

    assert again.duplicates == first.committed
    assert again.alert_errors == []
    assert _alerts(scratch_database) == before
