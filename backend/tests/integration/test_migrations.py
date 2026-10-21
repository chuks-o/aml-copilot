"""Migration 0001: upgrade head -> downgrade base -> upgrade head, in a scratch database.

The round trip runs in its own database (same container) so it can't disturb the
session-wide migrated database that other integration tests use.
"""

from alembic import command
from sqlalchemy import Engine, text

from aml.db import alembic_config
from tests.fixtures.postgres import MIGRATIONS

TABLES = {
    "accounts",
    "settings",
    "transactions",
    "ingest_quarantine",
    "alerts",
    "cases",
    "case_events",
    "analyst_decisions",
    "agent_runs",
    "agent_run_steps",
    "outbox",
    "idempotency_keys",
    "typology_docs",
}
PARTITIONS = {"transactions_2022_09", "transactions_default"}


def _schema(engine: Engine) -> dict[str, set[str]]:
    """What exists in the public schema, by kind."""
    queries = {
        # Ordinary and partitioned tables, but not partitions.
        "tables": "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where nspname = 'public' and relkind in ('r', 'p') and not relispartition",
        "partitions": "select inhrelid::regclass::text from pg_inherits "
        "where inhparent = to_regclass('public.transactions')",
        "sequences": "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where nspname = 'public' and relkind = 'S'",
        # Ours only: functions an extension installed (pgvector's) are owned by it ('e').
        "functions": "select proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where nspname = 'public' and not exists (select 1 from pg_depend d "
        "where d.objid = p.oid and d.deptype = 'e')",
        "extensions": "select extname from pg_extension where extname <> 'plpgsql'",
        "version": "select version_num from alembic_version",
    }
    with engine.connect() as connection:
        return {kind: set(connection.scalars(text(sql))) for kind, sql in queries.items()}


IDENTITY_SEQUENCES = {
    f"{t}_id_seq" for t in ("ingest_quarantine", "case_events", "agent_run_steps", "outbox")
}


def test_upgrade_downgrade_upgrade_round_trip(scratch_database: Engine) -> None:
    config = alembic_config(MIGRATIONS)
    upgraded = {
        "tables": TABLES | {"alembic_version"},
        "partitions": PARTITIONS,
        "sequences": {"transactions_id_seq"} | IDENTITY_SEQUENCES,
        "functions": {"case_events_append_only"},
        "extensions": {"vector"},
        "version": {"0002"},
    }

    command.upgrade(config, "head")
    assert _schema(scratch_database) == upgraded

    command.downgrade(config, "base")
    assert _schema(scratch_database) == {
        "tables": {"alembic_version"},
        "partitions": set(),
        "sequences": set(),
        "functions": set(),
        "extensions": set(),
        "version": set(),
    }

    command.upgrade(config, "head")
    assert _schema(scratch_database) == upgraded
