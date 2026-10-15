# Backend tasks. Also called by the root Makefile.

.DEFAULT_GOAL := help
.PHONY: help install lint fmt typecheck test migrate seed replay eval-smoke notebooks

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

test: ## pytest
	uv run pytest

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
