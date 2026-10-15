# Root entry point. Delegates to web/ (pnpm scripts) and backend/ (its Makefile).
# Stub targets print TODO until their ticket lands.

WEB := pnpm --dir web
BACKEND := $(MAKE) --no-print-directory -C backend

.DEFAULT_GOAL := help
.PHONY: help install lint fmt typecheck test codegen up down migrate seed replay eval-smoke

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

up: ## Start the local stack
	@echo "TODO: docker compose -f infra/compose.yaml up -d"

down: ## Stop the local stack
	@echo "TODO: docker compose -f infra/compose.yaml down"

migrate: ## Apply database migrations
	$(BACKEND) migrate

seed: ## Load starter data
	$(BACKEND) seed

replay: ## Replay HI-Small transactions
	$(BACKEND) replay

eval-smoke: ## Quick evaluation run
	$(BACKEND) eval-smoke
