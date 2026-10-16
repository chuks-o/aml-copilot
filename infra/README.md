# infra

Local stack: [`docker-compose.yml`](docker-compose.yml), run from the repo root with `make up` / `make down` / `make replay`. Every service reads the repo-root `.env`.

| Path | What |
| --- | --- |
| `docker-compose.yml` | postgres (pgvector), rabbitmq, one-shot migrate, api, worker, web; `replayer` under the `tools` profile |
| `rabbitmq/` | broker config and the queue/exchange topology (`definitions.json`) loaded at boot |

Images are built from `backend/Dockerfile` and `web/Dockerfile`. Choices and trade-offs: [docs/decisions/0013-local-stack.md](../docs/decisions/0013-local-stack.md).
