# migrations

Alembic migrations, applied by `aml migrate` (`make migrate` locally; the one-shot `migrate` container in Docker Compose; the `migrated_engine` test fixture).

Alembic is configured in code (`aml.db.alembic_config`), so there is no `alembic.ini`. `env.py` reads the database URL from `aml.common.Settings`.

| Revision | What |
| --- | --- |
| `0003` | `alerts.created_at` (wall clock), `alerts.heldout_cycle`; `split` is `dev`/`test`; `typology_label` may be `UNLISTED`. See [decision 0029](../../docs/decisions/0029-labels-and-time-split.md). |
| `0002` | `alerts.typology`: the scoring model's guess, kept apart from the ground-truth `typology_label`. See [decision 0025](../../docs/decisions/0025-idempotency.md). |
| `0001` | Schema v1: accounts, settings, monthly-partitioned transactions, ingest quarantine, alerts, cases, case events, analyst decisions, agent runs and steps, outbox, idempotency keys, typology docs. See [decision 0022](../../docs/decisions/0022-schema-v1.md). |

## Adding a revision

Migrations are handwritten (there are no SQLAlchemy models to autogenerate from yet). Name the file `NNNN_short_name.py`, set `revision = "NNNN"` and `down_revision` to the previous one, and give every constraint and index an explicit name (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`). `downgrade()` must undo `upgrade()` exactly: `tests/integration/test_migrations.py` runs upgrade → downgrade → upgrade and compares what exists after each step.

## Adding a month to `transactions`

Rows outside every month land in `transactions_default`. Before inserting a new month's data, add its partition in a new revision:

```python
op.execute(
    "CREATE TABLE transactions_2022_10 PARTITION OF transactions "
    "FOR VALUES FROM ('2022-10-01 00:00+00') TO ('2022-11-01 00:00+00')"
)
```

Postgres rejects this if `transactions_default` already holds rows for that month. Move them out first (detach the default, create the month, re-insert, re-attach), which is why the default should stay close to empty.
