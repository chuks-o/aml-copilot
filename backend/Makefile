# Backend tasks. Also called by the root Makefile.

.DEFAULT_GOAL := help
.PHONY: help install lint fmt typecheck test test-integration contract codegen migrate seed replay eval-smoke notebooks

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install from uv.lock
	uv sync --locked

lint: ## Ruff (lint + format check) and import-linter contracts
	uv run ruff check .
	uv run ruff format --check .
	uv run lint-imports

fmt: ## Auto-fix and format
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## mypy --strict on src and tests
	uv run mypy

test: ## Unit and contract tests (no Docker needed)
	uv run pytest -m "unit or contract"

test-integration: ## Integration tests against real Postgres and RabbitMQ containers (needs Docker)
	uv run pytest -m integration

contract: ## Contract test only, with its Schemathesis summary (SEED=<n> to explore other inputs)
	SCHEMATHESIS_SEED=$(SEED) uv run pytest -m contract -s -p no:cacheprovider tests/contract

codegen: ## Regenerate the client (src/aml/clients/cases_api) and server models (src/aml/api/schemas.py)
	uv run openapi-python-client generate --path openapi.yaml --meta none \
		--output-path src/aml/clients/cases_api --overwrite --config openapi-python-client.yaml
	uv run datamodel-codegen --input openapi.yaml --input-file-type openapi --openapi-scopes schemas \
		--output-model-type pydantic_v2.BaseModel --target-python-version 3.12 \
		--use-annotated --field-constraints --use-standard-collections --use-union-operator \
		--use-type-alias --use-unique-items-as-set --disable-timestamp --formatters builtin \
		--custom-file-header '# Generated from openapi.yaml by datamodel-codegen (make codegen). Do not edit.' \
		--output src/aml/api/schemas.py
	uv run ruff format --quiet src/aml/api/schemas.py

migrate: ## Apply database migrations
	uv run aml migrate

seed: ## Load starter data
	uv run aml seed

replay: ## Replay HI-Small transactions
	uv run aml replay

eval-smoke: ## Quick evaluation run
	uv run aml eval --smoke

notebooks: ## Re-execute notebooks in place
	uv run --group notebooks jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
