# 0022 — Schema v1 (migration 0001)

**Status:** Accepted · **Ticket:** T10 · **Date:** 2026-10-18

## Context

T10 creates the first real schema: dataset tables (accounts, monthly-partitioned transactions, quarantine, settings), the case workflow (alerts, cases, events, decisions, agent runs and steps), plumbing (a transactional outbox, idempotency keys) and `typology_docs` with a pgvector embedding. Two facts, measured on `HI-Small_Trans.csv`, shaped it:

- **Amounts:** the largest has 13 integer digits (`1046302363293.48`). 294,217 Bitcoin amount values carry 6 decimals, many as small as `0.000001`.
- **Time range:** every row falls between 2022-09-01 00:00 and 2022-09-18 16:18, a single month.

## Decision

The full DDL is `backend/migrations/versions/0001_schema_v1.py`. The choices:

1. **Amounts are `numeric(26,8)`**, not the ticket's `numeric(18,2)`, which would round every sub-cent Bitcoin amount to `0.00`. `(26,8)` is exactly the OpenAPI `Money` pattern (≤ 18 integer digits, ≤ 8 decimals). `tests/integration/test_schema_v1.py` stores `0.000001` BTC and reads it back exactly.
2. **One alert per case** (`cases.alert_id UNIQUE`), as the ticket specifies. This **contradicts REST** (0014), where `CaseCreate.alert_ids` and `Case.alert_ids` are arrays. GraphQL already exposes one `Case.alert`. REST changes to a single `alert_id` (contract 0.3.0) in the ticket that wires routes to the database, where the stubs change anyway.
3. **`alerts` gains `status`, `reason` and `transaction_ids`**, which the REST `Alert` requires. `rule_id` serves as REST's `model_version`, and `triggered_at` as `created_at`. `transaction_ids` is `bigint[]` with no foreign key, because `transactions`' key is `(id, ts)`, so `id` alone can't be referenced.
4. **Ground truth is stored but never exposed:** `transactions.is_laundering` and `pattern`, and `alerts.label`, `typology_label` and `split` (`train` / `validation` / `test`). This follows 0014 decision 11.
5. **`pattern` is null exactly for clean rows** (`CHECK (is_laundering = (pattern IS NOT NULL))`). It's one of the 8 typology names (OpenAPI spelling, `FAN_IN`) or `'UNLISTED'` for laundering rows missing from the patterns file (0003).
6. **Enums are `text` + `CHECK`**, with values matching OpenAPI, not Postgres `ENUM` types. A CHECK changes with one transactional `ALTER`; an ENUM can't drop values.
7. **`transactions` is `PARTITION BY RANGE (ts)`** with `transactions_2022_09` plus `transactions_default`.
   - The primary key is `(id, ts)`, because unique constraints on a partitioned table must include the partition key.
   - The indexes `(from_account, ts, id)` and `(to_account, ts, id)` are on the parent, so every partition gets them. They serve keyset pagination per account and direction (0014).
   - Bounds are written with `+00`, so they don't depend on the server's `TimeZone`.
   - `backend/migrations/README.md` shows how to add a month.
8. **Transaction ids come from ingest** (the CSV row number, stable across reloads, since alerts and claims cite them), with `nextval('transactions_id_seq')` as the default for new rows. The sequence is `OWNED BY transactions.id`, so dropping the table drops it. Postgres 16 has no identity columns on partitioned tables; that arrives in 17.
9. **Foreign keys from `transactions` to `accounts`.** They make bulk loads slower and require accounts to be loaded first, but an unknown account id is a correctness bug under 0015.
10. **`accounts.id` is checked against 0015's format** (`^(0|[1-9][0-9]*):[0-9A-F]+$`) and against its parts (`id = bank_id || ':' || account_number`). `kyc_profile jsonb` holds `bank_name`, `entity_id` and `entity_name`.
11. **`case_events` is append-only, enforced by triggers.** `UPDATE` and `DELETE` (row-level) and `TRUNCATE` (statement-level) raise `case_events is append-only`. The app connects as the table owner, so `REVOKE` wouldn't bind it.
12. **Once-only rules are constraints:** `uq_cases_alert_id`, `uq_analyst_decisions_case_id` (one decision per case, 0017), `uq_agent_run_steps_run_id_step_no` and `uq_alerts_idempotency_key`.
13. **The outbox has a partial index** `(created_at, id) WHERE published_at IS NULL`, for the relay's "oldest unpublished" query, so the index stays small as published rows accumulate.
14. **`idempotency_keys`:** `response` and `status_code` are both null while the first request is in flight (a retry gets 409), and both set when it's done (`ck_idempotency_keys_complete`). Indexed on `created_at` for the 24 h sweep.
15. **pgvector:** `CREATE EXTENSION IF NOT EXISTS vector` in `upgrade()`, dropped in `downgrade()`. `typology_docs.embedding` is `vector(1024)`, and a wrong dimension is rejected (tested). There's no ANN index: a few hundred chunks scan faster than an index. 1,024 dimensions commits us to an embedding model of that size; the RAG ticket confirms which.
16. **Defaults:** `timestamptz` everywhere with `now()`, UUIDs default to `gen_random_uuid()` (the app may supply its own, as T08's idempotent ids do), and other tables use `bigint` identity columns. Every constraint and index has an explicit name (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`).
17. **Handwritten migration, no autogenerate.** There are no SQLAlchemy models yet (`env.py` `target_metadata = None`); they arrive with the repository code. `downgrade()` drops everything in reverse, down to a schema holding only `alembic_version`.
18. **Round-trip test** (`tests/integration/test_migrations.py`): upgrade head → downgrade base → upgrade head, in a scratch database (`CREATE DATABASE` in the session container), so the shared migrated database is untouched. After each step it compares the exact sets of tables, partitions, sequences, non-extension functions, extensions and `alembic_version`. A planted incomplete `downgrade()` (not dropping `outbox`) fails it with `{'alembic_version', 'outbox'} != {'alembic_version'}`.

## Alternatives

- **`numeric(18,2)`** loses Bitcoin data. **Unconstrained `numeric`** stops enforcing the contract's limits.
- **An `alert_cases` join table** (many alerts per case) keeps REST as it is but contradicts the ticket's `alert_id unique`.
- **An `alert_transactions` link table** would need `ts` copied in, only to satisfy `transactions`' composite key.
- **Postgres `ENUM` types.** Values can't be removed, and adding them is awkward in transactional migrations.
- **`pg_partman` or a partition-creating function.** Machinery for a dataset that spans one month.
- **No foreign keys on `transactions`.** Faster loads, but unknown accounts get in silently.
- **`REVOKE UPDATE, DELETE` for append-only.** It doesn't bind the owner role the app uses.
- **An HNSW index on `embedding` now.** Slower than a scan at this size; add it when the corpus grows.
- **An identity column for `transactions.id`.** Not supported on partitioned tables in Postgres 16, and it would make ingest's explicit ids awkward.
- **Autogenerated migrations.** No models to generate from yet.
- **The round trip in the shared test database.** It would wipe the schema other integration tests rely on.

## Consequences

- **REST has to change before routes use the database:** `alert_ids` becomes `alert_id` (decision 2). Until then the stubs and the schema disagree on that one field.
- **Still missing from the schema:** the case-file data 0016 lists (`claims`, `missing_evidence`) and REST's `Recommendation.created_at`. The investigator ticket adds them in a later revision.
- **Ingest has to:**
  - load accounts first;
  - normalise bank codes (0015);
  - map currency names to codes and payment formats to the enum spelling;
  - use the CSV row number as the transaction id;
  - write `pattern`, including `'UNLISTED'`;
  - after loading with explicit ids, call `setval('transactions_id_seq', max(id))`.
- **Data outside September 2022 lands in `transactions_default`.** Add a month partition first (README) for replays that shift time.
