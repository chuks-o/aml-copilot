"""aml label end to end in a scratch database: labels, split, heldout_cycle, freeze, check."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest
from alembic import command
from sqlalchemy import Engine, text

from aml import db
from aml.db import alembic_config
from aml.evals import labels
from aml.evals.labels import LabelError
from tests.fixtures.postgres import MIGRATIONS

A, B, C, D, E = (f"10:80000000{n}" for n in range(5))
T = datetime(2022, 9, 1, tzinfo=UTC)
ALERTS = {
    # name: (alert id, account, triggered_at)
    "fan_in_positive": (UUID(int=1), A, T + timedelta(days=2, hours=9)),
    "cycle_only": (UUID(int=2), B, T + timedelta(days=7, hours=12)),
    "edge_negative": (UUID(int=3), C, T + timedelta(days=3)),
    "unlisted": (UUID(int=4), D, T + timedelta(days=8)),
}


@pytest.fixture
def conn(scratch_database: Engine) -> Iterator[psycopg.Connection[Any]]:
    command.upgrade(alembic_config(MIGRATIONS), "head")
    rows: list[tuple[int, datetime, str, str, bool, str | None]] = [
        (1, T, E, A, False, None),  # the first data row: the period starts 2022-09-01
        # A: two FAN_IN and one CYCLE laundering transaction within 72 h of its alert.
        (2, T + timedelta(days=1), E, A, True, "FAN_IN"),
        (3, T + timedelta(days=1, hours=1), E, A, True, "FAN_IN"),
        (4, T + timedelta(days=2), A, E, True, "CYCLE"),
        # B: only CYCLE (the account is the receiver).
        (5, T + timedelta(days=7), E, B, True, "CYCLE"),
        # C: laundering exactly 72 h before the alert is outside (t - 72 h, t].
        (6, T, E, C, True, "FAN_OUT"),
        # D: laundering missing from the patterns file.
        (7, T + timedelta(days=7, hours=20), D, E, True, "UNLISTED"),
    ]
    with scratch_database.begin() as connection:
        for account in (A, B, C, D, E):
            bank, number = account.split(":")
            connection.execute(
                text(
                    "insert into accounts (id, bank_id, account_number, entity_type) "
                    "values (:id, :bank, :number, 'CORPORATION')"
                ),
                {"id": account, "bank": bank, "number": number},
            )
        connection.execute(
            text("insert into settings values ('ANALYSIS_END', '\"2022-09-11T00:00:00Z\"')")
        )
        for tx_id, ts, src, dst, laundering, pattern in rows:
            connection.execute(
                text(
                    "insert into transactions values (:id, :ts, :src, :dst, 5, 'USD', 5, 'USD', "
                    "'ACH', :laundering, :pattern)"
                ),
                {
                    "id": tx_id,
                    "ts": ts,
                    "src": src,
                    "dst": dst,
                    "laundering": laundering,
                    "pattern": pattern,
                },
            )
        for alert_id, account, triggered_at in ALERTS.values():
            _insert_alert(connection, alert_id, account, triggered_at)
    with db.connect() as connection:
        yield connection


def _insert_alert(connection: Any, alert_id: UUID, account: str, triggered_at: datetime) -> None:
    connection.execute(
        text(
            "insert into alerts (id, account_id, rule_id, triggered_at, window_start, window_end, "
            "reason, transaction_ids, idempotency_key) values (:id, :account, 'rules-v1:fan_in', "
            ":t, :t - interval '1 day', :t + interval '1 minute', 'r', '{1}', :key)"
        ),
        {"id": alert_id, "account": account, "t": triggered_at, "key": str(alert_id)},
    )


def _stored(conn: psycopg.Connection[Any]) -> dict[UUID, tuple[Any, ...]]:
    rows = conn.execute(
        "select id, label, typology_label, split, heldout_cycle from alerts"
    ).fetchall()
    conn.rollback()
    return {r[0]: tuple(r[1:]) for r in rows}


def test_label_writes_labels_splits_and_the_frozen_file(
    conn: psycopg.Connection[Any], tmp_path: Path
) -> None:
    path = tmp_path / "splits.json"

    result = labels.run(conn, path=path)

    assert _stored(conn) == {
        ALERTS["fan_in_positive"][0]: (True, "FAN_IN", "dev", False),
        ALERTS["cycle_only"][0]: (True, "CYCLE", "test", True),
        ALERTS["edge_negative"][0]: (False, None, "dev", False),
        ALERTS["unlisted"][0]: (True, "UNLISTED", "test", False),
    }
    frozen = json.loads(path.read_text())
    assert frozen == result
    assert frozen["period"]["dev_end"] == "2022-09-07T00:00:00+00:00"
    assert frozen["splits"] == {
        "dev": {"alerts": 2, "positives": 1, "positive_rate": 0.5, "heldout_cycle": 0},
        "test": {"alerts": 2, "positives": 2, "positive_rate": 1.0, "heldout_cycle": 1},
    }
    assert labels.check(conn, path=path)["sha256"] == frozen["sha256"]


def test_check_fails_when_a_split_changes_without_the_hash(
    conn: psycopg.Connection[Any], tmp_path: Path
) -> None:
    path = tmp_path / "splits.json"
    labels.run(conn, path=path)
    # A hand-edited split (a test alert moved to dev) with splits.json left alone.
    conn.execute("update alerts set split = 'dev' where id = %s", (ALERTS["unlisted"][0],))
    conn.commit()

    with pytest.raises(LabelError, match="stored on alerts differ"):
        labels.check(conn, path=path)


def test_check_fails_when_the_data_would_relabel(
    conn: psycopg.Connection[Any], tmp_path: Path
) -> None:
    path = tmp_path / "splits.json"
    labels.run(conn, path=path)
    conn.execute(
        "insert into transactions values (8, %s, %s, %s, 5, 'USD', 5, 'USD', 'ACH', true, 'STACK')",
        (ALERTS["edge_negative"][2] - timedelta(hours=1), E, C),
    )
    conn.commit()

    with pytest.raises(LabelError, match="recomputed labels differ"):
        labels.check(conn, path=path)


def test_nothing_is_frozen_until_label_runs(conn: psycopg.Connection[Any], tmp_path: Path) -> None:
    with pytest.raises(LabelError, match="nothing is frozen yet"):
        labels.check(conn, path=tmp_path / "missing.json")


def test_an_alert_after_analysis_end_stops_labelling(
    conn: psycopg.Connection[Any], tmp_path: Path, scratch_database: Engine
) -> None:
    with scratch_database.begin() as connection:
        _insert_alert(connection, UUID(int=9), A, datetime(2022, 9, 11, 1, tzinfo=UTC))

    with pytest.raises(LabelError, match="at or after ANALYSIS_END"):
        labels.run(conn, path=tmp_path / "splits.json")
    assert not (tmp_path / "splits.json").exists()
