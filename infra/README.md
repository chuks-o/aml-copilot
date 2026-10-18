# infra

Local stack: [`docker-compose.yml`](docker-compose.yml), run from the repo root with `make up` / `make down` / `make replay`. Every service reads the repo-root `.env`.

| Path | What |
| --- | --- |
| `docker-compose.yml` | postgres (pgvector), rabbitmq, one-shot `rabbitmq-definitions` and `migrate`, api, worker, web; `replayer` under the `tools` profile |
| `rabbitmq/definitions.json` | queue/exchange topology, imported after the broker starts by `rabbitmq-definitions` (not at boot, which would skip creating the app user; see decision 0021) |

Images are built from `backend/Dockerfile` and `web/Dockerfile`. Choices and trade-offs: [docs/decisions/0013-local-stack.md](../docs/decisions/0013-local-stack.md).
