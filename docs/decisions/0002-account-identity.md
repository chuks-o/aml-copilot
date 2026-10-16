# 0002 — An account is identified by bank + account ID

**Status:** Superseded by [0015](0015-account-id-format.md) · **Ticket:** T01 · **Date:** 2026-10-15

## Context
Each transaction has `From Bank`, `Account`, `To Bank`, `Account`. It is unclear whether account IDs are globally unique.

## Decision
The account key is the composite `"<bank>|<account>"`, with both parts kept as strings.

## Evidence (backend/notebooks/00_explore.ipynb, section 3)
There are 515,088 distinct (bank, account) pairs but only 515,080 distinct account IDs: **8 account IDs appear at more than one bank.**

## Alternatives rejected
- **Account ID alone:** it would silently merge 8 pairs of unrelated accounts. That's rare, but a merged account in an investigation is a correctness bug, not noise.
- **Integer surrogate IDs:** useful later for graph libraries, but premature now and harder to read in tables.

## Consequences
Every later component (features, graph, alert records, copilot) uses the composite key. Bank codes must never be cast to integers, because `"010"` and `"10"` would collide.
