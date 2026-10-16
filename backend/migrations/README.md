# migrations

Alembic migrations, applied by `aml migrate` (`make migrate` locally; the one-shot `migrate` container in Docker Compose).

Alembic is configured in code (`aml.db.alembic_config`), so there is no `alembic.ini`. `env.py` reads the database URL from `aml.common.Settings`.

`versions/` is empty until T10, so `aml migrate` currently connects to Postgres, finds nothing to apply, and exits 0.
