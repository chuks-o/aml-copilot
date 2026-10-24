"""Golden set against a real database: the sample's candidate pools, and the screen's data
through a live API (real GET /accounts/{id}, alert times, nothing after the alert)."""

import json
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest
import uvicorn
from alembic import command
from sqlalchemy import Engine, text

from aml import db
from aml.api import database
from aml.api.app import app
from aml.common import get_settings
from aml.db import alembic_config
from aml.evals import golden, label_cli, labels
from tests.fixtures.postgres import MIGRATIONS

T = datetime(2022, 9, 1, tzinfo=UTC)
Z = "10:800000F00"  # the counterparty of every laundering transaction; never alerted
T01 = golden.T01_ACCOUNTS[0]
KYC = {
    "country": "NG",
    "business_type": "Construction",
    "expected_monthly_volume_band": "1000-9999",
    "onboarded_at": "2018-06-07",
    "synthetic": ["business_type", "country", "expected_monthly_volume_band", "onboarded_at"],
    "kyc_seed": 42,
    "bank_name": "Bank #10",
    "entity_id": "800AAA",
    "entity_name": "Corporation #7",
}
# alert account, triggered_at, score, rule, laundering (offset before the alert, pattern, format)
CASES: dict[str, tuple[str, datetime, float, str, tuple[timedelta, str, str] | None]] = {
    "listed": ("10:80000000A", T + timedelta(days=2, hours=12), 0.6, "fan_in",
               (timedelta(hours=2), "FAN_IN", "ACH")),
    "unlisted_wire": ("10:80000000B", T + timedelta(days=3, hours=12), 0.6, "fan_in",
                      (timedelta(hours=1), "UNLISTED", "WIRE")),
    "unlisted_ach": ("10:80000000C", T + timedelta(days=3, hours=12), 0.6, "fan_in",
                     (timedelta(hours=1), "UNLISTED", "ACH")),
    "t01": (T01, T + timedelta(days=1, hours=12), 0.95, "fan_in", None),
    "near_miss": ("10:80000000D", T + timedelta(days=4, hours=12), 0.6, "fan_in",
                  (timedelta(days=3, hours=11), "STACK", "ACH")),  # outside the 72 h window
    "high_score": ("10:80000000E", T + timedelta(days=4, hours=12), 0.95, "fan_in", None),
    "ordinary": ("10:80000000F", T + timedelta(days=4, hours=12), 0.3, "fan_out", None),
    "test_split": ("10:800000010", T + timedelta(days=7, hours=12), 0.3, "fan_out", None),
    "hub": ("10:800000011", T + timedelta(days=2, hours=12), 0.6, "fan_in",
            (timedelta(hours=2), "FAN_IN", "ACH")),
    "heldout_cycle": ("10:800000012", T + timedelta(days=2, hours=12), 0.6, "fan_in",
                      (timedelta(hours=2), "CYCLE", "ACH")),
}  # fmt: skip
HUB = CASES["hub"][0]


def _alert_id(name: str) -> UUID:
    return UUID(int=list(CASES).index(name) + 1)


@pytest.fixture
def conn(scratch_database: Engine, tmp_path: Path) -> Iterator[psycopg.Connection[Any]]:
    """The crafted dataset, labelled and frozen by ``aml label`` into tmp_path/splits.json."""
    command.upgrade(alembic_config(MIGRATIONS), "head")
    accounts = {Z} | {case[0] for case in CASES.values()}
    tx_id = 0

    def add_tx(connection: Any, ts: datetime, src: str, dst: str, laundering: bool,
               pattern: str | None, fmt: str) -> int:  # fmt: skip
        nonlocal tx_id
        tx_id += 1
        connection.execute(
            text(
                "insert into transactions values (:id, :ts, :src, :dst, 5, 'USD', 5, 'USD', "
                ":fmt, :laundering, :pattern)"
            ),
            {"id": tx_id, "ts": ts, "src": src, "dst": dst, "fmt": fmt,
             "laundering": laundering, "pattern": pattern},
        )  # fmt: skip
        return tx_id

    with scratch_database.begin() as connection:
        for account in sorted(accounts):
            bank, number = account.split(":")
            connection.execute(
                text(
                    "insert into accounts (id, bank_id, account_number, entity_type, "
                    "kyc_profile, is_high_volume) "
                    "values (:id, :bank, :number, 'CORPORATION', :kyc, :hub)"
                ),
                {"id": account, "bank": bank, "number": number, "kyc": json.dumps(KYC),
                 "hub": account == HUB},
            )  # fmt: skip
        connection.execute(
            text("insert into settings values ('ANALYSIS_END', '\"2022-09-11T00:00:00Z\"')")
        )
        add_tx(connection, T, Z, CASES["ordinary"][0], False, None, "ACH")  # data starts 09-01
        for name, (account, at, score, rule, laundering) in CASES.items():
            cited = [add_tx(connection, at, Z, account, False, None, "WIRE")]
            if laundering is not None:
                before, pattern, fmt = laundering
                add_tx(connection, at - before, Z, account, True, pattern, fmt)
            add_tx(connection, at + timedelta(hours=1), account, Z, False, None, "CASH")  # later
            connection.execute(
                text(
                    "insert into alerts (id, account_id, rule_id, triggered_at, window_start, "
                    "window_end, score, reason, transaction_ids, idempotency_key) values (:id, "
                    ":account, :rule, :t, :t, :t + interval '1 minute', :score, 'r', :cited, :key)"
                ),
                {"id": _alert_id(name), "account": account, "rule": f"rules-v2:{rule}", "t": at,
                 "score": score, "cited": cited, "key": name},
            )  # fmt: skip
    with db.connect() as labelled:
        labels.run(labelled, path=tmp_path / "splits.json")
        yield labelled


def test_each_alert_lands_in_its_pool_and_the_rest_are_excluded(
    conn: psycopg.Connection[Any],
) -> None:
    pools = golden.pools(conn)

    found = {
        stratum: {(c.alert_id, c.group) for c in candidates}
        for stratum, candidates in pools.items()
    }
    assert found == {
        "positive_listed": {(_alert_id("listed"), "FAN_IN")},
        "positive_unlisted_non_ach": {(_alert_id("unlisted_wire"), "")},
        "negative_t01": {(_alert_id("t01"), T01)},
        "negative_near_miss": {(_alert_id("near_miss"), "")},
        "negative_high_score": {(_alert_id("high_score"), "")},
        "negative_ordinary": {(_alert_id("ordinary"), "rules-v2:fan_out")},
    }  # unlisted ACH, test split, hub and heldout_cycle alerts are in no pool


def test_a_short_pool_writes_no_sample(conn: psycopg.Connection[Any], tmp_path: Path) -> None:
    path = tmp_path / "golden_v1_sample.json"

    with pytest.raises(golden.GoldenError, match="candidates available"):
        golden.write_sample(conn, path, splits_path=tmp_path / "splits.json")
    assert not path.exists()


def test_the_sample_refuses_labels_that_moved_since_the_freeze(
    conn: psycopg.Connection[Any], tmp_path: Path
) -> None:
    conn.execute("update alerts set split = 'test' where id = %s", (_alert_id("ordinary"),))
    conn.commit()

    with pytest.raises(labels.LabelError, match="stored on alerts differ"):
        golden.build_sample(conn, splits_path=tmp_path / "splits.json")


@pytest.fixture
def api(conn: psycopg.Connection[Any], monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
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
    yield
    server.should_exit = True
    thread.join(timeout=10)
    database.reset()


@pytest.mark.usefixtures("api")
def test_the_screen_reads_the_alert_kyc_and_history_up_to_the_alert_through_the_api() -> None:
    at = CASES["listed"][1]

    view = label_cli.load_view(label_cli.ApiSource(), _alert_id("listed"))

    assert (view.alert.triggered_at, view.alert.window_end) == (at, at + timedelta(minutes=1))
    assert view.account.entity_name == "Corporation #7"
    assert view.account.kyc.country == "NG" and view.account.kyc.synthetic == KYC["synthetic"]
    assert not hasattr(view.account.kyc, "kyc_seed")
    # The account has 3 transactions; the one an hour after the alert is not shown.
    assert [t.ts for t in view.transactions] == [at - timedelta(hours=2), at]
    assert view.account.activity.sent_count == 1  # the profile itself counts all history
    assert view.counterparties.window_end == at + timedelta(minutes=1)
    assert [e.counterparty_id for e in view.counterparties.items] == [Z]


@pytest.mark.usefixtures("api")
def test_an_unknown_account_is_404() -> None:
    with pytest.raises(golden.GoldenError, match=r"does not exist"):
        label_cli.ApiSource().account("10:8ABCDEF")
