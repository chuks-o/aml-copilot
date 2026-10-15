# aml-copilot

AML alert investigation system built on the IBM AML HI-Small dataset.

| Path | What |
| --- | --- |
| `web/` | Next.js console (App Router, urql, TanStack Query); will host the GraphQL API |
| `backend/` | Python package `aml`: FastAPI, ingest, scoring, investigator, evals; `aml` CLI |
| `infra/` | Infrastructure (empty for now) |
| `docs/decisions/` | Decision records. Read these first. |

## Quickstart

Requires Node 22+, pnpm 9, [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
cp .env.example .env
make install
make lint typecheck test
make help                 # all targets
cd backend && uv run aml api   # http://127.0.0.1:8000/healthz
```

Dataset download: see `backend/data/README.md`.
