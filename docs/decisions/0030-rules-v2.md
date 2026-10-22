# 0030 — rules-v2: fan_out at 10 counterparties

**Status:** Accepted · **Ticket:** T16 follow-up · **Date:** 2026-10-22 · **Amends:** [0028](0028-monitoring-rules.md) (the `fan_out` threshold)

## Context

0029 freezes labels and the dev/test split over the alerts the rules raise, so the rules that run in that replay are the ones every later evaluation is measured against. Under `rules-v1`, `fan_out` at 5 counterparties produced 6,653 dev alerts a day, and 0.2% of them cited laundering: close to the transaction base rate of about 0.1%, and two thirds of all alerts. 0028 recommended raising it before anything was built on it.

## Decision

1. **`fan_out.min_counterparties` goes from 5 to 10**, and `version` becomes `rules-v2`, so every alert's `model_version` says which thresholds raised it.
2. **The choice comes only from the dev-period sweep in 0028** (09-01 up to 09-06, inside the frozen dev period): N=10 gives 365 alerts a day at 0.5% citing laundering, against 1,072 a day at 0.3% for N=8. Precision keeps improving up to 10 while volume drops threefold, so 10 is past the knee, not at it. Nothing from the test period was read.
3. **Every other threshold is unchanged.** `structuring` (no laundering among its dev alerts) stays, and is revisited once labels exist. It's cheap (246 a day), and dropping a typology on a proxy signal of zero would be a decision made without evidence either way.
4. `tests/integration/test_monitoring.py` reads the version from the packaged `rules.yaml` instead of hardcoding it.

## Alternatives

- **N=8.** Three times the volume for a lower proxy precision.
- **Keeping v1 and freezing the split on it.** The frozen labels would be dominated by a rule that's close to noise, and moving to v2 later would mean re-freezing.
- **Retuning every rule now.** Only `fan_out` was clearly out of line; the others are revisited against real labels, still on dev only.

## Consequences

- Expected dev volume falls from about 10,800 to about 4,500 alerts a day across rules (0028's table), with `fan_in` now the largest source.
- `rules-v1` alerts aren't produced again; any already stored stay distinguishable by `model_version`.
