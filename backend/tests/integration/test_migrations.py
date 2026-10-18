"""Migration 0001: upgrade head -> downgrade base -> upgrade head, in a scratch database.

The round trip runs in its own database (same container) so it can't disturb the
session-wide migrated database that other integration tests use.
"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from testcontainers.community.postgres import PostgresContainer

from aml.common import get_settings
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


def _url(postgres: PostgresContainer, database: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=postgres.username,
        password=postgres.password,
        host=postgres.get_container_host_ip(),
        port=int(postgres.get_exposed_port(5432)),
        database=database,
    )


@pytest.fixture
def scratch_database(postgres: PostgresContainer) -> Iterator[Engine]:
    """An empty database for this test, with settings (and so Alembic) pointed at it."""
    name = f"roundtrip_{uuid4().hex[:12]}"
    admin = create_engine(_url(postgres, postgres.dbname), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(_url(postgres, name))
    with pytest.MonkeyPatch.context() as env:
        env.setenv("AML_POSTGRES_HOST", postgres.get_container_host_ip())
        env.setenv("AML_POSTGRES_PORT", str(postgres.get_exposed_port(5432)))
        env.setenv("POSTGRES_DB", name)
        get_settings.cache_clear()
        yield engine
    get_settings.cache_clear()
    engine.dispose()
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


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
        "version": {"0001"},
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
