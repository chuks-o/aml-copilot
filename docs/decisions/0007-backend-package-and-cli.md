# 0007 — Backend: one `aml` package, one `aml` CLI

**Status:** Accepted · **Ticket:** T02 · **Date:** 2026-10-15

## Decisions

1. **One distribution and import package, `aml`** (src layout, `py.typed`), with sub-packages `api`, `ingest`, `investigator`, `scoring`, `evals`, `clients`, `common` and `data`. Boundaries between them are enforced by import-linter (see [0009](0009-import-boundaries.md)), not by separate packages.
2. **Typer CLI** at `aml.cli:app`, installed as the `aml` script, with commands `api`, `worker`, `replay`, `migrate`, `seed`, `train` and `eval [--smoke]`.
   - Stubs print `aml <command>: not implemented` and **exit 0**, so the Makefile targets wired to them (`make migrate`, …) don't fail the build.
   - _Rejected:_ a non-zero exit for stubs. It's more "honest", but it would break `make` targets that exist on purpose.
3. **`aml api [--host] [--port] [--reload]`** runs uvicorn on `aml.api.app:app`. Defaults come from settings (`127.0.0.1:8000`). `log_config=None` routes uvicorn's logs through our JSON handler.
4. **`GET /healthz` is liveness only.** It returns `{"status":"ok","service":"aml-api","version":…}` and never checks dependencies; a readiness probe comes with the first dependency.
5. **Settings (`aml.common.config.Settings`):**
   - Read with pydantic-settings, prefix `AML_` (`AML_ENV`, `AML_LOG_LEVEL`, `AML_API_HOST`, `AML_API_PORT`), validated at startup.
   - `.env` is read from `../.env` and `.env` relative to the current directory, so the single repo-root `.env` is found from the root or from `backend/`. Real environment variables win.
   - _Rejected:_ a second `backend/.env`, which means two secrets files.
   - _Rejected:_ having the Makefile export `.env`, which doesn't help with `uv run aml api`.
6. **Logging (`aml.common.logging`):** structlog renders one JSON object per line on stdout, and stdlib/uvicorn logs go through the same formatter. `bind_contextvars(case_id=…)` adds fields to every later line.
   - _Rejected:_ a hand-rolled stdlib JSON formatter (no context binding) and `python-json-logger` (formatting only).
7. **`migrations/`** is empty with a README. The migration tool is chosen when the database is introduced.
