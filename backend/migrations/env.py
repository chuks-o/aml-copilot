"""Alembic environment. Run via ``aml migrate``; the URL comes from aml settings."""

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from aml.common import get_settings

target_metadata = None  # set to the SQLAlchemy MetaData once models exist (T10)


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, poolclass=NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) migrations are not supported; run `aml migrate`.")
run_migrations_online()
