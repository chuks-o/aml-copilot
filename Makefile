# Root entry point. Delegates to web/ (pnpm scripts) and backend/ (its Makefile).
# Stub targets print TODO until their ticket lands.

WEB := pnpm --dir web
BACKEND := $(MAKE) --no-print-directory -C backend
COMPOSE := docker compose -f infra/docker-compose.yml
# Everything `make codegen` writes. Committed; `make codegen-check` keeps it current.
GENERATED := web/src/generated backend/src/aml/clients/cases_api backend/src/aml/api/schemas.py

.DEFAULT_GOAL := help
.PHONY: help install lint lint-api fmt codegen-check typecheck test contract codegen up down migrate seed replay eval-smoke env-check

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install: ## Install web and backend dependencies from lockfiles
	$(WEB) install --frozen-lockfile
	$(BACKEND) install

lint: lint-api ## ESLint + Prettier (web); Ruff + import-linter (backend); the API contract
	$(WEB) run lint
	$(BACKEND) lint

lint-api: ## Redocly lint of backend/openapi.yaml (CLI pinned in web/package.json)
	$(WEB) exec redocly lint --config ../backend/redocly.yaml ../backend/openapi.yaml

fmt: ## Auto-format web and backend
	$(WEB) run format
	$(BACKEND) fmt

typecheck: ## tsc (web); mypy --strict (backend)
	$(WEB) run typecheck
	$(BACKEND) typecheck

test: ## Vitest (web); pytest (backend)
	$(WEB) run test
	$(BACKEND) test

contract: ## Contract test: Schemathesis against a live API server (SEED=<n> optional)
	$(BACKEND) contract SEED=$(SEED)

codegen: ## Regenerate typed clients from backend/openapi.yaml and web/src/graphql (commit the output)
	$(WEB) run codegen
	$(BACKEND) codegen

codegen-check: ## Run codegen, then fail if the committed generated code changed
	@$(MAKE) --no-print-directory codegen
	@# git status, not git diff: a newly generated file is untracked, and git diff misses it.
	@if [ -n "$$(git status --porcelain -- $(GENERATED))" ]; then \
		echo "Generated code is stale. Run 'make codegen' and commit:"; \
		git status --short -- $(GENERATED); \
		git --no-pager diff --stat -- $(GENERATED); \
		exit 1; \
	fi
	@echo "Generated code is up to date."

up: env-check ## Build images, start the stack, wait until every service is healthy
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack and delete its volumes (database included)
	$(COMPOSE) down -v

migrate: ## Apply database migrations
	$(BACKEND) migrate

seed: ## Load starter data
	$(BACKEND) seed

replay: env-check ## Replay HI-Small transactions (replayer container, "tools" profile)
	$(COMPOSE) --profile tools run --rm --build replayer

eval-smoke: ## Quick evaluation run
	$(BACKEND) eval-smoke

env-check:
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
