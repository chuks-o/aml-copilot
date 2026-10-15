# backend

One Python 3.12 package, `aml`, managed with uv. Everything runs through the `aml` CLI:

```bash
make install            # uv sync
uv run aml --help       # api, worker, replay, migrate, seed, train, eval
uv run aml api          # FastAPI on 127.0.0.1:8000, GET /healthz
make lint typecheck test
```

| Module | Purpose |
| --- | --- |
| `aml.api` | FastAPI app (cases, alerts, decisions) |
| `aml.ingest` | Load and replay transactions |
| `aml.scoring` | Score transactions/accounts, raise alerts |
| `aml.investigator` | LLM investigation agent |
| `aml.evals` | Evaluation harness (imported only by tests and the CLI) |
| `aml.clients` | HTTP clients for `aml.api`, used by the modules above |
| `aml.common` | Settings (`AML_*` env vars) and JSON logging |
| `aml.data` | Dataset access |

Import boundaries are enforced by import-linter; see `[tool.importlinter]` in `pyproject.toml`.
