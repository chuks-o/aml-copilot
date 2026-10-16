# Decision records

One file per decision area. Each record states the context, what we chose, what we rejected and why, and the consequences. Supersede a record by adding a new one and marking the old one's status; don't edit history away. Numbers are append-only.

New record: copy [0000-template.md](0000-template.md) to the next free number and add a row below in the same commit.

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-data-and-environment.md) | Data location, credentials, environment, loading | Accepted (T01); env part superseded by 0006 |
| [0002](0002-account-identity.md) | An account is bank + account ID | Superseded by 0015 |
| [0003](0003-pattern-join.md) | Join patterns onto transactions by exact full row | Accepted (T01) |
| [0004](0004-hard-negative-selection.md) | How hard-negative candidates are chosen | Accepted (T01) |
| [0005](0005-repo-layout.md) | Repository layout: web, backend, infra | Accepted (T02) |
| [0006](0006-toolchain-versions.md) | Toolchain versions | Accepted (T02) |
| [0007](0007-backend-package-and-cli.md) | Backend: one `aml` package, one `aml` CLI | Accepted (T02) |
| [0008](0008-web-app.md) | Web app structure and data clients | Accepted (T02) |
| [0009](0009-import-boundaries.md) | Import boundaries (import-linter) | Accepted (T02) |
| [0010](0010-quality-gates-and-ci.md) | Lint, type-check, test and CI | Accepted (T02) |
| [0011](0011-repo-layout-rationale.md) | Why the repo is laid out this way | Accepted (T04) |
| [0012](0012-working-rules.md) | Working rules in CLAUDE.md | Accepted (T04) |
| [0013](0013-local-stack.md) | Local stack with Docker Compose | Accepted (T03, recorded in T04) |
| [0015](0015-account-id-format.md) | Account id is `<bank>:<account>`, unpadded bank code | Accepted (T05) |
