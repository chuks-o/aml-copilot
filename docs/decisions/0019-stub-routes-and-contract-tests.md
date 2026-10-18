# 0019 — Stub routes from generated models, checked by Schemathesis

**Status:** Accepted · **Ticket:** T08 · **Date:** 2026-10-17 · **Refines:** [0016](0016-console-graphql-schema.md) decision 6

## Context

`aml.api` needs every operation in `backend/openapi.yaml` (0014, 0017) served before the database exists (T10), so the BFF and workers can integrate against real validation and real response shapes. The models must come from the spec, not be hand-written copies. A contract test has to prove the server keeps the spec's promises, against a running server.

## Decision

1. **Server models are generated** by datamodel-code-generator 0.83.0 into `backend/src/aml/api/schemas.py`, as part of `make codegen`, committed, and covered by `make codegen-check`. The flags:
   - `--disable-timestamp`, because the default header timestamp would change every run;
   - `--use-unique-items-as-set`, because otherwise `uniqueItems` is silently dropped;
   - `--use-type-alias`, so constrained scalars become `type PageLimit = Annotated[int, Field(ge=1, le=500)]`, which FastAPI accepts for query and header parameters (tested before adopting; the flag is marked experimental);
   - then our locked `ruff format`.

   The file is excluded from Ruff lint and kept under `mypy --strict`. Routes use only these models.
2. **Parameter constraints moved into named schemas** in the spec: `PageLimit`, `Cursor`, `WindowHours`, `CounterpartyLimit`, `IdempotencyKeyValue`, `ETagValue` and `EdgeDirection`, with `from`, `to` and `as_of` referencing `Timestamp`.
   - The generator only models `components/schemas`, so inline parameter schemas would have meant hand-coded bounds.
   - No meaning changed, so the contract version goes to 0.2.1.
   - The same pass fixed `example: Canada Bank #27`, which YAML had been reading as `Canada Bank` plus a comment.
3. **Bad input maps to the status the spec documents**, in `aml.api.problems`. Every error is `application/problem+json`.

   | Bad input | Status |
   | --- | --- |
   | Path parameter, malformed header, missing or invalid `Idempotency-Key` | 400 |
   | Missing `If-Match` | 428 |
   | Query parameter or body (including malformed JSON, and `from` ≥ `to`) | 422 `ValidationProblem`, with JSON-Pointer `errors` |
   | Wrong method | 405 |
   | Unexpected exception | 500 |

   A problem's `instance` is the request path **re-encoded** to RFC 3986 path characters. Schemathesis found that echoing the decoded path (`/accounts/\u0084`) breaks `format: uri-reference`.
4. **Placeholders are stateless and built from the generated models** (`aml.api.placeholders`), so they validate on construction and again on the way out.
   - Ids echo the request, or come from `uuid5(Idempotency-Key)`, so a retried create returns the same id.
   - Each write stub assumes the state that makes its rules testable:
     - `PATCH …/status` treats the case as `OPEN` at version 1;
     - `POST …/decisions` treats it as `COMPLETE` at version 1, with recommendation `ESCALATE`.
   - Stubs never return 404, 429 or 503, and `Idempotency-Key` is required but not stored.
5. **The routes are checked against the spec** (`tests/test_api_routes.py`): exactly one route per `operationId`, the same method, path and success status, and the same query parameter names, required flags and **defaults**. Defaults are the one thing written in route signatures, so this test is what keeps `limit = 50` equal to the spec's.
6. **Contract test:** `tests/test_contract.py`, marker `contract`.
   - It starts uvicorn on a free local port in a background thread and runs the Schemathesis 4.29.0 CLI against it, with `backend/schemathesis.toml`.
   - Config: only the three checks (`not_a_server_error`, `status_code_conformance`, `response_schema_conformance`), 100 examples per operation, seed `20220901`, and no example database, so runs are deterministic.
   - `make contract` runs it, `make contract SEED=<n>` explores other inputs, and CI runs it in the backend job.
   - It's excluded from the default `pytest` run (`-m "not contract"`).
   - Hypothesis is pinned to 6.168.3 (two weeks old), because the lock had picked a release from the day before.
7. **The opening alert of a case is the earliest-created one**, not position 0 of `alert_ids`. `uniqueItems` makes `alert_ids` a set, so the client's order isn't kept, and the stub returns ids sorted. This refines 0016 decision 6 ("the BFF returns the first").
8. **The "Schema validation mismatch" warning on `PATCH …/status` and `POST …/decisions` is expected.**
   - Schemathesis warns when most *valid* generated requests are rejected. Counted from its NDJSON report, the valid requests got:
     - `PATCH`: 200 ×36, 409 ×29, 412 ×41;
     - `POST`: 200 ×73, 412 ×78.
   - These are concurrency (random `If-Match` versions are stale) and state-machine refusals, not schema validation. A real server will behave the same way.
   - The success paths are covered by `tests/test_api_stubs.py`.

## Alternatives

- **Hand-written Pydantic models.** Forbidden by the ticket: two copies of every constraint.
- **Runtime request validation from the spec** (`openapi-core` middleware). Faithful, but handlers get untyped dicts, and it's a second validation layer on top of FastAPI's.
- **Connexion** (spec-first routing). It would replace FastAPI (0007) for routing alone.
- **Reusing the generated client's `attrs` models.** FastAPI can't validate with them, and the server would depend on the client.
- **A helper that reads parameter bounds out of the YAML at import time.** No static types, and a mini-framework to maintain.
- **FastAPI's default errors** (422 + `{"detail": …}` for everything). Wrong status for path and header errors, and wrong shape and content type everywhere.
- **An in-memory store behind the stubs.** A fake database that T10 deletes, and it makes generated tests depend on order.
- **In-process ASGI calls** instead of a live server. They skip real HTTP encoding, which is where the `instance` bug lived.
- **Testing against `make up`.** Needs Docker for every run and Postgres the stubs don't use.
- **pytest-native `@schema.parametrize()`.** Per-operation test ids, but no Schemathesis summary, and config split between code and TOML.
- **A random seed in CI.** It finds more over time, but a red run isn't reproducible from the log.
- **Disabling phases or checks to get green.** The one real bug found came from the coverage and fuzzing phases' negative tests.
- **Repeating parameter defaults beside each `$ref`.** openapi-python-client doesn't follow a `$ref` to find a parameter default, so the generated client now sends `UNSET` instead of `limit=50`. Behaviour is the same (the server applies the default); only the client docstring loses it. That's not worth a second copy of each default.

## Consequences

- T10 replaces `placeholders` with database reads and writes behind the same route signatures. The route-alignment, stub and contract tests keep running unchanged, with the stubs' assumed states becoming fixtures.
- Any new operation needs a route with the spec's `operationId`. `test_every_operation_has_exactly_one_route` fails until it exists.
- `make contract` takes about 15 s locally (2,550 generated requests). It runs on every CI push.
- The `_IncludedRouter` detail: FastAPI 0.143 wraps included routers lazily. The route test walks them by duck typing (`original_router`), not by importing the private class.
