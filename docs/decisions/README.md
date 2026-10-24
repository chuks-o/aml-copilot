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
| [0008](0008-web-app.md) | Web app structure and data clients | Accepted (T02); decision 6 superseded by 0020 |
| [0009](0009-import-boundaries.md) | Import boundaries (import-linter) | Accepted (T02) |
| [0010](0010-quality-gates-and-ci.md) | Lint, type-check, test and CI | Accepted (T02) |
| [0011](0011-repo-layout-rationale.md) | Why the repo is laid out this way | Accepted (T04) |
| [0012](0012-working-rules.md) | Working rules in CLAUDE.md | Accepted (T04); decision 2 amended by 0023, 0026 |
| [0013](0013-local-stack.md) | Local stack with Docker Compose | Accepted (T03, recorded in T04); decision 5 superseded by 0021 |
| [0014](0014-cases-api-contract.md) | Cases API contract (`backend/openapi.yaml`) | Accepted (T05); decision 6 superseded by 0017, decision 10 by 0023 |
| [0015](0015-account-id-format.md) | Account id is `<bank>:<account>`, unpadded bank code | Accepted (T05) |
| [0016](0016-console-graphql-schema.md) | Console GraphQL schema | Accepted (T06); decision 6 refined by 0019 |
| [0017](0017-decisions-close-cases-atomically.md) | Recording a decision closes or escalates the case, atomically | Accepted (T06) |
| [0018](0018-generated-clients.md) | Generated clients, committed and checked for staleness | Accepted (T07); decision 8 amended by 0028 |
| [0019](0019-stub-routes-and-contract-tests.md) | Stub routes from generated models, checked by Schemathesis | Accepted (T08); decision 6 opt-in superseded by 0020 |
| [0020](0020-test-infrastructure.md) | Test infrastructure: tiers, real containers, Jest | Accepted (T09) |
| [0021](0021-rabbitmq-definitions-after-boot.md) | RabbitMQ topology is imported after boot, not at boot | Accepted (T09) |
| [0022](0022-schema-v1.md) | Schema v1 (migration 0001) | Accepted (T10); decision 4 amended by 0029 |
| [0023](0023-seed-and-download.md) | `aml download` and `aml seed`: loading HI-Small with synthetic KYC | Accepted (T11) |
| [0024](0024-account-pagination.md) | Real account transactions and counterparties: keyset pagination over both sides | Accepted (T12) |
| [0025](0025-idempotency.md) | Idempotency-Key: one transaction, wait on the row lock, replay exact bytes | Accepted (T13); decision 9 amended by 0029 |
| [0026](0026-replayer.md) | Transaction replayer: paced, batched, quarantined, resumable | Accepted (T14); decisions 3, 8 superseded by 0027 |
| [0027](0027-streaming-replay.md) | Replay streams a sorted copy instead of loading the file | Accepted (T14 follow-up) |
| [0028](0028-monitoring-rules.md) | Monitoring rules that raise alerts | Accepted (T15); decision 8 amended by 0029, `fan_out` threshold by 0030 |
| [0029](0029-labels-and-time-split.md) | Alert labels and a frozen time split | Accepted (T16) |
| [0030](0030-rules-v2.md) | rules-v2: fan_out at 10 counterparties | Accepted (T16 follow-up) |
| [0031](0031-first-frozen-split.md) | The first frozen split (rules-v2, full replay) | Accepted (T16 follow-up) |
| [0032](0032-golden-set.md) | Golden set v1: a blind, stratified sample labelled in the terminal | Accepted (T17) |
