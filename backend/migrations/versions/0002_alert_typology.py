"""alerts.typology: the scoring model's guess at the pattern (POST /alerts ``typology``).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

Kept apart from ``typology_label``, which is evaluation ground truth (0022); mixing a model's
guess into it would contaminate every evaluation. Rationale: docs/decisions/0025-idempotency.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of the typologies at this revision (migrations never import each other).
TYPOLOGIES = (
    "FAN_IN",
    "FAN_OUT",
    "CYCLE",
    "BIPARTITE",
    "STACK",
    "SCATTER_GATHER",
    "GATHER_SCATTER",
    "RANDOM",
)


def upgrade() -> None:
    op.add_column("alerts", sa.Column("typology", sa.Text, nullable=True))
    allowed = ", ".join(f"'{t}'" for t in TYPOLOGIES)
    op.create_check_constraint("ck_alerts_typology", "alerts", f"typology IN ({allowed})")


def downgrade() -> None:
    op.drop_constraint("ck_alerts_typology", "alerts", type_="check")
    op.drop_column("alerts", "typology")
