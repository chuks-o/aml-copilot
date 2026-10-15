# 0009 — Import boundaries (import-linter)

**Status:** Accepted · **Ticket:** T02 · **Date:** 2026-10-15

## Context

`ingest`, `investigator`, `scoring` and `evals` should depend on the API's *contract* (HTTP), not its internals, so each can later run as a separate process. Evals must stay a leaf, so production code never depends on test harnesses.

## Decisions

The contracts live in `[tool.importlinter]` in `backend/pyproject.toml` (one config file rather than a separate `.importlinter`), and `make lint` runs `lint-imports`. All three are forbidden contracts. These include indirect imports, so `scoring → clients → api` is also caught.

| id | Rule |
| --- | --- |
| `workers-use-http` | `aml.ingest`, `aml.investigator`, `aml.scoring` and `aml.evals` must not import `aml.api`. They call it through `aml.clients`. |
| `evals-is-a-leaf` | No other `aml` module imports `aml.evals`. Tests live outside the package, so they're exempt. |
| `common-is-foundation` | `aml.common` imports nothing else from `aml`. This contract was added beyond the ticket and approved. |

1. **`aml.cli → aml.evals` is an explicit exception.** The `aml eval` command must reach the evals code. import-linter also sees imports inside functions, so a lazy import wouldn't avoid the rule.
   - `unmatched_ignore_imports_alerting = "none"`, because today's stub doesn't import evals yet.
   - _Rejected:_ shelling out to `python -m aml.evals` only to satisfy the linter, which hides the dependency instead of declaring it.
2. **Contract lists are explicit, and a test guards them.** Forbidden contracts name modules one by one. `tests/test_architecture.py` therefore fails if a new top-level `aml` module isn't added to `evals-is-a-leaf`'s sources and `common-is-foundation`'s forbidden list.
3. **Verified:** a planted violation was checked against each contract (`scoring → api.app`, `api → evals`, `common → data`). Each made exactly its own contract `BROKEN`, and each was reverted.

## Consequences

Shared request and response models can't live in `aml.api` if `aml.clients` needs them (because of indirect imports). They belong in `aml.common` or a future schema module.
