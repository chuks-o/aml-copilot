# 0025 — Idempotency-Key: one transaction, wait on the row lock, replay exact bytes

**Status:** Accepted · **Ticket:** T13 · **Date:** 2026-10-21

## Context

0014 decision 4 requires an `Idempotency-Key` on every POST and specifies the outcomes: replay, 422 for a reused key, 409 while in flight, 24 h retention. The `idempotency_keys` table exists (0022): `key` primary key, `request_hash`, `response jsonb`, `status_code`, `created_at`. T13 implements this for `POST /alerts`, `POST /cases` and `POST /cases/{id}/decisions`.

All three POSTs were stubs (0019) with no database write. Scope **A** was chosen: `POST /alerts` (and `GET /alerts/{id}`) become real writes. The two case POSTs go through the same idempotency layer, but keep placeholder bodies until the case-workflow ticket, which also turns REST's `alert_ids` into `alert_id` (0022).

## Decision

1. **The claim and the write share one transaction.** `idempotent()` in `aml.api.unit_of_work` opens the transaction, then:
   1. claims the key: `INSERT … ON CONFLICT (key) DO UPDATE … WHERE created_at < now() − 24 h RETURNING key`;
   2. on a fresh claim, runs the write and stores the response with `UPDATE`, then commits;
   3. otherwise, replays the stored response.

   The key and the alert row commit together or not at all.
2. **Concurrency: wait on the row lock, 409 only after `lock_timeout`.**
   - While the first request is uncommitted, its key row is locked. A duplicate's insert **blocks** on it: Postgres's own unique-index wait, with no polling.
   - When the first commits, the duplicate replays its response. If it rolled back, the duplicate proceeds as the first.
   - `SET LOCAL lock_timeout = '5s'`: a duplicate still waiting after 5 s gets **409** problem+json ("still in progress"), from SQLSTATE `55P03`.
   - **Chosen over** an immediate 409, which needs the "in progress" marker committed *before* the write in its own transaction. That breaks decision 1, and a crash between the two leaves a key stuck in progress until it expires.
   - A retry a few milliseconds late, the common case, now gets the real answer instead of an error.
3. **The fingerprint** is `sha256` over `{method, path, body}`. The body is the *validated* request model, canonicalised: object keys sorted, set members (`transaction_ids`, `alert_ids`) sorted, and UUIDs, dates and enums as strings. Key order, whitespace and set order are therefore the same request, while a different value, path or method is a different one (**422**, problem+json).
4. **The exact response is stored and replayed: status, body bytes, `Location` and `ETag`.** `response` holds `{"content": "<serialized body>", "headers": {…}}`. The body is a **string** because `jsonb` re-orders object keys (by length, then bytes): a first attempt that stored the body as a JSON object replayed `{"id": …}` where the original said `{"account_id": …}`. The integration tests caught it, and they compare `response.content` byte for byte. The first response is sent from the same string.
5. **Only 2xx responses are stored.** Any error inside the write (a 422 business rule, a 409, a 5xx) rolls the transaction back, taking the claim with it, so a retry runs fresh. That's correct for transient failures and harmless for deterministic ones.
6. **Expiry:** a key older than 24 h counts as absent. The claim statement re-arms it in place, so the window never depends on when the sweep last ran. `aml sweep-idempotency-keys` (`make -C backend sweep-idempotency-keys`) deletes expired rows: the cleanup query, with no scheduler yet.
7. **The mechanism is a helper the route calls, not middleware or a `yield` dependency.**
   - Middleware runs outside the route's transaction and would have to re-buffer bodies.
   - The cleanup of a `yield` dependency runs at a FastAPI-version-dependent point relative to the response, and that's not where a commit should be.
   - With the helper, the commit happens inside the handler, before the response exists.
8. **`UnitOfWork` gives a route one connection's transaction, idempotency store and repositories.** Unit and contract tests override it with `tests/fixtures/fakes.py` (in memory, with the same claim, replay, reuse and rollback rules), so `make test` stays Docker-free (0020, 0024).
9. **Real `POST /alerts`:**
   - The window is derived from the cited transactions: earliest `ts` to latest + 1 minute, because `alerts.window_*` are `NOT NULL` and `AlertCreate` sends no window.
   - `rule_id` = `model_version`, `triggered_at` = now, `status` = `OPEN`.
   - `alerts.idempotency_key` = the request's key. Its unique constraint is a second line of defence: with the idempotency layer planted out, the duplicate test fails with `UniqueViolation … uq_alerts_idempotency_key`, not a second row.
   - **422** with JSON-Pointer `errors` for an unknown account, an unknown transaction, or a transaction that doesn't involve the account.
10. **Migration `0002` adds `alerts.typology`** (the model's guess, CHECKed against the 8 typologies). It's kept separate from `typology_label`, which is evaluation ground truth (0022).
11. **Contract 0.3.1** (wording and behaviour only): the duplicate waits up to 5 s, then 409; only 2xx responses are stored; a request that failed can be retried with the same key; and createAlert's window and 422 causes are documented.

## Evidence

`tests/integration/test_idempotency.py`, real Postgres:

| Test | Shows |
| --- | --- |
| duplicate POST | 201 twice, identical bytes and `Location`; 1 alert row, 1 key row; `GET` returns the same alert |
| key order and whitespace | reordered, indented JSON with `transaction_ids` reversed replays the same bytes |
| same key, different body | 422 problem+json; still 1 alert |
| two concurrent identical requests | the first holds its transaction open for 1 s after inserting; the second waits (more than 0.5 s), then replays the same bytes; 1 alert |
| lock timeout | `LOCK_TIMEOUT` 200 ms against a 1.5 s first request: the second gets 409 "still in progress" |
| failed write | 422 for unknown or uninvolved transactions; retrying the same key runs again; 0 key rows stored |
| expiry and sweep | a 25 h-old key is reused for a different request (201, not 422); the sweep deletes the other expired key and keeps the fresh one |
| cases | `POST /cases` replays identical bytes and `ETag`; the same key with another body is 422 |

## Alternatives

- **An immediate 409 for concurrent duplicates.** It breaks the single transaction (decision 2), and a crash in between leaves stuck keys.
- **`SELECT … FOR UPDATE` on an existing row before inserting.** It doesn't cover the first insert race, where no row exists yet. The unique-index wait does.
- **Storing the body as a jsonb object.** Key order changes on replay.
- **Hashing raw request bytes.** The same object re-serialised with different key order would be a false 422.
- **Storing error responses too.** A transient 503 would become "the answer" for 24 h.
- **Middleware, or a `yield` dependency.** See decision 7.
- **Adding `window_start`/`window_end` to `AlertCreate`.** A contract change, redundant with the cited transactions.
- **Writing the model's typology into `typology_label`.** It contaminates evaluation ground truth.
- **Making cases and decisions real now (scope B).** About twice the work, and it mixes the case workflow into this ticket.

## Consequences

- Every new POST must use `idempotent()`. The Redocly plugin already requires the header on every POST (0014).
- `GET /alerts` (the list), `GET /cases/{id}`, `PATCH /cases/{id}/status`, and the bodies of `POST /cases` and decisions are still placeholders. Their idempotency is real, so a replayed placeholder is the stored placeholder.
- A duplicate can hold a pool connection for up to 5 s while it waits. That's fine at current load; revisit if many duplicates arrive at once.
- Expired keys pile up until someone runs the sweep. Schedule it when a scheduler exists.
