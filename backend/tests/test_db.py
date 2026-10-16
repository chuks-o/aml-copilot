from pathlib import Path

from alembic.script import ScriptDirectory

from aml.db import alembic_config

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def test_migrations_dir_loads_and_has_no_revisions_yet() -> None:
    script = ScriptDirectory.from_config(alembic_config(MIGRATIONS))

    assert script.get_heads() == []
