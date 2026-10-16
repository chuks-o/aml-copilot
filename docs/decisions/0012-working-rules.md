# 0012 — Working rules in CLAUDE.md

**Status:** Accepted · **Ticket:** T04 · **Date:** 2026-10-16

## Context

T04 turns the project's working rules into a root `CLAUDE.md`, which Claude Code reads at the start of every session and people read as the contributing guide. A few rules didn't match the repo as it stood and needed a choice.

## Decision

1. **Decision-record numbering is append-only.** The T02 rationale became [0011](0011-repo-layout-rationale.md), not the requested `0001-repo-layout.md`. `0000-template.md` is the template and is not listed as a decision.
2. **"Only `aml.api` owns database migrations" means the API service owns the schema.** The migration code stays in `aml.db` (run by `aml migrate`). A new import-linter contract, `db-belongs-to-api`, bars every module except `aml.api` and the CLI entry points (`aml.cli`, `aml.__main__`) from importing `aml.db`. Workers that need data go through the API. `tests/test_architecture.py` keeps the contract's module list complete.
3. **Commit format:** conventional commits, `type(scope): summary`, where the scope is the area (`web`, `backend`, `infra`, `docs`, `ci`) and the ticket goes in a `Refs: TNN` trailer. One logical change per commit, so a ticket may be several commits. Earlier `TNN: …` commits stay as they are.
4. **Rules for code that doesn't exist yet** (the generated client in `aml.clients`, the retry helper in `aml.common`) are stated now, marked "added later", so nobody writes a stand-in in the meantime.
5. **CLAUDE.md holds rules plus a short checks table**, so "paste the output" has named commands. The codebase tour stays in the decision records and READMEs.

## Alternatives

- **Renumber 0001–0010 to free 0001.** Rewrites accepted history and breaks the links between records.
- **Move `aml.db` into `aml.api.db`.** Matches the rule's wording literally, but it's a code move in a docs ticket, and it would make `aml migrate` import the web framework's package just to run Alembic.
- **State the database rule without enforcing it.** The first direct database query from a worker would slip through review.
- **Ticket as the commit scope** (`feat(t04): …`). Scope is meant to say *where* the change is; the ticket already has a trailer.
- **commitlint with a git hook.** That's Node tooling and a hook to install, for a one-person repo. Add it if commit messages start drifting.
- **A long CLAUDE.md with a codebase map.** It goes stale quickly, and it's loaded into every session.

## Consequences

- Ingest, scoring and the investigator read and write data through `aml.api` endpoints, not SQL. Bulk ingest of HI-Small will need a bulk endpoint, or a later record granting an exception.
- Changes above 3 files wait for approval, which slows large tickets but keeps every step explained.
