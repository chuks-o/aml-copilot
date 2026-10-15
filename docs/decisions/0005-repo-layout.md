# 0005 — Repository layout: web, backend, infra

**Status:** Accepted · **Ticket:** T02 · **Date:** 2026-10-15

## Context

The system has one TypeScript web app (console, and later the GraphQL API) and one Python backend. An earlier T02 draft used a pnpm/Turborepo + uv-workspace monorepo with separate apps, services and packages. That draft was discarded before it was committed, in favour of this simpler layout.

## Decisions

1. **The top level holds only:** `web/`, `backend/`, `infra/`, `docs/decisions/`, `.github/workflows/`, `Makefile`, `README.md`, `CLAUDE.md`, `.env.example` and `.gitignore` (plus the git-ignored `.env`). Toolchain files (`.nvmrc`, `.python-version`, Prettier config) live inside the half they configure.
2. **Two independent projects.** `web/` has its own `package.json` and `pnpm-lock.yaml`. `backend/` has its own `pyproject.toml` and `uv.lock`. There are no workspaces and no Turborepo; with one project per language, they'd add machinery without benefit.
3. **The root Makefile delegates:**
   - `pnpm --dir web run <script>` for web (pnpm scripts are web's native interface);
   - `$(MAKE) -C backend <target>` for backend, so `make test` also works inside `backend/`.
   - _Rejected:_ a `web/Makefile` that only wraps pnpm.
   - _Rejected:_ inlining every command in the root Makefile, which makes the halves less self-contained.
4. **Unbuilt targets:**
   - `codegen`, `up` and `down` print TODO. Docker isn't installed yet, so `infra/` holds only a README.
   - `migrate`, `seed`, `replay` and `eval-smoke` are already wired to the real `aml` CLI commands, which print "not implemented".
5. **T01 artefacts moved:**
   - `notebooks/00_explore.ipynb` → `backend/notebooks/` (with `git mv`);
   - `data/README.md` → `backend/data/`;
   - `data/raw/` → `backend/data/raw/` (git-ignored).

   The notebook finds `data/` relative to its parent folder, so it needed no path changes. It was re-executed under Python 3.12 and its checks cell passes. A stray edit, `` color=``SERIES`` ``, was fixed back to `color=SERIES`.
6. **`CLAUDE.md` is a one-line placeholder** until T04.
   - _Rejected:_ leaving it absent, which would leave the agreed root layout incomplete.

## Consequences

- Two lockfiles and two toolchains, each owned by its half.
- Cross-cutting changes (for example a GraphQL type that the backend also feeds) touch both halves in one commit, which is the main reason to keep a single repo.
