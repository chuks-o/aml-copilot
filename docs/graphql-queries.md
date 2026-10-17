# Console GraphQL operations

The exact operations the two console screens send to `/api/graphql`. The schema is [`web/src/graphql/schema.graphql`](../web/src/graphql/schema.graphql), and the design choices are in [decision 0016](decisions/0016-console-graphql-schema.md).

The operations live in [`web/src/graphql/operations/`](../web/src/graphql/operations/). `make codegen` turns them into typed documents in `web/src/generated/graphql.ts`, and the screens pass those to urql's `useQuery`, `useMutation` and `useSubscription`. `web/test/graphql-operations.test.ts` checks that each block below is identical to its `.graphql` file, and codegen rejects any operation the schema doesn't allow. Change them together.

## Case queue screen

Source: [`case-queue.graphql`](../web/src/graphql/operations/case-queue.graphql).

A table of cases, newest first, filterable by status and typology, 50 rows per page, and live-updating.

```graphql
query CaseQueue($first: Int!, $after: String, $status: CaseStatus, $typology: Typology) {
  cases(first: $first, after: $after, status: $status, typology: $typology) {
    totalCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      cursor
      node {
        ...CaseQueueRow
      }
    }
  }
}

subscription CaseQueueUpdates {
  caseUpdated {
    ...CaseQueueRow
  }
}

fragment CaseQueueRow on Case {
  id
  status
  decision
  typology
  confidence
  score
  version
  updatedAt
  account {
    id
    entityName
    bankName
  }
}
```

- First page: `{"first": 50}`, plus `status` and/or `typology` when a filter is set.
- Next page: the same variables plus `"after": <pageInfo.endCursor>`. Stop when `hasNextPage` is false.
- Show `totalCount` as "~N cases". It's an estimate.
- `CaseQueueUpdates` is subscribed once while the screen is open. urql's cache merges each pushed row by `__typename` + `id`, so the matching row updates in place. A case that changes status may then belong to a different filter; the screen re-runs `CaseQueue` when a pushed case no longer matches the filter.

## Case file screen

Source: [`case-file.graphql`](../web/src/graphql/operations/case-file.graphql).

One case: the copilot's decision and confidence, the claims with their cited transactions, the evidence the copilot couldn't find, the run cost, the analyst's review, and the decision form.

```graphql
query CaseFile($id: ID!) {
  case(id: $id) {
    ...CaseFileFields
  }
}

mutation DecideCase($input: DecideCaseInput!) {
  decideCase(input: $input) {
    __typename
    ... on DecideCaseSuccess {
      case {
        ...CaseFileFields
      }
    }
    ... on VersionConflict {
      currentVersion
      case {
        ...CaseFileFields
      }
    }
    ... on InvalidTransition {
      from
      allowedFrom
    }
    ... on UserError {
      message
    }
  }
}

subscription CaseFileUpdates($id: ID!) {
  caseUpdated(id: $id) {
    ...CaseFileFields
  }
}

fragment CaseFileFields on Case {
  id
  status
  decision
  typology
  confidence
  score
  version
  updatedAt
  missingEvidence
  alert {
    id
    score
    typology
    reason
    modelVersion
    createdAt
  }
  account {
    id
    bankId
    bankName
    accountNumber
    entityId
    entityName
    entityType
  }
  claims {
    id
    text
    verified
    citations {
      id
      ts
      fromAccountId
      toAccountId
      amountPaid {
        amount
        currency
      }
      amountReceived {
        amount
        currency
      }
      paymentFormat
    }
  }
  run {
    steps
    tokens
    costUsd
    durationMs
  }
  review {
    kind
    decision
    reason
    analystId
    decidedAt
  }
}
```

- `CaseFile` runs with `{"id": "<case uuid>"}`. A `null` case shows "not found".
- `CaseFileUpdates` runs with the same id while the screen is open, so a running investigation fills in claims and run stats live.
- `DecideCase` runs with:

  ```json
  {
    "input": {
      "caseId": "<case uuid>",
      "version": 3,
      "decision": "ESCALATE",
      "reason": "Funds consolidated from 14 unrelated accounts and forwarded within 8 hours."
    }
  }
  ```

  where `version` is the `Case.version` the analyst was looking at. The screen branches on `__typename`:

  | `__typename`        | What the screen does                                                                                                                                  |
  | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
  | `DecideCaseSuccess` | Shows the updated case (now `ESCALATED` or `CLOSED`, with `review` set).                                                                              |
  | `VersionConflict`   | Says "this case changed while you were reading it", shows the returned current case, and keeps the analyst's reason in the form so they can resubmit. |
  | `InvalidTransition` | Says the case can't be decided from `from`, for example still `INVESTIGATING` or already `CLOSED`, and disables the form.                             |
  | anything else       | A union member added later. Shows `message` (every error member implements `UserError`).                                                              |

  Any top-level `errors` entry (not found, bad input, the API being down) shows the generic error banner.

## Why decideCase errors are a union, not just top-level errors

GraphQL has a built-in error channel: the `errors` array next to `data`. Each entry is a message plus a free-form `extensions` object. It works for _anything_ that goes wrong, which is exactly its weakness for the errors an analyst is expected to hit.

1. **It's untyped.** The schema can't say which errors `decideCase` produces, or what data they carry. A client would have to string-match `extensions.code` and hope the fields it needs, like the current version, are there. With a union, `VersionConflict.currentVersion: Int!` is in the schema, type-checked by codegen, and validated by the test that checks this file.
2. **The client is forced to handle each case.** The generated TypeScript type for `decideCase` is a discriminated union on `__typename`. A `switch` that forgets `VersionConflict` fails the exhaustiveness check at compile time. Nothing comparable exists for entries in `errors`.
3. **An error can carry real data.** `VersionConflict.case` returns the case as it is now, selected with the same fragment as the screen. The UI refreshes from the mutation response alone, and urql's cache updates it everywhere. Data in `extensions` bypasses the cache and has no type.
4. **Expected outcomes aren't failures.** A stale version is a normal result of two analysts working at once. Putting it in `errors` makes `data.decideCase` null, gets it logged as a server error, and trips error monitoring. That's noise that hides real failures.
5. **It still adds up to one rule.** The _union_ holds outcomes the analyst can act on. _Top-level errors_ hold what they can't: a case that doesn't exist, malformed input (a bug in our own UI), or the REST API or database being down (`extensions.code`: `NOT_FOUND`, `BAD_USER_INPUT`, `UNAVAILABLE`). Those get one generic banner, and nobody needs typed data from them.

The `UserError` interface keeps the union open to change. If a new member such as `CaseLocked` is added later, older clients still select `... on UserError { message }` and show something sensible instead of nothing.
