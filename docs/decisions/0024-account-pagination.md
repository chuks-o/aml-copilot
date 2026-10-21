# 0024 — Real account transactions and counterparties: keyset pagination over both sides

**Status:** Accepted · **Ticket:** T12 · **Date:** 2026-10-21

## Context

`GET /accounts/{id}/transactions` and `GET /accounts/{id}/counterparties` were stubs (0019). T12 serves them from the seeded database (0022, 0023), with keyset pagination on `(ts, id)` (0014), a cursor bound to its filters, and a total that's estimated above 10,000.

The hard case is the 15 bank-70 hubs. The largest, `70:100428660`, has 169,756 transactions, while the median account has 4. An account appears on *both* sides of its transactions (`from_account` or `to_account`), and 0022 indexed each side separately: `(from_account, ts, id)` and `(to_account, ts, id)`.

## Decision

1. **Each page is the `UNION ALL` of two index-ordered scans:**

   ```sql
   (SELECT … WHERE from_account = :a [AND window] [AND (ts, id) > (:ts, :id)] ORDER BY ts, id LIMIT :n)
   UNION ALL
   (SELECT … WHERE to_account = :a AND from_account <> :a … ORDER BY ts, id LIMIT :n)
   ORDER BY ts, id LIMIT :n
   ```

   - Each half walks its own index from the cursor position and reads at most `n` entries, and Postgres merges them (`Merge Append`). The `<>` keeps a self-transfer from appearing twice.
   - The page asks for `limit + 1` rows; the extra row says whether there's a next page.
   - The SQL is built by `transactions_query()` in `aml.api.repositories.accounts`, which the benchmark also `EXPLAIN`s, so the measured plan is the served plan.
2. **The cursor** is `base64url(JSON{"v": 1, "ts", "id", "f"})`, unpadded and **not signed**.
   - `f` is a 16-hex-digit SHA-256 of the canonical filters: `account`, `from`, `to`.
   - A cursor presented with different filters, or a malformed one (bad base64 or JSON, another version, naive `ts`, `id < 1`), returns **400**, problem+json.
   - `limit` is not part of the hash, so a client may change page size between pages.
3. **`limit` defaults to 100, maximum 500**, through a new `TransactionLimit` schema. `PageLimit` stays 50 for alerts and cases.
4. **Totals:**
   - A bounded exact count: each half is capped at 10,001 rows.
   - At or under 10,000 it's exact, with `total_is_estimate: false`.
   - Above that, it's the planner's estimate for the unbounded union (`EXPLAIN (FORMAT JSON)` `Plan Rows`, at least 10,001), with `total_is_estimate: true`.
   - The contract adds `TransactionPage.total_is_estimate` (required) and redefines `total` as "exact unless estimated", which makes it **0.3.0**.
5. **Unknown accounts are 404** (one primary-key lookup) on both endpoints, not an empty page.
6. **Counterparties:**
   - one edge per (counterparty, direction, currency) in `[as_of − window_hours, as_of)`, with `as_of` defaulting to now, as 0014 specifies;
   - `OUT` sums `amount_paid`, `IN` sums `amount_received`, and self-transfers are excluded;
   - edges are ordered by count desc, then counterparty, direction and currency;
   - `total_edges` is `count(*) OVER ()` over the groups, before `LIMIT`.
7. **Money is shown with trailing zeros trimmed, but never below two decimals:** `numeric(26,8)` `3697.34000000` → `3697.34`, `100.00000000` → `100.00`, `0.00000100` → `0.000001`. It still matches the `Money` pattern.
8. **Synchronous SQLAlchemy Core with `text()` SQL**, a pooled engine created lazily in `aml.api.database` (`pool_pre_ping`), and one connection per request through a FastAPI dependency in plain `def` routes, which run in FastAPI's thread pool. This settles the async question T09 deferred: sync, for now.
9. **Routes depend on an `AccountsRepository` protocol.** `SqlAccountsRepository` is the real one. The **contract test overrides it with an in-memory fake** (`tests/contract/fake_accounts.py`), so `make test` still needs no Docker (0020). The SQL is covered by `tests/integration/test_account_transactions.py`.
10. **Ruff `S608` is waived for `src/aml/api/repositories/**` only.** Queries there are assembled from constant fragments in the same module, and every value is a bound parameter.
11. **`GET /accounts/{id}` is still a placeholder.** The profile endpoint is wired when the KYC data is exposed.

## Evidence

**Concurrent inserts** (`test_paging_while_rows_are_inserted_has_no_duplicates_and_no_gaps`):
- The test pages through 5,000 rows touching one account (out, in and self, three per minute, so timestamps tie) at 100 per page, while another thread inserts rows into the same window.
- It asserts no duplicate ids, every original id present, `(ts, id)` order, and that the inserts overlapped the paging.
- With the keyset condition planted as `>=`, it fails: `a row appeared twice`, with 6,100 rows returned but only 6,040 distinct.

**`make bench-pagination`**, on the largest hub, 50 runs, 100 rows per page:

| Query | p95 |
| --- | --- |
| keyset, page 1 | 3.77 ms |
| keyset, last page (after row 169,655) | 5.84 ms |
| `OFFSET 169,656`, last page (10 runs) | 45.10 ms |
| total (estimate 168,381; exact 169,756) | 5.21 ms |

**The plan.** `EXPLAIN (ANALYZE, BUFFERS)` of the last keyset page shows, for both halves and both partitions, an `Index Scan using …_from_account_ts_id_idx` (and `…_to_account_ts_id_idx`) with `Index Cond: (from_account = … AND ROW(ts, id) > ROW(…))`. It returned `rows=100` with `shared hit=99` buffers, **execution 0.105 ms**. The rest of the 5.84 ms is client-side: building 100 response models. `OFFSET` is only 8× slower here because this hub is fully cached. Its cost grows with depth; keyset's doesn't.

## Alternatives

- **One `OR` query** (`from_account = A OR to_account = A`). Postgres gathers every row of the account with a bitmap and sorts on every page, so the cost is the account's size, not the page's.
- **A denormalised `account_transactions` table** with one row per side. It doubles 5M rows to serve what two indexes already do.
- **HMAC-signed cursors.** A secret to manage, for no security gain while there's no auth and tampering only moves the caller's own start position.
- **`limit` in the filter hash.** It would forbid a harmless change of page size.
- **Always-exact totals.** O(rows) on every page; for a hub, that's the cost keyset avoids.
- **A stored per-account count.** It goes stale with every insert.
- **Async database access** (psycopg async or asyncpg). Not needed yet, since every request is one or two indexed queries. Revisit if requests wait on slower I/O.
- **Moving the contract test to the integration tier** with a real database. It would put Docker into `make test`.
- **`as_of` defaulting to `ANALYSIS_END`.** Convenient for 2022 data, but it changes the contract's meaning.
- **Benchmarking over HTTP.** JSON serialisation noise would hide the query difference.

## Consequences

- Callers must treat `total` as approximate when `total_is_estimate` is true. The planner's estimate was 0.8% off for the largest hub.
- The BFF and the web client get `total_is_estimate` through `make codegen`. The console should show "~N" for estimated totals, as it already does for queue counts (0016).
- Counterparty queries on 2022 data need an explicit `as_of`. The default "now" window is empty.
- Any new account read goes in `aml.api.repositories`, with the same two-sided union shape when it touches transactions.
