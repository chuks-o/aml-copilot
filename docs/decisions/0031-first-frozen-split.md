# 0031 — The first frozen split (rules-v2, full replay)

**Status:** Accepted · **Ticket:** T16 follow-up · **Date:** 2026-10-22

## Context

0029 built the labelling and the freeze, but left `backend/data/splits.json` uncommitted until real alerts existed. This record documents the run that produced them, and what every later evaluation is now measured against.

## Decision

1. **`splits.json` is frozen from a full replay of HI-Small with `rules-v2`** (0030): all 5,078,345 rows, `--rate 0 --compression 0 --corrupt-rate 0`, through a local `aml api` on the current code, into the `make up` Postgres (migrated to 0003, transactions truncated first).
2. **The frozen numbers:**

   | Split | Days | Alerts | Positives | Positive rate | heldout_cycle |
   | --- | --- | ---: | ---: | ---: | ---: |
   | dev | 09-01 up to 09-07 | 26,588 | 846 | 3.18% | 5 |
   | test | 09-07 up to 09-11 | 17,445 | 620 | 3.55% | 3 |

   SHA-256 `605e8446275d197018cddf9e08180bdced6939a52eaf88a721afdc555df9ba67`. The latest alert was at 2022-09-10 23:59, before `ANALYSIS_END`.
3. **Alerts per rule:** `fan_in` 15,146, `new_counterparty_burst` 14,390, `pass_through` 6,934, `structuring` 4,337, `fan_out` 3,226. That's about 4,400 a day, as 0030 predicted.
4. **Typology labels of the positives:** `UNLISTED` 1,190 of 1,466 (81%). The listed ones, dev / test: `SCATTER_GATHER` 32 / 46, `GATHER_SCATTER` 29 / 15, `FAN_IN` 23 / 21, `STACK` 12 / 34, `FAN_OUT` 12 / 11, `RANDOM` 11 / 2, `CYCLE` 8 / 5, `BIPARTITE` 5 / 10.

## Findings

- **The rules' precision is about 3%** on the 72 h account label, against about 0.1% laundering transactions. That's the baseline the scoring model has to beat on test.
- **Most positives are `UNLISTED`.** The patterns file lists only part of HI-Small's laundering, so per-typology results rest on dozens of alerts, not hundreds. Any per-typology metric needs its count beside it. `heldout_cycle` (8 alerts) is a sanity check, not a measurement.
- **Positive rates in dev and test are close** (3.2% against 3.6%), so the time split doesn't hide a large shift in base rate.
- **The monitor doesn't keep up at full speed.** Rule-to-alert lag p95 was 0.4 s at the start, 3.7 s after 3.4 million rows, and 148 s over the last 1.6 million. The cause is the per-batch history query (both sides of every touched account's full history), which grows with the data. Throughput fell from about 4,300 to about 900 rows a second. The real-time target needs an incremental history (a per-account window kept in memory, or a bounded `ts >` cut-off) before replays run at speed. That's a separate change.
- **This machine can only just run it.** The replay was paused once at 3.48 million rows, when macOS swap (which lives on the same disk) had cut free space to 1.8 GB. It then resumed from its watermark behind an automatic pause at 1.2 GB free, which worked as designed: no rows were lost, quarantined or duplicated. Peak memory of the replay process wasn't measured.

## Alternatives

- **Freezing on `rules-v1`.** Rejected in 0030.
- **Waiting for the incremental monitor before freezing.** It changes speed, not which alerts fire, since the rules are pure and independent of batching (0028). So the frozen labels stay valid once it lands, as long as `--check` passes.

## Consequences

- `make -C backend check-splits` now compares against a real file, and `tests/unit/test_labels.py` checks `rules.yaml`'s dev period against it.
- Rebuilding the database means replaying again (close to 2 hours here, across both runs) before `--check` can pass. The uuid5 alert ids (0029) make the result identical.
- Any change to rules, the label window or the data that moves a label fails `--check`, and needs a new freeze and a record like this one.
