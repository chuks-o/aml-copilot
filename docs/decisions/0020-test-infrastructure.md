# 0020 — Test infrastructure: tiers, real containers, Jest

**Status:** Accepted · **Ticket:** T09 · **Date:** 2026-10-18 · **Supersedes:** [0008](0008-web-app.md) decision 6 (Vitest), the opt-in part of [0019](0019-stub-routes-and-contract-tests.md) decision 6

## Context

T10 onwards needs tests against a real Postgres and RabbitMQ, and the web half needs component tests. The ticket specifies the tools: pytest, pytest-asyncio and testcontainers; Jest, ts-jest and React Testing Library. It also specifies the split: `make test` runs unit + contract tests, and `make test-integration` runs the integration tests.

Building the RabbitMQ fixture exposed a bug in the T03 stack's broker setup, fixed separately in [0021](0021-rabbitmq-definitions-after-boot.md). The fixture follows that fix.

## Decision

### Backend

1. **Tiers are directories**: `tests/unit/`, `tests/integration/`, `tests/contract/`.
   - `tests/conftest.py` adds the matching marker from the path. Its hook runs `tryfirst`, before pytest's `-m` deselection.
   - A test outside those directories, or carrying another tier's marker, is a collection error. `--strict-markers` is on.
   - `slow` is applied by hand; the contract test has it.
2. **Selection:**

   | Command | Runs |
   | --- | --- |
   | `make test` | `-m "unit or contract"` (also the `addopts` default) |
   | `make test-integration` | `-m integration` |
   | `make contract` | the contract test alone, with its Schemathesis summary |

   CI runs both test targets in the backend job. GitHub's Ubuntu runners have Docker.
3. **Fixtures live in `tests/fixtures/`**, loaded via `pytest_plugins`:
   - `postgres` (session) is `pgvector/pgvector:pg16` via testcontainers.
   - `migrated_engine` (session) points `Settings` at the container and calls the real `aml.db.upgrade_to_head`, the same code path as `aml migrate`.
   - `db` (per test) is a connection inside a transaction that is always rolled back.
   - `rabbitmq` (session) is `rabbitmq:3-management`, started *without* definitions. It waits for the management API, then `POST /api/definitions` with `infra/rabbitmq/definitions.json`, the same mechanism as Compose ([0021](0021-rabbitmq-definitions-after-boot.md)).
   - `fake_llm` is a scripted `FakeLLM`: `script(...)`, `complete(prompt)`, `.prompts`. An unscripted call raises. It's a placeholder interface; T29 replaces it.
   - Container images are constants that `tests/unit/test_fixture_images.py` keeps equal to `infra/docker-compose.yml`.
4. **Fixtures are synchronous.** testcontainers and the SQLAlchemy engine are sync. pytest-asyncio 1.4.0 runs in `asyncio_mode = "auto"`, and the one `anyio`-marked test moved to it, so one async plugin is in charge. Async database access is T10's decision.
5. **No Docker → integration tests fail, never skip**, with "Integration tests need a running Docker daemon". A skipped suite looks green.
6. **Network guard:** pytest-socket with `--allow-hosts=127.0.0.1,localhost,::1 --allow-unix-socket`. The Unix socket is needed because testcontainers talks to Docker through it; the first run without that flag was blocked. `tests/unit/test_network_guard.py` proves `1.1.1.1:443` is refused and localhost works. This enforces CLAUDE.md's "tests never call the internet".

### Web

7. **Jest 30.5.2 + ts-jest 29.4.14 replace Vitest**, superseding 0008 decision 6. All existing test files were migrated:
   - `@jest/globals` imports, with no ambient globals and no `@types/jest`;
   - `expect-type` 1.4.0 for compile-time assertions (the same library Vitest bundled);
   - `__dirname` instead of `import.meta.url`.
8. **CommonJS, transpile-only.**
   - `tsconfig.jest.json` extends `tsconfig.json` with `module: commonjs`, `moduleResolution: node10` (plus `ignoreDeprecations: "6.0"`, since TypeScript 6 deprecates `node10`), `verbatimModuleSyntax: false` and `isolatedModules: true`.
   - `make typecheck` (`tsc`) still type-checks the tests.
   - All runtime dependencies ship CommonJS builds (checked: graphql, openapi-fetch, urql, TanStack Query).
   - The config is `jest.config.mjs` rather than `.ts`, because a TypeScript config needs ts-node or type stripping just to load.
9. **Two Jest projects:** `node` for `*.test.ts` (resolvers, the REST client, route handlers) and `jsdom` for `*.test.tsx` (components, with React Testing Library 16.3.3 and jest-dom 7.0.1 via `test/setup-dom.ts`).

## Alternatives

- **Keeping Vitest.** It was already working and needs less configuration (0008), but the ticket specifies Jest. Running both was rejected: two configs, two ways to write a test.
- **Jest's ESM mode.** Needs `--experimental-vm-modules`. **`next/jest`** transforms with SWC, not ts-jest.
- **jsdom for every web test.** Slower, and it lacks Node's `fetch`/`Response`, which the REST client and route tests use.
- **Markers by decorator.** A forgotten marker means a test silently never runs.
- **Testing against the `make up` stack.** It shares state with development. **testcontainers' Compose module** starts the whole stack per run.
- **Truncating between tests.** Needs a table list kept in sync. **A database per test** is slow.
- **A `MagicMock` for the LLM.** It accepts any call, which hides mistakes.
- **Skipping integration tests without Docker.** It hides a missing suite.

## Consequences

- `make test` takes about 15 s, mostly the contract test. Use `-m "not slow"` locally for a few seconds.
- `make test-integration` takes about 16 s, mostly container start-up. Images are cached after the first pull.
- Code under test that commits its own transactions would escape the rollback isolation. T10 can switch `db` to savepoints (`join_transaction_mode="create_savepoint"`) when repositories commit.
- The `migrated_engine` fixture changes database settings for the rest of the session. Only integration tests request it, and they run separately from unit tests.
- New TypeScript tests import from `@jest/globals`. A component test needs the `.test.tsx` extension to get jsdom.
