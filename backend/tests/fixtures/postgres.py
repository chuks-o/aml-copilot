"""Postgres 16 + pgvector in a container, migrated once per session.

``db`` gives each test a connection inside a transaction that is always rolled back, so
tests share the container but never see each other's rows.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, create_engine
from testcontainers.community.postgres import PostgresContainer

from aml.common import get_settings
from aml.db import upgrade_to_head
from tests.fixtures.docker import TEST_PASSWORD, TEST_USER, require_docker

# Same image as infra/docker-compose.yml (tests/unit/test_fixture_images.py keeps them equal).
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


@pytest.fixture(scope="session")
def postgres() -> Iterator[PostgresContainer]:
    require_docker()
    container = PostgresContainer(
        POSTGRES_IMAGE, username=TEST_USER, password=TEST_PASSWORD, dbname="aml", driver=None
    )
    with container:
        yield container


@pytest.fixture(scope="session")
def migrated_engine(postgres: PostgresContainer) -> Iterator[Engine]:
    """Settings pointed at the container, then the real ``aml migrate`` code path."""
    with pytest.MonkeyPatch.context() as env:
        env.setenv("AML_POSTGRES_HOST", postgres.get_container_host_ip())
        env.setenv("AML_POSTGRES_PORT", str(postgres.get_exposed_port(5432)))
        env.setenv("POSTGRES_USER", postgres.username)
        env.setenv("POSTGRES_PASSWORD", postgres.password)
        env.setenv("POSTGRES_DB", postgres.dbname)
        get_settings.cache_clear()
        upgrade_to_head(MIGRATIONS)
        engine = create_engine(get_settings().database_url)
        yield engine
        engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Connection]:
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
