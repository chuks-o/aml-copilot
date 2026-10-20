"""Schema v1: dataset tables, case workflow, outbox, idempotency, typology docs.

Revision ID: 0001
Revises:
Create Date: 2026-10-18

Rationale for every choice here: docs/decisions/0022-schema-v1.md.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum values match backend/openapi.yaml (text + CHECK, not Postgres ENUM types).
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
ENTITY_TYPES = (
    "CORPORATION",
    "PARTNERSHIP",
    "SOLE_PROPRIETORSHIP",
    "INDIVIDUAL",
    "COUNTRY",
    "DIRECT",
)
PAYMENT_FORMATS = ("ACH", "BITCOIN", "CASH", "CHEQUE", "CREDIT_CARD", "REINVESTMENT", "WIRE")
ALERT_STATUSES = ("OPEN", "IN_CASE", "DISMISSED")
CASE_STATUSES = ("OPEN", "INVESTIGATING", "COMPLETE", "NEEDS_HUMAN", "ESCALATED", "CLOSED")
OUTCOMES = ("ESCALATE", "CLOSE")
SPLITS = ("train", "validation", "test")

# Monthly partitions of transactions: [start, end) in UTC. HI-Small spans 2022-09-01..18.
PARTITIONS = (("transactions_2022_09", "2022-09-01", "2022-10-01"),)

ACCOUNT_ID_PATTERN = "^(0|[1-9][0-9]*):[0-9A-F]+$"  # decision 0015
# OpenAPI Money: <= 18 integer digits, <= 8 fractional digits (Bitcoin uses 6).
MONEY = sa.Numeric(26, 8)
USD = sa.Numeric(12, 6)
EMBEDDING_DIMENSIONS = 1024


class Vector(sa.types.UserDefinedType[list[float]]):
    """pgvector's ``vector(n)``, enough for DDL (no pgvector Python package needed)."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        return f"vector({self.dimensions})"


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(f"'{v}'" for v in values)})"


def _created_at(name: str = "created_at") -> sa.Column[datetime]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _uuid_pk() -> sa.Column[uuid.UUID]:
    return sa.Column(
        "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------ dataset
    op.create_table(
        "accounts",
        sa.Column("id", sa.Text, nullable=False),
        sa.Column("bank_id", sa.Text, nullable=False),
        sa.Column("account_number", sa.Text, nullable=False),
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("kyc_profile", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_high_volume", sa.Boolean, nullable=False, server_default=sa.false()),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
        sa.UniqueConstraint("bank_id", "account_number", name="uq_accounts_bank_id_account_number"),
        sa.CheckConstraint(f"id ~ '{ACCOUNT_ID_PATTERN}'", name="ck_accounts_id_format"),
        sa.CheckConstraint("id = bank_id || ':' || account_number", name="ck_accounts_id_parts"),
        sa.CheckConstraint(_in("entity_type", ENTITY_TYPES), name="ck_accounts_entity_type"),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_settings"),
    )

    # Ingest supplies ids (the CSV row number, stable across reloads); new rows fall back to
    # the sequence. Postgres 16 has no identity columns on partitioned tables.
    op.execute("CREATE SEQUENCE transactions_id_seq AS bigint")
    op.create_table(
        "transactions",
        sa.Column(
            "id",
            sa.BigInteger,
            nullable=False,
            server_default=sa.text("nextval('transactions_id_seq')"),
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_account", sa.Text, nullable=False),
        sa.Column("to_account", sa.Text, nullable=False),
        sa.Column("amount_paid", MONEY, nullable=False),
        sa.Column("currency_paid", sa.Text, nullable=False),
        sa.Column("amount_received", MONEY, nullable=False),
        sa.Column("currency_received", sa.Text, nullable=False),
        sa.Column("payment_format", sa.Text, nullable=False),
        sa.Column("is_laundering", sa.Boolean, nullable=False),
        sa.Column("pattern", sa.Text, nullable=True),
        # Unique constraints on a partitioned table must include the partition key.
        sa.PrimaryKeyConstraint("id", "ts", name="pk_transactions"),
        sa.ForeignKeyConstraint(
            ["from_account"], ["accounts.id"], name="fk_transactions_from_account"
        ),
        sa.ForeignKeyConstraint(["to_account"], ["accounts.id"], name="fk_transactions_to_account"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_transactions_amount_paid"),
        sa.CheckConstraint("amount_received >= 0", name="ck_transactions_amount_received"),
        sa.CheckConstraint("currency_paid ~ '^[A-Z]{3}$'", name="ck_transactions_currency_paid"),
        sa.CheckConstraint(
            "currency_received ~ '^[A-Z]{3}$'", name="ck_transactions_currency_received"
        ),
        sa.CheckConstraint(
            _in("payment_format", PAYMENT_FORMATS), name="ck_transactions_payment_format"
        ),
        sa.CheckConstraint(
            _in("pattern", (*TYPOLOGIES, "UNLISTED")), name="ck_transactions_pattern"
        ),
        # pattern is null exactly for clean rows; 'UNLISTED' marks laundering rows that are
        # missing from the patterns file (0003).
        sa.CheckConstraint(
            "is_laundering = (pattern IS NOT NULL)", name="ck_transactions_pattern_iff_laundering"
        ),
        postgresql_partition_by="RANGE (ts)",
    )
    op.execute("ALTER SEQUENCE transactions_id_seq OWNED BY transactions.id")
    for name, start, end in PARTITIONS:
        op.execute(
            f"CREATE TABLE {name} PARTITION OF transactions "
            f"FOR VALUES FROM ('{start} 00:00+00') TO ('{end} 00:00+00')"
        )
    op.execute("CREATE TABLE transactions_default PARTITION OF transactions DEFAULT")
    # On the parent, so every partition gets them. Keyset order for both directions (0014).
    op.create_index(
        "ix_transactions_from_account_ts_id", "transactions", ["from_account", "ts", "id"]
    )
    op.create_index("ix_transactions_to_account_ts_id", "transactions", ["to_account", "ts", "id"])

    op.create_table(
        "ingest_quarantine",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("raw", JSONB, nullable=False),
        sa.Column("error", sa.Text, nullable=False),
        _created_at("received_at"),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_quarantine"),
    )

    # ------------------------------------------------------------- case workflow
    op.create_table(
        "alerts",
        _uuid_pk(),
        sa.Column("account_id", sa.Text, nullable=False),
        sa.Column("rule_id", sa.Text, nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Numeric(6, 5), nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="OPEN"),
        sa.Column("reason", sa.Text, nullable=False),
        # No FK: transactions' key is (id, ts), so id alone can't be referenced.
        sa.Column("transaction_ids", ARRAY(sa.BigInteger), nullable=False),
        # Evaluation ground truth: stored, never exposed by the API (0014 decision 11).
        sa.Column("label", sa.Boolean, nullable=True),
        sa.Column("typology_label", sa.Text, nullable=True),
        sa.Column("split", sa.Text, nullable=True),
        sa.Column("idempotency_key", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_alerts"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_alerts_account_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_alerts_idempotency_key"),
        sa.CheckConstraint("window_end > window_start", name="ck_alerts_window"),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name="ck_alerts_score"),
        sa.CheckConstraint(_in("status", ALERT_STATUSES), name="ck_alerts_status"),
        sa.CheckConstraint("cardinality(transaction_ids) >= 1", name="ck_alerts_transaction_ids"),
        sa.CheckConstraint(_in("typology_label", TYPOLOGIES), name="ck_alerts_typology_label"),
        sa.CheckConstraint(_in("split", SPLITS), name="ck_alerts_split"),
    )
    op.create_index("ix_alerts_account_id_triggered_at", "alerts", ["account_id", "triggered_at"])
    op.create_index("ix_alerts_status_triggered_at_id", "alerts", ["status", "triggered_at", "id"])

    op.create_table(
        "cases",
        _uuid_pk(),
        sa.Column("alert_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="OPEN"),
        sa.Column("decision", sa.Text, nullable=True),  # the copilot's proposal
        sa.Column("typology", sa.Text, nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        _created_at(),
        _created_at("updated_at"),
        sa.PrimaryKeyConstraint("id", name="pk_cases"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name="fk_cases_alert_id"),
        sa.UniqueConstraint("alert_id", name="uq_cases_alert_id"),
        sa.CheckConstraint(_in("status", CASE_STATUSES), name="ck_cases_status"),
        sa.CheckConstraint(_in("decision", OUTCOMES), name="ck_cases_decision"),
        sa.CheckConstraint(_in("typology", TYPOLOGIES), name="ck_cases_typology"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_cases_confidence"),
        sa.CheckConstraint("version >= 1", name="ck_cases_version"),
    )
    op.create_index("ix_cases_status_created_at_id", "cases", ["status", "created_at", "id"])
    op.create_index("ix_cases_typology_created_at_id", "cases", ["typology", "created_at", "id"])

    op.create_table(
        "case_events",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("actor", sa.Text, nullable=False),
        _created_at("at"),
        sa.PrimaryKeyConstraint("id", name="pk_case_events"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_case_events_case_id"),
    )
    op.create_index("ix_case_events_case_id_at_id", "case_events", ["case_id", "at", "id"])
    # Append-only, enforced for every role including the table owner (permissions aren't).
    op.execute(
        """
        CREATE FUNCTION case_events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'case_events is append-only: % is not allowed', TG_OP;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER case_events_no_update_or_delete BEFORE UPDATE OR DELETE ON case_events "
        "FOR EACH ROW EXECUTE FUNCTION case_events_append_only()"
    )
    op.execute(
        "CREATE TRIGGER case_events_no_truncate BEFORE TRUNCATE ON case_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION case_events_append_only()"
    )

    op.create_table(
        "analyst_decisions",
        _uuid_pk(),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("outcome", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("analyst_id", sa.Text, nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_analyst_decisions"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_analyst_decisions_case_id"),
        sa.UniqueConstraint("case_id", name="uq_analyst_decisions_case_id"),  # once per case (0017)
        sa.CheckConstraint(
            _in("action", ("APPROVE", "OVERRIDE")), name="ck_analyst_decisions_action"
        ),
        sa.CheckConstraint(_in("outcome", OUTCOMES), name="ck_analyst_decisions_outcome"),
        sa.CheckConstraint("length(reason) > 0", name="ck_analyst_decisions_reason"),
    )

    op.create_table(
        "agent_runs",
        _uuid_pk(),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="RUNNING"),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", USD, nullable=False, server_default="0"),
        _created_at("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_agent_runs_case_id"),
        sa.CheckConstraint(
            _in("status", ("RUNNING", "SUCCEEDED", "FAILED")), name="ck_agent_runs_status"
        ),
        sa.CheckConstraint("tokens >= 0 AND cost_usd >= 0", name="ck_agent_runs_usage"),
    )
    op.create_index("ix_agent_runs_case_id_started_at", "agent_runs", ["case_id", "started_at"])

    op.create_table(
        "agent_run_steps",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_no", sa.Integer, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", USD, nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        _created_at("started_at"),
        sa.PrimaryKeyConstraint("id", name="pk_agent_run_steps"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], name="fk_agent_run_steps_run_id", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("run_id", "step_no", name="uq_agent_run_steps_run_id_step_no"),
        sa.CheckConstraint(_in("kind", ("MODEL", "TOOL")), name="ck_agent_run_steps_kind"),
        sa.CheckConstraint("step_no >= 1", name="ck_agent_run_steps_step_no"),
        sa.CheckConstraint(
            "tokens >= 0 AND cost_usd >= 0 AND duration_ms >= 0", name="ck_agent_run_steps_usage"
        ),
    )

    # ---------------------------------------------------------------- plumbing
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("headers", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        _created_at(),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_outbox"),
    )
    # The relay's query: oldest unpublished first. Partial, so it stays small.
    op.create_index(
        "ix_outbox_unpublished",
        "outbox",
        ["created_at", "id"],
        postgresql_where=sa.text("published_at IS NULL"),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("request_hash", sa.Text, nullable=False),
        # Both null while the first request is still running (a retry then gets 409).
        sa.Column("response", JSONB, nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("key", name="pk_idempotency_keys"),
        sa.CheckConstraint(
            "(response IS NULL) = (status_code IS NULL)", name="ck_idempotency_keys_complete"
        ),
    )
    op.create_index(
        "ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"]
    )  # 24 h sweep

    op.create_table(
        "typology_docs",
        _uuid_pk(),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("chunk", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_typology_docs"),
    )


def downgrade() -> None:
    # Reverse order of upgrade(); leaves only alembic_version behind.
    op.drop_table("typology_docs")
    op.drop_table("idempotency_keys")
    op.drop_table("outbox")
    op.drop_table("agent_run_steps")
    op.drop_table("agent_runs")
    op.drop_table("analyst_decisions")
    op.drop_table("case_events")  # drops its triggers too
    op.execute("DROP FUNCTION case_events_append_only()")
    op.drop_table("cases")
    op.drop_table("alerts")
    op.drop_table("ingest_quarantine")
    op.drop_table("transactions")  # drops its partitions and the owned sequence
    op.drop_table("settings")
    op.drop_table("accounts")
    op.execute("DROP EXTENSION IF EXISTS vector")
