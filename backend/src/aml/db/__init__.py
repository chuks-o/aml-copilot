"""Database access: engine and schema migrations (Alembic)."""

from pathlib import Path

from alembic import command
from alembic.config import Config


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
