"""aml replay against real Postgres: commits valid rows, quarantines corrupt ones, resumes."""

import csv
import random
from collections.abc import Iterator
from datetime import datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import Engine, text

from aml.data import dataset
from aml.db import alembic_config
from aml.ingest.replayer import ReplayConfig, replay
from tests.fixtures.postgres import MIGRATIONS

ROWS = 20_000
ACCOUNTS = [(f"{bank:03d}", f"8{n:08X}") for bank in (10, 20, 70) for n in range(60)]
UNLIMITED = ReplayConfig(rate=0, corrupt_rate=0.01, seed=42, report_every=0)


def _write_dataset(directory: Path, rows: int, unknown_account_rows: int = 0) -> None:
    """A HI-Small-shaped file: out of time order, with timestamp ties and padded banks."""
    rng = random.Random(3)  # noqa: S311 - test data, not secrets
    start = datetime(2022, 9, 1)
    lines = []
    for n in range(rows):
        (src_bank, src), (dst_bank, dst) = rng.sample(ACCOUNTS, 2)
        if n < unknown_account_rows:
            dst_bank, dst = "999", "8FFFFFFFF"
        ts = start + timedelta(minutes=rng.randrange(60 * 24 * 9))
        label = "1" if rng.random() < 0.002 else "0"
        amount = f"{rng.uniform(1, 9000):.2f}"
        lines.append(
            [ts.strftime("%Y/%m/%d %H:%M"), src_bank, src, dst_bank, dst, amount, "US Dollar",
             amount, "US Dollar", rng.choice(["ACH", "Wire", "Cheque"]), label]
        )  # fmt: skip
    with (directory / dataset.TRANSACTIONS_FILE).open("w", newline="") as f:
        csv.writer(f).writerows([list(dataset.TRANSACTION_HEADER), *lines])
    (directory / dataset.PATTERNS_FILE).write_text("")  # laundering rows become UNLISTED


@pytest.fixture
def stream(scratch_database: Engine, tmp_path: Path) -> Iterator[Path]:
    """A migrated scratch database holding the accounts; the dataset file in tmp_path."""
    command.upgrade(alembic_config(MIGRATIONS), "head")
    with scratch_database.begin() as connection:
        for bank, number in ACCOUNTS:
            connection.execute(
                text(
                    "insert into accounts (id, bank_id, account_number, entity_type) "
                    "values (:id, :bank, :number, 'CORPORATION')"
                ),
                {"id": f"{bank.lstrip('0')}:{number}", "bank": bank.lstrip("0"), "number": number},
            )
    yield tmp_path


def _ids(engine: Engine, sql: str) -> set[int]:
    with engine.connect() as connection:
        return {int(i) for i in connection.scalars(text(sql))}


def test_replay_commits_valid_rows_and_quarantines_corrupted_ones(
    stream: Path, scratch_database: Engine
) -> None:
    _write_dataset(stream, ROWS)
    progress: list[str] = []

    report = replay(stream, UNLIMITED, echo=progress.append)

    corrupted = set(report.corrupted_ids)
    committed = _ids(scratch_database, "select id from transactions")
    quarantined = _ids(scratch_database, "select (raw->>'id')::bigint from ingest_quarantine")
    assert 150 < len(corrupted) < 250  # about 1% of 20,000
    assert committed == set(range(1, ROWS + 1)) - corrupted
    assert quarantined == corrupted
    assert (report.committed, report.quarantined, report.duplicates) == (
        ROWS - len(corrupted),
        len(corrupted),
        0,
    )
    with scratch_database.connect() as connection:
        reasons: dict[str, int] = dict(
            connection.execute(
                text(
                    "select split_part(error, ' ''', 1), count(*) from ingest_quarantine group by 1"
                )
            ).all()
        )
        unlisted = connection.scalar(
            text("select count(*) from transactions where is_laundering and pattern = 'UNLISTED'")
        )
        position = connection.scalar(
            text("select value from settings where key = 'REPLAY_POSITION'")
        )
    assert set(reasons) == {"unknown currency", "negative amount", "unparsable timestamp"}
    assert max(reasons.values()) - min(reasons.values()) <= 1  # round-robin
    assert unlisted and unlisted > 0
    assert position == report.position
    assert any(line.startswith("progress:") and "rows/s" in line for line in progress)
    assert progress[-1].startswith("done:")


def test_rows_are_committed_in_timestamp_order(stream: Path, scratch_database: Engine) -> None:
    _write_dataset(stream, 3_000)

    replay(stream, ReplayConfig(rate=0, batch_size=500), echo=lambda _: None)

    with scratch_database.connect() as connection:
        # xmin is the inserting transaction: one per batch, in commit order.
        batches = connection.execute(
            text(
                "select xmin::text::bigint as tx, min(ts) as first, max(ts) as last "
                "from transactions group by 1 order by 1"
            )
        ).all()
    assert len(batches) == 6
    for earlier, later in pairwise(batches):
        assert earlier.last <= later.first


def test_a_stopped_replay_resumes_after_its_position_and_adds_nothing_twice(
    stream: Path, scratch_database: Engine
) -> None:
    _write_dataset(stream, 5_000)

    first = replay(stream, ReplayConfig(rate=0, limit=2_000), echo=lambda _: None)
    rest = replay(stream, ReplayConfig(rate=0), echo=lambda _: None)
    again = replay(stream, ReplayConfig(rate=0), echo=lambda _: None)
    from_start = replay(stream, ReplayConfig(rate=0, from_start=True), echo=lambda _: None)

    assert (first.committed, rest.committed, again.committed) == (2_000, 3_000, 0)
    assert _ids(scratch_database, "select id from transactions") == set(range(1, 5_001))
    assert (from_start.committed, from_start.duplicates) == (0, 5_000)


def test_rows_with_unknown_accounts_are_quarantined_not_fatal(
    stream: Path, scratch_database: Engine
) -> None:
    _write_dataset(stream, 1_000, unknown_account_rows=3)

    report = replay(stream, ReplayConfig(rate=0), echo=lambda _: None)

    assert (report.committed, report.quarantined) == (997, 3)
    with scratch_database.connect() as connection:
        errors = set(connection.scalars(text("select error from ingest_quarantine")))
    assert errors == {"unknown account 999:8FFFFFFFF"}
