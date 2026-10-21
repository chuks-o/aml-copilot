# 0026 — Transaction replayer: paced, batched, quarantined, resumable

**Status:** Accepted; decisions 3 (in-memory sort) and 8 (round-robin corruption) superseded by [0027](0027-streaming-replay.md) · **Ticket:** T14 · **Date:** 2026-10-21 · **Amends:** [0012](0012-working-rules.md) decision 2 (with [0023](0023-seed-and-download.md))

## Context

`aml seed` (0023) loads HI-Small in one go. T14 adds `aml replay`, which streams the same transactions as if they were arriving live, so scoring and alerting can run against a growing table. Requirements:
- timestamp order;
- a rate cap (default 2,000 tx/s) and a time-compression factor;
- `COPY` batches of 5,000 into a staging table, moved in one statement;
- malformed rows to `ingest_quarantine` with the reason;
- `--corrupt-rate` for testing;
- a progress report every 10 s.

Measured: **2,418,736 rows** of `HI-Small_Trans.csv` have an earlier timestamp than the row before them. The file isn't in time order, so file-position ids (0023) aren't either.

## Decision

1. **`aml.ingest` may import `aml.db`**, the second exception to 0012's database rule after `aml.data` (0023), for the same reason: bulk `COPY` can't go through REST. The import contract `db-belongs-to-api`, its architecture test and `CLAUDE.md` list both bulk loaders.
2. **Replay and seed are alternatives.**
   - Replay writes exactly the seed's rows: file-position ids, original 2022 timestamps, normalised accounts (0015), currency codes, pattern labels (0003).
   - It needs accounts but no transactions: `aml seed --accounts-only` loads accounts and `settings` and leaves `transactions` empty.
   - Rows already present are skipped (`ON CONFLICT (id, ts) DO NOTHING`) and counted as duplicates.
   - The seed deletes `REPLAY_POSITION`, since it has just replaced the table.
3. **Order:** all rows sorted in memory by `(original ts, id)`, a stable sort, about 2.3 GB peak like the seed.
4. **Pacing:**
   - **The rule:** a row is due at `max(i / rate, (ts − first_ts) / compression)` seconds after the start. Either term is off at 0. Both terms only increase, so due times do too.
   - **Defaults:** `--rate 2000`, `--compression 0`.
   - **Batches:** due rows are written up to 5,000 per batch, and flushed early once the oldest due row has waited 1 s, so slow paces still write promptly.
   - **Why both knobs:** compression keeps the data's rhythm (one wall second plays `compression` dataset seconds), and the rate cap bounds bursts. On Sept 1, a single dataset day has more than a million rows.
5. **One transaction per batch:**
   1. format-check the rows in Python;
   2. `COPY` the valid ones into the session's `TEMP` table `replay_staging` (`LIKE transactions INCLUDING DEFAULTS` plus `raw jsonb`, `ON COMMIT DELETE ROWS`);
   3. **one statement** (a CTE) inserts rows whose two accounts exist into `transactions`, and inserts the rest into `ingest_quarantine` as `unknown account <id>`;
   4. insert the format failures into `ingest_quarantine`;
   5. set `settings.REPLAY_POSITION = {ts, id}` of the batch's last row (in original sort order, so a corrupted timestamp doesn't break it);
   6. commit.

   A crash loses at most the batch in flight, and the next run resumes strictly after the watermark. `--from-start` ignores it.
6. **Validation is split by what knows the rule.**
   - **Format, in Python,** reusing `aml.data.dataset`'s mappings:
     - the timestamp parses as `YYYY/MM/DD HH:MM`;
     - amounts are non-negative decimals;
     - both currencies and the payment format are known;
     - `Is Laundering` is 0 or 1.

     The first failing check gives the error, for example `unknown currency 'Dogecoin' in Payment Currency`, `negative amount '-123.45' in Amount Paid`, or `unparsable timestamp '2022/13/45 25:99'`.
   - **Referential, in SQL,** inside the move statement, so an unknown account quarantines its row instead of aborting the batch on a foreign-key error.
   - The Python checks are needed, not belt-and-braces: with the negative-amount check planted out, the integration test fails because one bad row hits `ck_transactions_amount_paid` and **aborts the whole batch**.
7. **Quarantine `raw`** holds the received fields (our column names, from 0023's header mapping) plus the row's `id`. That's enough to find the original line.
8. **Corruption** (`--corrupt-rate`, `--seed`, default 42):
   - It replaces one field of each chosen row, round-robin in file order: unknown currency, negative amount, unparsable timestamp.
   - Rows are chosen per **file position** (one draw per row of the whole file), so `--limit` and resuming never change which rows are damaged.
   - A corrupted row is quarantined instead of committed; its valid version is never written.
9. **Progress** every 10 s, and once at the end: a structured log event (`replay_progress` / `replay_finished`: `rows_per_s`, `committed`, `quarantined`, `duplicates`, `batch_ms_p50`, `batch_ms_p95`, `position`) and a summary line on stdout.
10. **SQL composed from module constants**, so Ruff `S608` is waived for `src/aml/ingest/**`, as for the repositories (0024).

## Evidence

`tests/integration/test_replayer.py` builds a HI-Small-shaped file in a temp directory (shuffled out of time order, timestamp ties, zero-padded banks, about 0.2% laundering) and replays it against real Postgres, unthrottled:

| Test | Shows |
| --- | --- |
| 20,000 rows, 1% corruption (seed 42) | committed ids = all ids − corrupted; quarantined ids = corrupted; the three reasons evenly spread (round-robin); laundering rows labelled `UNLISTED`; the watermark equals the last row; progress and done lines printed |
| commit order | 3,000 rows at 500 per batch: 6 transactions (`xmin`), each batch's earliest `ts` ≥ the previous batch's latest |
| resume | `--limit 2000`, then a full run, then another: 2,000 + 3,000 + 0, ids exactly 1..5,000; `--from-start` adds 0 and counts 5,000 duplicates |
| unknown accounts | 3 rows quarantined as `unknown account 999:8FFFFFFFF`; the other 997 committed |

**Real data:** `aml replay --limit 50000 --corrupt-rate 0.01` at the default 2,000 rows/s. It ran in a throwaway database holding the 57,039 accounts those rows reference, not on the seeded stack.

```
progress: 1,964.6 rows/s, 19,804 committed, 206 quarantined, 0 duplicates, batch p50 185.2 ms p95 499.3 ms
progress: 1,998.6 rows/s, 39,612 committed, 408 quarantined, 0 duplicates, batch p50 184.2 ms p95 223.2 ms
done: 1,998.2 rows/s, 49,512 committed, 488 quarantined, 0 duplicates, batch p50 191.9 ms p95 215.4 ms
replayed 49,512 committed, 488 quarantined, 0 duplicates in 25 batches, 25.19 s
```

- **Coverage:** the 50,000 rows span 2022-09-01 00:00–00:04, the start of the 1.1M-row first day.
- **Quarantine:** negative amount 163, unknown currency 174, unparsable timestamp 151. That's uneven because round-robin runs in file order while the first rows *by time* are a scattered sample of the file.
- **Batch size:** about 2,000 rows, not 5,000. At 2,000 rows/s the 1 s flush fires first, which is decision 4's purpose: due rows are written within a second. Full 5,000-row batches appear above 5,000 rows/s.
- **Memory:** a peak resident size of 2.33 GB. macOS swap grew by 1.1 GB and free disk fell by the same, confirming the memory consequence below.

The unit tests (`tests/unit/test_replayer.py`) cover the `(ts, id)` order, the pacing maths (even spacing; compression keeps rhythm; the rate caps a burst), corruption determinism across `--limit`, and each error message.

## Alternatives

- **A bulk-insert REST endpoint.** 5,000-row JSON batches, losing `COPY`'s speed.
- **Putting the replayer in `aml.data`.** Against the ticket and the package's purpose.
- **Shifting timestamps to "now".** It breaks `ANALYSIS_END`, the partitions, and the ids and timestamps agent citations rely on.
- **Compression only.** Busy dataset hours would flood the database.
- **All validation in SQL.** The mapping tables would be duplicated in SQL, and a bad date aborts the statement without a safe-parse function.
- **All validation in Python.** An unknown account would abort the move statement on its foreign key.
- **A permanent `UNLOGGED` staging table.** Shared between replayers, and it needs a migration.
- **No watermark.** A restart means starting over or guessing.
- **Corruption chosen per run.** A test couldn't predict which rows are damaged after `--limit` or a resume.
- **An external merge sort.** Not needed at 5M rows, though see Consequences.

## Consequences

- **Memory.** Like `aml seed`, `aml replay` holds the whole sorted file in memory, about 2.3 GB. On the development Mac, that pushed about 1.5 GB into macOS swap each time. Swap lives on the same disk, which explains the repeated low-disk incidents since T11. If this becomes a problem, the cheapest fix is a narrower load (only the needed columns, pyarrow-backed strings); the next is an external sort.
- **Gradual demos:** `aml seed --accounts-only` then `aml replay`. To restore the full table at once: `aml seed`.
- Replayed rows arrive in `(ts, id)` order with original 2022 timestamps, so `ANALYSIS_END` still applies downstream.
