# 0015 — Account id is `"<bank>:<account>"` with an unpadded bank code

**Status:** Accepted · **Ticket:** T05 · **Date:** 2026-10-16 · **Supersedes:** [0002](0002-account-identity.md)

## Context

[0002](0002-account-identity.md) made the account key `"<bank>|<account>"`, using the bank code exactly as written in `HI-Small_Trans.csv`, and warned never to cast bank codes to integers because `"010"` and `"10"` would collide. T05 puts account ids in URLs (`GET /accounts/{id}`) and joins them to `HI-Small_accounts.csv`, which holds each account's bank and entity. Measured on the full files:

| Check | Result |
| --- | --- |
| Transaction bank codes with a leading `0` | all 5,078,345 rows; lengths 3–7 (`010`, `037861`, `0010057`) |
| Accounts-file bank codes with a leading `0` | 0 of 518,581 (`10`, `37861`) |
| Transaction account keys found in the accounts file as-is | **0** of 515,088 |
| … after stripping leading zeros on both sides | **515,088** of 515,088 |
| Distinct transaction bank codes, raw → stripped | 30,528 → 30,470: 58 banks appear under two spellings |
| Distinct account keys, raw → stripped | 515,088 → 515,088: no merges |

The 58 merged codes are one bank written two ways. For example, `010` and `0010` both resolve to accounts-file bank `10`, "National Bank of Laramie", and every account under either spelling is listed there under `10`. The padding is noise from the data generator, not information.

## Decision

1. **Account id = `"<bank>:<account>"`**, where `bank` is the bank code with leading zeros stripped (`"0"` if nothing is left) and `account` is the upper-case hex account number as given. Example: `10:8000EBD30`. OpenAPI pattern: `^(0|[1-9][0-9]*):[0-9A-F]+$`.
2. **The separator is `:`**, because it's legal unescaped in a URL path segment (RFC 3986 `pchar`). `|` has to be sent as `%7C`.
3. **Both parts stay strings.** Normalising zeros is a deliberate, verified step done once at ingest, not a side effect of casting. Account numbers are hex and must never be parsed as numbers.
4. Ingest normalises the transactions file's bank codes. The accounts file is already in this form.

## Alternatives

- **Keep the raw padded code** (`010:8000EBD30`). It matches nothing in the accounts file, splits 58 banks in two, and every profile lookup would need padding logic in reverse.
- **Keep `|`.** It works in a database, but every URL would carry `%7C` and hand-typed URLs would break.
- **Pad everything to a fixed width.** Codes are 3–7 characters long with no single width, and the accounts file doesn't pad.
- **Integer surrogate ids for accounts.** These are still rejected for the reasons in 0002: unreadable in investigations, and premature.

## Consequences

- 0002's "8 account ids appear at more than one bank" still holds: normalising merges no account keys. Its warning about `"010"` vs `"10"` is replaced: they *are* the same bank.
- Anyone reading the raw transactions file must normalise before joining or comparing. The ingest ticket owns that, with a test on the examples above.
- The T01 notebook keeps its raw `|` keys. It's an exploration record, not a consumer of this format.
