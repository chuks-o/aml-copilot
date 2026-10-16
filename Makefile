# Root entry point. Delegates to web/ (pnpm scripts) and backend/ (its Makefile).
# Stub targets print TODO until their ticket lands.

WEB := pnpm --dir web
BACKEND := $(MAKE) --no-print-directory -C backend
COMPOSE := docker compose -f infra/docker-compose.yml

.DEFAULT_GOAL := help
.PHONY: help install lint fmt typecheck test codegen up down migrate seed replay eval-smoke env-check

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install web and backend dependencies from lockfiles
	$(WEB) install --frozen-lockfile
	$(BACKEND) install

lint: ## ESLint + Prettier (web); Ruff + import-linter (backend)
	$(WEB) run lint
	$(BACKEND) lint

fmt: ## Auto-format web and backend
	$(WEB) run format
	$(BACKEND) fmt

typecheck: ## tsc (web); mypy --strict (backend)
	$(WEB) run typecheck
	$(BACKEND) typecheck

test: ## Vitest (web); pytest (backend)
	$(WEB) run test
	$(BACKEND) test

codegen: ## Generate GraphQL types into web/src/generated
	@echo "TODO: graphql-codegen from web/src/graphql/schema.graphql -> web/src/generated"

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
