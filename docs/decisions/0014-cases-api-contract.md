# 0014 — Cases API contract (`backend/openapi.yaml`)

**Status:** Accepted; decision 6 superseded by [0017](0017-decisions-close-cases-atomically.md) · **Ticket:** T05 · **Date:** 2026-10-16

## Context

`aml.api` will serve alerts, account data and investigation cases to the web app's GraphQL BFF and to the workers (through `aml.clients`). Both clients will be generated from the API description, so it has to exist, and be right, before the server does. The rules this ticket sets: problem+json errors, `Retry-After` on 429/503, UUIDs except for transactions and accounts, money as decimal strings, idempotent POSTs, and versioned status changes.

## Decision

1. **Contract-first.** `backend/openapi.yaml` (OpenAPI 3.1) is the source of truth. The server is written to match it. FastAPI's generated `/openapi.json`, `/docs` and `/redoc` are turned off (`openapi_url=None`), and a test asserts that they 404.
2. **Cursor (keyset) pagination on every list.**
   - The cursor is opaque. It encodes the last row's sort key, and is valid only with the filters it was issued for.
   - Transactions are ordered by `(ts, id)` ascending; alerts and cases by `(created_at, id)` descending.
   - `next_cursor` is `null` on the last page.
   - Alerts and cases report `total_estimate`. Transactions report an exact `total` for the window.
   - See *Cursor versus offset* below.
3. **Errors are RFC 9457 problem details** (`application/problem+json`, `type/title/status/detail/instance`).
   - Validation failures are **422** and carry an `errors` list with a JSON-Pointer `location` per field.
   - Malformed requests (a bad header, an unparseable cursor or id, a missing `Idempotency-Key`) are **400**.
   - **429** and **503** carry `Retry-After` in seconds.
   - Every operation declares 429, 500 and 503.
4. **Idempotency on every POST** (`/alerts`, `/cases`, `/cases/{id}/decisions`), following the IETF Idempotency-Key draft:
   - missing key → 400;
   - same key and same body → the stored original response;
   - same key with a different body → 422;
   - same key while the original is in flight → 409;
   - keys are kept for 24 h.

   The ticket required the key on the first two POSTs. Decisions get it too, so that every POST behaves the same way.
5. **Optimistic concurrency on case status.** `version` (starting at 1, +1 per change) is in the body and sent as a strong `ETag` (`"3"`).
   - `PATCH /cases/{id}/status` requires `If-Match`. Missing → **428**, stale → **412**.
   - A transition outside the table is **409**. The table is `OPEN → INVESTIGATING → (COMPLETE | NEEDS_HUMAN) → (ESCALATED | CLOSED)`, with `ESCALATED` and `CLOSED` final.
   - The table is also machine-readable as `x-transitions` on the `CaseStatus` schema, for the server's tests to use.
6. **Decisions are recorded, not applied.**
   - `POST /cases/{id}/decisions` takes either `APPROVE` (adopts the copilot's `recommendation.outcome`) or `OVERRIDE` (states a different `outcome`). Both need a `reason` and an `analyst_id`.
   - Allowed once per case, and only in `COMPLETE` or `NEEDS_HUMAN`. Otherwise 409.
   - The status still moves only through `PATCH`.
7. **Identifiers:**
   - alerts, cases and decisions are UUIDs;
   - transactions are `int64` JSON integers, exact in JavaScript below 2^53, which the dataset never approaches;
   - accounts are `"<bank>:<account>"`, specified in [0015](0015-account-id-format.md).
8. **Money** is `{"amount": "<decimal string>", "currency": "<code>"}`.
   - The amount is non-negative with at most 8 fractional digits; Bitcoin uses 6 in the data.
   - The currency matches `^[A-Z]{3}$`: ISO 4217 codes, plus `BTC` for Bitcoin. Ingest maps the dataset's 15 names ("US Dollar" → `USD`, …).
   - A transaction has both `amount_paid` and `amount_received`, because the dataset records both and they differ across currencies.
9. **Counterparties.**
   - The window is `[as_of - window_hours, as_of)`. The `as_of` parameter is an addition to the ticket and defaults to now: the data is from September 2022, so a window ending now would always be empty.
   - There is one edge per (counterparty, direction, currency). Totals in different currencies are never added together.
   - Outgoing edges sum `amount_paid`; incoming edges sum `amount_received`. Self-transfers are excluded.
   - A `limit` (≤ 500, default 100) and `total_edges` cap hub accounts. This is also an addition.
10. **The account profile holds only what the data has:** bank, entity id, entity name, entity type parsed from the name (`COUNTRY` and `DIRECT` are undocumented generator labels, passed through) and an activity summary.
11. **The laundering label is never exposed.** `Is Laundering` is the evaluation's ground truth. If the investigator could read it through the API, every evaluation would be meaningless.
12. **No authentication yet.** The spec declares no security scheme, and Redocly's `security-defined` rule is off. `analyst_id` is supplied by the caller. Both get revisited when auth lands.
13. **No `/v1` prefix**, and the server URL is relative (`/`). The only consumers are deployed together with the API. `info.version` carries the contract version.
14. **`GET /healthz` is not part of this contract.** It's an ops probe ([0007](0007-backend-package-and-cli.md)) with no inputs, no rate limit and no 4xx responses, so it would fail the rules that every Cases operation must meet.
15. **Lint: Redocly CLI 2.57.0**, pinned as a web dev dependency. The latest release, 2.64.1, came out the day this was written; 2.57.0 was the newest release at least two weeks old.
    - Config `backend/redocly.yaml` (next to the spec, since the root is closed) extends `recommended-strict`, which promotes warnings to errors.
    - Declarative rules: every 4xx/5xx is problem+json only, and 429/503 declare `Retry-After`.
    - A small plugin (`backend/redocly/rules.js`) adds two more: every POST requires `Idempotency-Key`, and every operation declares 429/500/503.
    - `make lint-api` runs it, `make lint` includes it, and CI runs it in the web job, which already has Node.
    - Each custom rule was checked against a planted violation.

## Cursor versus offset

**Offset pagination** (`?offset=1000&limit=50`) means "skip 1,000 rows, return the next 50".
- *For it:* it's simple, the client can jump to any page, and "page 7 of 12" is easy to show.
- *Against it:* the database still reads and throws away the 1,000 skipped rows, so page *n* costs O(n). With 5M transactions, deep pages get slow.
- *Against it, and worse:* results move under you. If an alert is inserted while an analyst pages through newest-first, every row shifts down one, so the next page repeats a row. A deletion skips one. For a review queue, "I saw every alert" has to be true.

**Cursor (keyset) pagination** returns `next_cursor`, which encodes the sort key of the last row returned, for example `(ts, id)`. The next request asks for rows *after* that key: `WHERE (ts, id) > (:ts, :id) ORDER BY ts, id LIMIT 50`.
- *For it:* a composite index finds the starting row directly, so every page costs the same, page 1 or page 100,000.
- *For it:* inserts and deletes elsewhere don't shift the pages, so nothing is repeated or skipped.
- *How ties are handled:* `id` breaks ties when two transactions share a timestamp. HI-Small timestamps are minute-precision, so ties are common, and `ts` alone would drop or repeat rows.
- *Against it:* there's no "jump to page 37" and no page count. That's why lists return a separate `total_estimate`, or `total` for transactions.

**Why the cursor is opaque.** Clients receive a base64 token, not `ts=…&id=…`. That leaves the server free to change the sort key or add fields later without breaking clients, and stops clients from constructing cursors the server never issued.

**Why totals differ.** An exact `COUNT(*)` over all alerts or cases is a full scan, which is what keyset pagination avoids. Postgres can give an estimate cheaply. Transactions are counted within a single account and time window, which the `(account, ts)` index makes small and exact. That's the number an investigator needs ("41 transactions in 72 h").

## Alternatives

- **Code-first, with FastAPI generating the spec.** Less to write, but the contract would change whenever the Python changes, clients couldn't be generated before the server exists, and the problem+json, Idempotency-Key and ETag rules would be invisible or hard to express in FastAPI's generator.
- **Offset pagination**, rejected for the reasons above. **Page-number pagination** has the same problems.
- **A transparent cursor** (`?after_ts=&after_id=`). Easier to debug, but clients would depend on the sort key forever.
- **400 for all invalid input.** It mixes "your request is broken" with "your data is invalid". 422 is FastAPI's default and the IETF draft's code for reused keys.
- **Version in the body only** (no `If-Match`). It's non-standard, and HTTP caches and clients already understand ETags.
- **Treating a missing `If-Match` as an unconditional write.** That defeats concurrency control.
- **Decisions that move the status themselves.** That gives two ways to change status, and two places where transitions are checked.
- **A closed currency enum.** Adding a currency would break strict clients. **Dataset currency names** ("US Dollar") aren't codes.
- **One sum per counterparty in a single currency.** The dataset has no FX rates, so any conversion would be invented.
- **Declaring bearer auth now.** That documents something nothing implements.
- **Redocly via `npx` or Docker.** `npx` has no lockfile and needs the network at lint time. Docker is slow and needs a daemon running just to lint. **A `package.json` in `backend/`** would add Node to the Python half.
- **Spectral** instead of Redocly. It's equally capable, but the ticket names Redocly.

## Consequences

- The server and both generated clients must follow this file. A later ticket adds a contract test that compares FastAPI's routes and models against it.
- Ingest has to normalise bank codes (0015), map currency names to codes, and parse entity types.
- Bulk reads through the API (0012) can use the keyset cursors. There is no bulk write endpoint yet.
- Without auth, `analyst_id` is unverified. The audit trail is only as trustworthy as the caller until auth lands.
- Redocly lint needs the web dependencies installed (`make install`).
