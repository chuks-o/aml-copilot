# 0004 — How hard-negative candidates are chosen

**Status:** Accepted · **Ticket:** T01 · **Date:** 2026-10-15

## Context
We want clean accounts that look suspicious ("hard negatives") to test models and the investigation copilot against false positives. "Suspicious by volume" needs a concrete definition.

## Decisions
1. **Volume = number of distinct counterparties** (tie-broken by transaction count), counted separately as senders (in-degree) and receivers (out-degree). Self-transfers are excluded.
   - *Rejected:* summed amounts. They span 15 currencies, and FX conversion is out of scope for T01. Likewise, laundering *rate* is measured by transaction count, not money.
   - *Rejected:* raw transaction count. It rewards accounts that pay the same few counterparties repeatedly, which doesn't look like any laundering typology.
2. **Candidates must have zero laundering transactions in either direction**, not just "the account isn't flagged". Labels exist only at transaction level.
3. **Take the top 3 by distinct senders (fan-in-like) and the top 2 by distinct receivers (fan-out-like).**
   - *Rejected:* a single combined ranking. It returns five near-identical collector accounts, and hard negatives should cover more than one shape.
4. **No special rule for mega-hubs.** The plan anticipated excluding bank-internal hubs, but the data made that unnecessary: every one of the large bank-070 hubs (up to ~170k transactions) touches laundering, so the zero-laundering filter already removes them.

## Evidence
The chosen accounts have 84–93 distinct senders and 34–35 distinct receivers. The largest fan-in and fan-out in the patterns file each have 16. One candidate received all 84 of its payments within 29 minutes.

## Consequences
- Later tickets can scale the same rule to hundreds of candidates.
- "Clean" is trustworthy only because the data is synthetic. On real data, unlabelled means not caught, and the rule would have to change.
