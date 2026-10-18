# 0021 — RabbitMQ topology is imported after boot, not at boot

**Status:** Accepted · **Ticket:** T09 · **Date:** 2026-10-18 · **Supersedes:** [0013](0013-local-stack.md) decision 5

## Context

0013 loaded `infra/rabbitmq/definitions.json` at broker boot (`rabbitmq.conf` set `definitions.import_backend = local_filesystem`). Building the T09 test fixture, a probe container with exactly that configuration showed:

- the log line `Will not seed default virtual host and user: have definitions to load...`;
- `rabbitmqctl list_users` and `list_vhosts` both empty;
- `rabbitmqctl authenticate_user aml …` failing with `invalid credentials`.

So the Compose broker had no `aml` user and no `/` vhost, and no client could log in. The healthcheck (`rabbitmq-diagnostics ping`) never authenticates, so it reported healthy. Nothing consumes the broker yet, which is why this went unnoticed since T03.

## Decision

1. **The broker boots without definitions.** `infra/rabbitmq/rabbitmq.conf`, whose only job was the boot import, is deleted. RabbitMQ creates `RABBITMQ_DEFAULT_USER` and the `/` vhost from the environment again.
2. **The topology is imported through the management API after start-up.** A one-shot Compose service, `rabbitmq-definitions` (`curlimages/curl:8.22.0`), posts `definitions.json` to `/api/definitions` with the app's credentials, retrying until the API is up. `api` and `worker` start only after it completes (`service_completed_successfully`). The test fixture does the same `POST` ([0020](0020-test-infrastructure.md)).
3. **The healthcheck authenticates:** `rabbitmqctl authenticate_user "$RABBITMQ_DEFAULT_USER" "$RABBITMQ_DEFAULT_PASS"`. "Healthy" now means the app's credentials work, not just that the node answers.

Verified with `make up`:
- every service healthy, and `rabbitmq-definitions` exited 0 with `definitions imported`;
- `list_users` shows `aml [administrator]` and `list_vhosts` shows `/`;
- `authenticate_user` returns `Success`;
- `GET /api/whoami` answers `{"name":"aml",…}`.

The integration test `test_app_user_exists_with_the_default_vhost` guards the fixture side.

## Alternatives

- **Put the user, the vhost and a password hash in `definitions.json`.** Boot import would then create them, but that commits a credential, even if only a dev one.
- **Generate `definitions.json` from a template at container start** (entrypoint script plus `rabbitmqctl hash_password`). It works, but it adds a custom entrypoint to a stock image for something the management API already does.
- **Have the worker declare queues in code at start-up.** Simple, but the topology becomes whatever the first process to connect declares. That reverses 0013's choice of a versioned topology file.
- **Keep the ping healthcheck.** It's what hid this bug.

## Consequences

- Topology changes go in `definitions.json`, and `make up` applies them. Imports merge, so removing a queue from the file doesn't delete it from a running broker; `make down` (which wipes volumes) does.
- `make up` gains a few seconds while `rabbitmq-definitions` runs.
- The management plugin is now required, not just convenient. The image already includes it (`rabbitmq:3-management`).
