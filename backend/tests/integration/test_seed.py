"""``aml seed`` on the fixture dataset, in a scratch database: loads, reports, and is idempotent."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from sqlalchemy import Engine, text

from aml.data.seed import SeedError, seed
from aml.db import alembic_config
from tests.fixtures.postgres import MIGRATIONS

DATA = Path(__file__).resolve().parents[1] / "fixtures" / "data"


def _snapshot(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        return {
            "accounts": connection.execute(text("select * from accounts order by id")).all(),
            "transactions": connection.execute(
                text("select * from transactions order by id, ts")
            ).all(),
            "settings": connection.execute(text("select * from settings order by key")).all(),
            "next_id": connection.scalar(text("select last_value from transactions_id_seq")),
        }


def test_seed_loads_the_fixture_dataset(scratch_database: Engine) -> None:
    command.upgrade(alembic_config(MIGRATIONS), "head")

    report = seed(DATA, echo=lambda _: None, batch_size=50)

    assert report.tables["accounts"] == 15
    assert report.tables["transactions"] == 126
    assert report.partitions == {"transactions_2022_09": 126}
    assert report.analysis_end == datetime(2022, 9, 4, tzinfo=UTC)
    assert report.after_end == {"rows": 2, "laundering": 1, "clean": 1}
    assert report.high_volume_banks == {"70": 1}
    assert report.unlisted_by_format == {"CASH": 2}
    with scratch_database.connect() as connection:
        assert (
            connection.scalar(text("select value from settings where key = 'ANALYSIS_END'"))
            == "2022-09-04T00:00:00Z"
        )
        hub = connection.execute(
            text("select is_high_volume, kyc_profile from accounts where id = '70:ABC000001'")
        ).one()
        assert hub.is_high_volume is True
        # The load drops and rebuilds the secondary indexes: each must be back, valid, on
        # every partition (pg_get_indexdef's "ON ONLY" once rebuilt them on the parent alone).
        indexes = connection.execute(
            text(
                "select i.indexrelid::regclass::text, i.indisvalid, "
                "(select count(*) from pg_inherits c where c.inhparent = i.indexrelid) "
                "from pg_index i where i.indrelid = 'transactions'::regclass order by 1"
            )
        ).all()
        assert [tuple(r) for r in indexes] == [
            ("ix_transactions_from_account_ts_id", True, 2),
            ("ix_transactions_to_account_ts_id", True, 2),
            ("pk_transactions", True, 2),
        ]
        assert hub.kyc_profile["bank_name"] == "Test Bank #70"
        assert hub.kyc_profile["synthetic"] == [
            "business_type", "country", "expected_monthly_volume_band", "onboarded_at",
        ]  # fmt: skip


def test_seeding_twice_leaves_identical_data(scratch_database: Engine) -> None:
    command.upgrade(alembic_config(MIGRATIONS), "head")

    first_report = seed(DATA, echo=lambda _: None, batch_size=50)
    first = _snapshot(scratch_database)
    second_report = seed(DATA, echo=lambda _: None, batch_size=50)

    assert _snapshot(scratch_database) == first
    assert second_report.fingerprints == first_report.fingerprints


def test_seed_refuses_when_alerts_exist(scratch_database: Engine) -> None:
    command.upgrade(alembic_config(MIGRATIONS), "head")
    seed(DATA, echo=lambda _: None, batch_size=50)
    with scratch_database.begin() as connection:
        connection.execute(
            text(
                "insert into alerts (account_id, rule_id, triggered_at, window_start, window_end, "
                "reason, transaction_ids, idempotency_key) values ('70:ABC000001', 'r', now(), "
                "now() - interval '1 hour', now(), 'r', '{1}', 'k')"
            )
        )

    with pytest.raises(SeedError, match="alerts reference accounts"):
        seed(DATA, echo=lambda _: None, batch_size=50)
