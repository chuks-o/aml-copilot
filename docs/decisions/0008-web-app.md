# 0008 — Web app structure and data clients

**Status:** Accepted; decision 6 (Vitest) superseded by [0020](0020-test-infrastructure.md) · **Ticket:** T02 · **Date:** 2026-10-15

## Decisions

1. **Next.js App Router under `src/`:**
   - `src/app/` holds pages and route handlers;
   - `src/graphql/` holds the schema (SDL) and resolvers;
   - `src/generated/` holds codegen output (empty, excluded from lint and format).
2. **SDL-first GraphQL.** `src/graphql/schema.graphql` is the source of truth. It currently declares only `Query.health`, plus a hand-written `resolvers.ts` and a test that keeps the two consistent.
   - _Rejected:_ code-first (Pothos), where the schema is a by-product of TS code and harder for backend developers to review.
3. **No `src/app/api/graphql/route.ts` until T28,** and GraphQL Yoga isn't installed yet.
   - _Rejected:_ a placeholder route returning 501. It would ship a fake endpoint.
4. **`GET /api/healthz`** is a static liveness route, giving web something real to test and probe.
5. **urql owns all GraphQL** (configured for `/api/graphql` via `NEXT_PUBLIC_GRAPHQL_URL`). **TanStack Query owns non-GraphQL server state.** Both providers are mounted once in `src/app/providers.tsx`.
   - _Rejected:_ TanStack Query + `graphql-request` for everything (one cache, but urql was specified).
   - _Rejected:_ urql alone, which leaves no idiomatic tool for non-GraphQL calls.
   - Reviewers should reject GraphQL calls made through TanStack Query, and vice versa.
6. **Test runner: Vitest.**
   - _Rejected:_ Jest, which needs extra configuration for ESM and TS.
