"""Database access: engine and schema migrations (Alembic)."""

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg.rows import TupleRow

from aml.common import get_settings


def alembic_config(migrations_dir: Path) -> Config:
    """Alembic config built in code, so no alembic.ini is needed in the image.

    The database URL is read from settings by ``migrations/env.py``, never put in
    the config, so passwords containing ``%`` can't break config interpolation.
    """
    config = Config()
    config.set_main_option("script_location", str(migrations_dir))
    return config


def upgrade_to_head(migrations_dir: Path) -> None:
    command.upgrade(alembic_config(migrations_dir), "head")


def connect() -> psycopg.Connection[TupleRow]:
    """A psycopg connection to the configured database (for COPY, which SQLAlchemy doesn't wrap)."""
    url = get_settings().database_url.set(drivername="postgresql")
    return psycopg.connect(url.render_as_string(hide_password=False))
