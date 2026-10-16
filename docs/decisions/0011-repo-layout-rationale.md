# 0011 — Why the repo is laid out this way

**Status:** Accepted · **Ticket:** T04 · **Date:** 2026-10-16

## Context

T02 set up the layout ([0005](0005-repo-layout.md)), the backend package ([0007](0007-backend-package-and-cli.md)), the web app ([0008](0008-web-app.md)) and the import contracts ([0009](0009-import-boundaries.md)). Those records say *what* was chosen. This one explains *why* the three biggest choices were made, so they can be judged when the system grows.

(T04 asked for this as `0001-repo-layout.md`. That number already belongs to the T01 data record, and renumbering accepted records breaks links between them, so it takes the next free number instead. See [0012](0012-working-rules.md).)

## Decision

1. **One Python package, `aml`, run as several processes.**
   - The backend has several jobs: serve the API, run background work, migrate the database, replay transactions, train and evaluate. Each needs its own process (they scale, crash and restart independently), but they share settings, logging, data types and the dataset code.
   - One package means one `pyproject.toml`, one lockfile, one Docker image and one CLI (`aml api`, `aml worker`, …). A shared change is one commit and one version, and there's no internal package publishing.
   - The process boundary is set by *how the code is started*, not by which package it lives in. The communication rule (REST, GraphQL, RabbitMQ only) keeps processes from depending on each other's memory.
2. **The GraphQL BFF lives inside Next.js** (`web/src/app/api/graphql`).
   - GraphQL exists to serve the console. Its schema follows the screens, not the backend's data model, so it belongs with the UI that shapes it.
   - Inside Next.js, the schema, resolvers, generated TypeScript types and the pages that query them are type-checked together in one project and deployed as one unit. A breaking schema change fails `tsc` in the same commit.
   - The browser calls the same origin (`/api/graphql`), so there's no CORS setup and no extra service to run. Resolvers call `aml.api` over REST, which keeps the Python API the single owner of business logic and data.
3. **Boundaries are enforced with import-linter, not separate packages.**
   - The rules ("workers don't import `aml.api`", "nothing imports `aml.evals`", "`aml.common` depends on nothing", "only the API owns `aml.db`") are about *who may depend on whom*. import-linter checks exactly that, including indirect imports, and fails `make lint` and CI.
   - Moving a module across a boundary is a contract edit reviewed in a diff, not a repackaging job.

## Alternatives

- **One package per service** (uv workspace with `api`, `worker`, `ingest`… each with its own `pyproject.toml`). That's real isolation, but each package needs its own dependency list, versioning and image, plus a shared library package. It's heavy for one developer, and a missing dependency declaration still doesn't stop an import if the workspace installs everything together. This was the discarded T02 draft (see 0005).
- **A separate GraphQL server** (Python Strawberry inside `aml.api`, or a standalone Node service). Strawberry would put UI-shaped schema into the business API and lose end-to-end TypeScript types. A standalone Node service adds a deployable and CORS for no benefit while there is one UI.
- **No GraphQL; the browser calls REST directly.** Simpler, but the console would stitch several REST calls per screen and hand-write types for each.
- **Boundaries by convention only.** Free today, but nothing catches the first shortcut import, and indirect imports are invisible in review.

## Consequences

- One image and one lockfile for all Python processes. Each process's image carries dependencies it doesn't use (for example the API carries training libraries). Revisit if image size or cold start starts to matter.
- Every new top-level `aml` module must be added to the import contracts. `tests/test_architecture.py` fails until it is.
- Shared request and response models can't live in `aml.api` (see 0009). They go in `aml.common` or a schema module.
- The web app becomes a server, not a static site. That was already true for route handlers.
