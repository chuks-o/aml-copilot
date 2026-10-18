# 0013 — Local stack with Docker Compose

**Status:** Accepted; decision 5 (definitions at boot) superseded by [0021](0021-rabbitmq-definitions-after-boot.md) · **Ticket:** T03 (recorded in T04) · **Date:** 2026-10-16

## Context

T03 made `make up` start the whole system locally: Postgres, RabbitMQ, the API, the worker and the web app, with migrations applied first. It shipped without a decision record; this one records its choices after the fact. The files are `infra/docker-compose.yml`, `backend/Dockerfile`, `web/Dockerfile`, `infra/rabbitmq/` and `backend/migrations/`.

## Decision

1. **One Compose file, `infra/docker-compose.yml`, driven from the root Makefile.**
   - `make up` runs `up -d --build --wait`, which returns only when every service is healthy.
   - `make down` runs `down -v`, which also deletes the database volume.
   - `make replay` runs the `replayer`, which sits under the `tools` profile so `up` doesn't start it.
   - An `env-check` target fails fast if `.env` is missing.
2. **Every service reads the single repo-root `.env`.**
   - Credentials use the names the images already read (`POSTGRES_PASSWORD`, `RABBITMQ_DEFAULT_PASS`), and `aml` settings read them under the same names. Each secret appears once.
   - Hosts default to `localhost` for commands run on the machine. Compose overrides them to the service names.
   - Passwords are `SecretStr` and required, with no default.
3. **Ports bind to `127.0.0.1` only**, so the dev databases aren't reachable from the network.
4. **Postgres is `pgvector/pgvector:pg16`**: plain Postgres 16 with the vector extension available, so later embedding search doesn't need an image swap. Its healthcheck uses TCP (`-h 127.0.0.1`), because during first boot the image runs a temporary socket-only server that would otherwise report ready too early.
5. **RabbitMQ is `rabbitmq:3-management`**, with topology loaded at boot from `infra/rabbitmq/definitions.json`, which is empty for now. Queues will be declared in that file, in version control, rather than by whichever process starts first.
6. **One backend image for every Python process.**
   - Multi-stage: uv installs dependencies into a venv in their own cached layer, and the runtime stage copies only the venv and `migrations/`.
   - It runs as a non-root user. The Compose `command` picks the process (`aml api`, `aml worker`, `aml migrate`, `aml replay`). See [0011](0011-repo-layout-rationale.md).
7. **The web image uses Next.js `output: "standalone"`**: the server plus only the `node_modules` it needs, running as non-root. `NEXT_PUBLIC_*` values are baked in at build time.
8. **Migrations: Alembic, run by a one-shot `migrate` service.**
   - `api` and `worker` wait for it to exit successfully (`service_completed_successfully`).
   - Alembic is configured in code (`aml.db.alembic_config`), with no `alembic.ini`. `env.py` takes the URL from settings, so a `%` in a password can't break Alembic's config interpolation.
   - The driver is psycopg 3 via SQLAlchemy `URL.create`, which escapes credentials.
9. **The worker's healthcheck is a heartbeat file.** The loop touches it after every iteration, and the container is unhealthy if it's older than 30 s, so a hung job shows up even though the worker serves no HTTP.

## Alternatives

- **Plain `postgres:16`.** It works today, but adding pgvector later means changing the image under existing data.
- **Run migrations when the API starts.** With several API replicas they race, and the worker can start against an old schema. A separate job runs once and gates everything else.
- **`alembic.ini` with the URL in it.** It duplicates config, and `%` in passwords breaks interpolation.
- **Separate images per process.** Smaller images, but N builds of the same code and versions that can drift.
- **Separate `.env` files per service, or `AML_`-prefixed copies of the credentials.** Two places to keep each secret in sync.
- **Binding ports on all interfaces** (Compose's default). It exposes dev databases with dev passwords to the local network.
- **`depends_on` without healthchecks.** "Started" isn't "ready", so the API would crash-loop until Postgres accepts connections.

## Consequences

- A first `make up` needs about 10 GB free disk for images and build cache. T03 hit a full disk; `docker system prune -a` recovers the space.
- `make down` wipes the database. That's fine while data is reproducible from the dataset, but it needs a non-destructive `stop` target once it isn't.
- `versions/` is empty until T10, so `migrate` currently connects and exits 0.
- Changing a `NEXT_PUBLIC_*` value needs an image rebuild, not a restart.
