# aml-copilot

AML alert investigation system built on the IBM AML HI-Small dataset.

| Path | What |
| --- | --- |
| `web/` | Next.js console (App Router, urql, TanStack Query); will host the GraphQL API |
| `backend/` | Python package `aml`: FastAPI, ingest, scoring, investigator, evals; `aml` CLI |
| `infra/` | Docker Compose for the local stack (Postgres, RabbitMQ, api, worker, web) |
| `docs/decisions/` | Decision records. Read these first. |

Working rules (for people and Claude Code) are in [`CLAUDE.md`](CLAUDE.md).

## Quickstart

Requires Node 22+, pnpm 9, [uv](https://docs.astral.sh/uv/), Python 3.12, and Docker for the full stack.

```bash
cp .env.example .env
make install
make lint typecheck test   # make test-integration needs Docker
make help                 # all targets
cd backend && uv run aml api   # http://127.0.0.1:8000/healthz
```

Whole stack in Docker (needs about 10 GB free disk on first build):

```bash
make up     # builds images, migrates, waits until every service is healthy
make down   # stops it and deletes the database volume
```

| Service | URL |
| --- | --- |
| Web console | http://localhost:3000 |
| API | http://localhost:8000/healthz |
| RabbitMQ UI | http://localhost:15672 (user/password from `.env`) |
| Postgres | `localhost:5432` |

Dataset download: see `backend/data/README.md`.
