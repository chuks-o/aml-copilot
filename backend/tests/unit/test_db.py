from pathlib import Path

from alembic.script import ScriptDirectory

from aml.db import alembic_config

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def test_migrations_form_one_linear_history_ending_at_0001() -> None:
    script = ScriptDirectory.from_config(alembic_config(MIGRATIONS))

    assert script.get_heads() == ["0001"]
    assert [r.revision for r in script.walk_revisions()] == ["0001"]
