# CLAUDE.md

Working rules for this repo. They apply to every change, human or agent. The reasoning behind them is in [docs/decisions/](docs/decisions/); read those before changing structure.

## Teaching rules

- Before changing code, restate the goal, explain the concepts involved in plain English, and list the files you will change. Wait for approval on anything that touches more than 3 files.
- For any decision with a real alternative, write `docs/decisions/NNNN-short-title.md` (context, decision, alternatives, consequences) in the same commit. Start from [0000-template.md](docs/decisions/0000-template.md), take the next free number, and add a row to [docs/decisions/README.md](docs/decisions/README.md). Never renumber or rewrite an accepted record; supersede it with a new one.
- When claiming a test or check passes, paste the command and its output.

## Layout rules

- The root holds only `web/`, `backend/`, `infra/`, `docs/`, `.github/` and the five root files: `README.md`, `CLAUDE.md`, `Makefile`, `.env.example`, `.gitignore` (plus the git-ignored `.env`). Ask before adding anything at the root.
- `web/` is one Next.js app; its GraphQL BFF lives at `src/app/api/graphql`.
- `backend/` is one Python package (`aml`) run as several processes (`aml api`, `aml worker`, `aml migrate`, …).

## Architecture rules

- Processes talk only via REST (`aml.api`), GraphQL (the web app's `/api/graphql` route) or RabbitMQ.
- Modules outside `aml.api` never import it; they use the generated client in `aml.clients` (added later). import-linter enforces this (`make lint`).
- Only `aml.api` owns the database: migrations live in `backend/migrations`, and only `aml.api` and the `aml` CLI may import `aml.db`. import-linter enforces this too.
- All outbound network calls go through the retry helper in `aml.common` (added later). Don't write ad-hoc retry loops in the meantime.
- No secrets in code. Configuration and credentials come from the environment (`.env`, documented in `.env.example`).
- Tests never call real LLM APIs or the internet. Fake or stub them.
- Conventional commits, one logical change per commit: `type(scope): summary`, where `scope` is the area (`web`, `backend`, `infra`, `docs`, `ci`), with the ticket as a trailer, e.g. `Refs: T04`.

## Checks

| What | Command |
| --- | --- |
| Lint (ESLint, Prettier, Ruff, import-linter, Redocly on `backend/openapi.yaml`) | `make lint` (API contract alone: `make lint-api`) |
| Types (tsc, mypy --strict) | `make typecheck` |
| Tests (Vitest, pytest) | `make test` |
| Whole stack, healthy | `make up` (stop and wipe with `make down`) |

`make help` lists every target.
