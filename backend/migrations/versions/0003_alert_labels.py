"""Alert labels and the time split: created_at, heldout_cycle, dev/test, UNLISTED.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

- ``created_at``: when the alert row was written (wall clock). ``triggered_at`` becomes
  dataset time, the alert's latest cited transaction.
- ``heldout_cycle``: positives whose laundering is all CYCLE, never trained or tuned on.
- ``split`` values become ``dev`` / ``test`` (by time), and ``typology_label`` may be
  ``UNLISTED`` (laundering missing from the patterns file, 0003).

Rationale: docs/decisions/0029-labels-and-time-split.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
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


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(f"'{v}'" for v in values)})"


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.add_column(
        "alerts",
        sa.Column("heldout_cycle", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.drop_constraint("ck_alerts_split", "alerts", type_="check")
    op.create_check_constraint("ck_alerts_split", "alerts", _in("split", ("dev", "test")))
    op.drop_constraint("ck_alerts_typology_label", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alerts_typology_label", "alerts", _in("typology_label", (*TYPOLOGIES, "UNLISTED"))
    )
    # A label and its typology go together: typology only on positives.
    op.create_check_constraint(
        "ck_alerts_typology_label_on_positives",
        "alerts",
        "typology_label IS NULL OR label",
    )


def downgrade() -> None:
    op.drop_constraint("ck_alerts_typology_label_on_positives", "alerts", type_="check")
    op.drop_constraint("ck_alerts_typology_label", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alerts_typology_label", "alerts", _in("typology_label", TYPOLOGIES)
    )
    op.drop_constraint("ck_alerts_split", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alerts_split", "alerts", _in("split", ("train", "validation", "test"))
    )
    op.drop_column("alerts", "heldout_cycle")
    op.drop_column("alerts", "created_at")
