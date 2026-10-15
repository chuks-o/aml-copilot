# 0010 — Lint, type-check, test and CI

**Status:** Accepted · **Ticket:** T02 · **Date:** 2026-10-15

## Decisions

- **Backend:**
  - Ruff with `E,F,W,I,B,UP,SIM,RUF,N,S` (`S101` allowed in tests), line length 100.
  - `ruff format --check` and `lint-imports` in `make lint`.
  - `mypy --strict` with the pydantic plugin over `src` and `tests`.
  - pytest with FastAPI's `TestClient` and Typer's `CliRunner`.
- **Web:**
  - `strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` and `verbatimModuleSyntax`.
  - typescript-eslint `strictTypeChecked` + `stylisticTypeChecked` + `eslint-config-next/core-web-vitals`, with `--max-warnings=0`.
  - Prettier check as part of `lint`.
  - `next typegen && tsc --noEmit` for type-checking.
- _Rejected:_ default rule sets. Tightening later means fixing a whole codebase; tightening now costs nothing.
- **CI (`.github/workflows/ci.yml`):**
  - Two parallel jobs, `web` and `backend`, on every push to `main` and every PR. Each takes its toolchain version from the half's own files (`web/.nvmrc`, `web/package.json` `packageManager`, `backend/.python-version`) and installs from lockfiles only.
  - The web job also runs `next build`.
  - _Rejected:_ path filters that skip an unchanged half. They save minutes, but complicate required status checks for no gain at this size.
