# 0017 — Recording a decision closes or escalates the case, atomically

**Status:** Accepted · **Ticket:** T06 · **Date:** 2026-10-16 · **Supersedes:** [0014](0014-cases-api-contract.md) decision 6

## Context

0014 decision 6 made `POST /cases/{id}/decisions` record only: the status then moved to `ESCALATED` or `CLOSED` through a separate `PATCH /cases/{id}/status`. The aim was one way to change status and one place to check transitions.

The console's `decideCase` mutation ([0016](0016-console-graphql-schema.md)) is a single analyst action: "escalate this, because …". It takes the version the analyst saw, and fails with either `VersionConflict` or `InvalidTransition`. Under 0014, the BFF would have to make two REST calls with nothing tying them together. If the `PATCH` then got a 412 or a 503, the decision would be saved while the case stayed `COMPLETE`: decided, but still sitting in the queue.

## Decision

1. **`POST /cases/{id}/decisions` records the decision and moves the case to `ESCALATED` (outcome `ESCALATE`) or `CLOSED` (outcome `CLOSE`) in one database transaction.**
   - It requires `If-Match` (missing → 428, stale → 412) as well as `Idempotency-Key`.
   - It returns `200` with the updated `Case` and its new `ETag`, so the caller gets the new version without another read.
   - It's allowed only from `COMPLETE` or `NEEDS_HUMAN`, and only once (409 otherwise).
2. **The final statuses are reachable only through a decision.**
   - `PATCH /cases/{id}/status` now handles only `OPEN → INVESTIGATING → COMPLETE | NEEDS_HUMAN`. A `PATCH` to `ESCALATED` or `CLOSED` returns 409.
   - `CaseStatus` gains `x-decision-only: [ESCALATED, CLOSED]` next to `x-transitions`.
   - The point: every closed or escalated case has exactly one recorded review.
3. `info.version` goes to **0.2.0**, since this breaks the response shape and the preconditions. Nothing implements the contract yet, so no client is affected.

## Alternatives

- **Keep 0014 and have the BFF make two calls.** Not atomic, as above. Retrying the `PATCH` can't fix it if the case changed between the two calls.
- **Have the BFF compensate** (delete the decision if the `PATCH` fails). Decisions are an audit record, and a delete endpoint for them would be worse than the problem.
- **Keep `PATCH` able to reach the final statuses as well.** Then there are two ways to close a case, and one of them leaves no review behind.
- **Return `201` with the `Decision`.** The caller's next step always needs the case and its new version. Returning the case saves a round trip, and the decision is already on it (`Case.decision`).

## Consequences

- 0014's goal of having a single place that checks transitions still holds: the server has one state-machine function, and both endpoints call it with the transitions they're allowed to make.
- The server's tests must cover the "both or neither" guarantee: force a failure after the decision insert and assert that the status is unchanged.
