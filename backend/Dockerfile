# syntax=docker/dockerfile:1.7
# One image for every Python process: api, worker, migrate, replay (command differs).

# ---- build: resolve and install dependencies + the aml package into /app/.venv.
# Same base as runtime, so the venv's interpreter path is valid there; uv pinned.
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, in their own layer, so code changes don't reinstall them.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---- runtime: Python + the venv + migrations; no uv, no source tree, no build tools
FROM python:3.12-slim-bookworm AS runtime
RUN groupadd --system --gid 10001 aml \
 && useradd --system --uid 10001 --gid aml --no-create-home --home-dir /nonexistent aml
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER aml
EXPOSE 8000
CMD ["aml", "api"]
