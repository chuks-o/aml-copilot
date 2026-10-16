# 0016 — Console GraphQL schema

**Status:** Accepted · **Ticket:** T06 · **Date:** 2026-10-16

## Context

The console has two screens, a case queue and a case file. They talk only to the web app's GraphQL BFF (`/api/graphql`), which calls the REST API ([0014](0014-cases-api-contract.md)). T06 designs the schema, `web/src/graphql/schema.graphql`, and documents the operations the screens send in [`docs/graphql-queries.md`](../graphql-queries.md). The route and resolvers come in T28 ([0008](0008-web-app.md)).

## Decision

1. **The schema follows the screens, not REST.** It includes fields REST doesn't serve yet (see Consequences). `Query.health` stays.
2. **`Query.cases` is a Relay connection** (`edges { cursor node }`, `pageInfo`, `totalCount`), forward-only (`first` / `after`).
   - `first` must be 1–100. Anything else is a top-level `BAD_USER_INPUT`, because it's a client bug, not something to clamp silently.
   - `hasPreviousPage` is always false.
   - `totalCount` keeps the Relay and ticket name but is documented as **approximate**, since it comes from REST's `total_estimate`. The UI shows "~N".
3. **`Case.decision` is the copilot's proposed decision** (`CaseDecision`: `ESCALATE | CLOSE`), shown next to `confidence`. The analyst's ruling is a separate field, `Case.review` (`APPROVED | OVERRIDDEN`, the applied decision, reason, analyst and time). This field goes beyond the ticket's list.
4. **`decideCase(input: {caseId, version, decision, reason})`** takes a plain outcome.
   - The BFF derives REST's action: `APPROVE` when `decision` equals `Case.decision`, otherwise `OVERRIDE`. With no copilot decision, it's `OVERRIDE`.
   - It calls the atomic REST endpoint from [0017](0017-decisions-close-cases-atomically.md), with `If-Match: "<version>"`.
   - `analyst_id` comes from the request context, not the input. Until auth exists, that's a fixed dev identity.
5. **`DecideCasePayload` is a union:** `DecideCaseSuccess | VersionConflict | InvalidTransition`.
   - Both error members implement the `UserError { message }` interface.
   - `VersionConflict` returns `currentVersion` and the current `case`.
   - `InvalidTransition` returns `from` and `allowedFrom`.
   - How REST outcomes map:

     | REST | GraphQL |
     | --- | --- |
     | 200 | `DecideCaseSuccess` |
     | 412 | `VersionConflict` (the BFF re-reads the case) |
     | 409 | `InvalidTransition` |
     | 404 | top-level `NOT_FOUND` |
     | 400 / 422 | top-level `BAD_USER_INPUT` |
     | 428, 429, 5xx | top-level `UNAVAILABLE` (428 can only be a BFF bug) |

   - The reasoning is in [`docs/graphql-queries.md`](../graphql-queries.md#why-decidecase-errors-are-a-union-not-just-top-level-errors).
6. **`Case.alert` is singular**, as the ticket says: the alert that opened the case. REST allows several alerts per case, and the BFF returns the first.
7. **Ids are plain `ID`s** (UUIDs, the `<bank>:<account>` account id), with no Relay `Node` interface and no global ids. urql's cache already keys on `__typename` + `id`.
8. **Scalars:**
   - `DateTime` (RFC 3339 in UTC) and `Decimal` (exact decimal string).
   - `Money { amount: Decimal!, currency: String! }`, and `run.costUsd: Decimal!`.
   - **Transaction ids are `ID`** (strings), because GraphQL `Int` is 32-bit and REST ids are 64-bit.
   - `score` and `confidence` are `Float`, since they're probabilities, not money.
9. **`run.steps` is a count** (`Int!`) next to `tokens`, `costUsd` and `durationMs`.
10. **Nullability:**
    - Identity fields, lists and anything that always exists (`score`, `alert`, `account`, `version`) are non-null.
    - Anything produced by the investigation or the review (`decision`, `confidence`, `typology`, `run`, `review`) is nullable until it exists.
    - Lists are non-null and empty rather than null.
    - `Query.case` and `Subscription.caseUpdated` are nullable, as the ticket specifies.
11. **`caseUpdated(id: ID)`:** with an id it watches one case (the case file); without one it watches all cases (the queue). Transport is T28's choice. Next.js route handlers can't upgrade to WebSockets, so the expected transport is server-sent events via GraphQL Yoga.
12. **Documented operations are tested.** `web/test/graphql-operations.test.ts` parses every `graphql` block in `docs/graphql-queries.md`, checks the operation names, and validates each block against the schema. It also checks the union's members and that every failure implements `UserError`.

## Alternatives

- **Top-level errors only for `decideCase`.** They're untyped, invisible to codegen, and they'd null out `data`. Rejected; see the doc linked above.
- **A union with no shared interface.** Adding a member later would leave older clients with nothing to show.
- **`decision` meaning the analyst's ruling.** That would leave the copilot's proposal, the thing the analyst reviews, without a field.
- **`action` + `outcome` in the mutation input.** Two fields that can contradict each other, where the outcome alone determines the action.
- **`alerts: [Alert!]!`.** More general, but the ticket and both screens want the opening alert. Add it if multi-alert cases reach the UI.
- **Renaming `totalCount` to `totalEstimate`.** More honest in the name, but it departs from the ticket and Relay convention. The field description carries the caveat instead.
- **The Relay `Node` interface and global ids.** Only worth it with the Relay client; we use urql.
- **`Float` for money, `Int` for transaction ids.** These lose precision and overflow, respectively.
- **A step list in `run`.** It's more than the case file shows now. Add `run.stepDetails` when the trace view exists.
- **Bidirectional pagination.** The queue only scrolls forward.

## Consequences

- **REST must grow before T28 can resolve the case file.** It's missing per case:
  - `confidence`;
  - `claims[]` (`id`, `text`, `verified`, `citations` as transaction ids);
  - `missing_evidence[]`;
  - run stats (`steps`, `tokens`, `cost_usd`, `duration_ms`).

  REST's `recommendation.outcome` maps to `Case.decision`, and its `decision` maps to `Case.review`. The investigator ticket owns adding these to `openapi.yaml`.
- Claims cite transactions by id. The BFF has to fetch those transactions, which needs a batch lookup in REST (`GET /transactions?ids=…`) or a DataLoader over single fetches, so a claim list isn't N round trips.
- `Case.score` duplicates `alert.score`. That keeps the queue row flat, at the cost of one more field to keep consistent.
- The queue subscription pushes every case change to every open queue. That's fine at this scale; filter server-side if it gets noisy.
