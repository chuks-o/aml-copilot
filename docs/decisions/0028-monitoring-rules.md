# 0028 — Monitoring rules that raise alerts

**Status:** Accepted · **Ticket:** T15 · **Date:** 2026-10-21 · **Amends:** [0018](0018-generated-clients.md) decision 8 (the `httpx` contract)

## Context

T15 adds five transaction-monitoring rules. The replayer (0026, 0027) evaluates them for the accounts each batch touches, and raises alerts through `POST /alerts` with the generated client (0018), so Idempotency-Key handling (0025) dedupes them.

The ticket also specifies the alert key `rule_id:account_id:window_start`, thresholds in YAML set from dev-period data only, hub accounts skipped, and no alert after `ANALYSIS_END`.

## Decision

1. **The rules are pure functions** in `aml.ingest.rules`, over one account's trailing window (no database, clock or I/O):

   | Rule | Fires when | Window |
   | --- | --- | --- |
   | `fan_in` | distinct senders ≥ N | 24 h |
   | `fan_out` | distinct receivers ≥ N | 24 h |
   | `pass_through` | an incoming, then an outgoing payment in the same currency, out within the window, `\|out − in\| ≤ 5%` of in; the trigger is the outgoing leg | 2 h |
   | `structuring` | ≥ 3 amounts in `[90%, 100%)` of a per-currency threshold (USD 10,000; other currencies unchecked) | 48 h |
   | `new_counterparty_burst` | ≥ 5 counterparties never seen in the account's earlier history | 6 h |

   Self-transfers are excluded. Amounts are what *this* account paid or received.
2. **Trailing windows anchored at the trigger: one episode, one alert.**
   - `scan()` checks each new transaction in `(ts, id)` order against the window `(trigger.ts − window, trigger.ts]`, and fires at the first trigger where the rule holds.
   - After an alert, only transactions *after* its trigger count towards the next one, so `window_start = max(trigger.ts − window, previous trigger)`.
   - The window only looks backwards, so **the same data gives the same hits however it was batched**. `test_hits_do_not_depend_on_how_transactions_were_batched` checks this.
   - That makes the idempotency key deterministic, and a re-run replays existing keys instead of creating alerts.
   - **Changed during implementation from the plan's** "anchor at the earliest qualifying transaction in the history seen so far". That depended on where batch boundaries fell, which depends on wall-clock pacing, and would have given different keys, and duplicate alerts, from run to run.
3. **The previous trigger per (rule, account) is read from `alerts`** (`max(window_end) − 1 min`; `POST /alerts` ends a window one minute after its last cited transaction). It's cached for the run, so it survives restarts.
4. **The monitor** (`aml.ingest.monitor`) runs after each committed batch:
   1. it finds the touched accounts, minus hubs, and their new transactions before `ANALYSIS_END`;
   2. it loads those accounts' full history in one query (`UNION ALL` of both sides, `= ANY(accounts)`);
   3. it scans each rule;
   4. it posts the hits through `create_alert.asyncio_detailed`, with up to 16 requests in flight and `asyncio.run` per batch.

   The alert payload:
   - `model_version` = `rules-v1:<rule_id>`;
   - `typology` = `FAN_IN` / `FAN_OUT`, or null for the other rules;
   - `reason` is one sentence;
   - `transaction_ids` = the cited transactions, at most 500;
   - `score` = `min(1, observed / (2 × threshold))` (pass-through: `0.5 + 0.5 × (1 − difference / tolerance)`). It's for queue ordering only; the scoring model replaces it.
5. **`ANALYSIS_END` is enforced once, in the monitor.** Triggers at or after it are ignored, and history is cut at it. The rules stay pure.
6. **Segmentation: `is_high_volume` accounts are skipped.** The 15 bank-70 hubs have 6,468 to 169,756 transactions each. Thresholds tuned for ordinary accounts would fire on them continuously. In practice such accounts are monitored by a separate process, with its own thresholds and peer groups, which is out of scope here. `skip_high_volume: true` in `rules.yaml`.
7. **Thresholds live in `aml/ingest/rules.yaml`**, shipped in the wheel (checked) and loaded and validated by pydantic (`load_config`). PyYAML moves from dev to runtime dependencies. `version: rules-v1` goes into every alert's `model_version`, so alerts from different thresholds are never mixed.
8. **The dev/test split is by time:** dev = 2022-09-01 up to 2022-09-06, test = 2022-09-06 up to `ANALYSIS_END`. A random split by account or row would leak multi-day, multi-account schemes into both sides.
9. **History comes from the database**, which the replayer is allowed to read (0026). `GET /accounts/{id}/transactions` per account per batch would be thousands of HTTP calls.
10. **The `http-only-via-clients` contract now forbids *direct* `httpx` imports only** (`allow_indirect_imports = true`). Its purpose is that HTTP goes *through* `aml.clients`, so `aml.ingest → aml.clients → httpx` is the intended path. It only surfaced now because nothing called `aml.clients` before. A planted `import httpx` in the monitor is still reported (`aml.ingest.monitor -> httpx`).

## Evidence

**Unit tests** (`tests/unit/test_rules.py`, 26 tests). Each rule has positive, negative and boundary cases:
- fan-in and fan-out at N and N−1;
- distinct counterparties versus repeat payments;
- the 24 h edge, at 23 h 56 min versus 24 h 4 min;
- pass-through at exactly ±5%, and at ±5.001%;
- structuring at exactly 90% of the threshold, and at the threshold itself;
- the burst, with counterparties seen three days earlier.

Plus the scan semantics: one episode makes one alert, hits are independent of batching, and window anchoring.

**Integration** (`tests/integration/test_monitoring.py`, with a live API on a scratch database):
- a crafted dataset raises exactly `fan_in` and `new_counterparty_burst` for the fan target and `pass_through` for the conduit;
- the hub and a post-`ANALYSIS_END` fan-in raise nothing (with the hub skip planted out, the hub alerts and the test fails);
- re-replaying everything from the start creates no new alerts.

**Dev-period volume per threshold** (`make tune-rules`: 515,073 non-hub accounts, dev rows only, 542 s, 151 MB peak):

| Setting | Alerts | Per day | Accounts | Citing laundering |
| --- | ---: | ---: | ---: | ---: |
| fan_in N=3 | 52,210 | 10,442 | 36,240 | 1.1% |
| fan_in N=4 | 14,638 | 2,928 | 8,499 | 2.0% |
| **fan_in N=5** | 7,542 | 1,508 | 3,669 | 2.6% |
| fan_in N=6 | 5,226 | 1,045 | 2,453 | 2.9% |
| fan_in N=8 | 3,226 | 645 | 1,594 | 3.0% |
| fan_in N=10 | 2,323 | 465 | 1,266 | 3.2% |
| fan_out N=3 | 152,270 | 30,454 | 41,170 | 0.2% |
| **fan_out N=5** | 33,263 | 6,653 | 13,213 | 0.2% |
| fan_out N=8 | 5,360 | 1,072 | 2,772 | 0.3% |
| fan_out N=10 | 1,823 | 365 | 1,071 | 0.5% |
| pass_through | 3,471 | 694 | 3,145 | 0.2% |
| structuring (USD) | 1,229 | 246 | 1,106 | 0.0% |
| new_counterparty_burst | 8,699 | 1,740 | 4,976 | 1.7% |

"Citing laundering" is the share of alerts with at least one dev-period laundering transaction among their cited ids. That's against a base rate of roughly 0.1% of transactions.

- **`fan_in` at 5 carries signal:** about 25× the base rate. Raising N buys little extra precision for far fewer alerts.
- **`fan_out` at 5 is close to noise:** 6,653 alerts a day at 0.2%. Many clean accounts pay five or more counterparties a day.
- **`structuring` found nothing laundering-related** in dev with a USD 10,000 threshold. Either HI-Small's generator doesn't structure, or it does so in other currencies.

`rules-v1` keeps the ticket's starting point (`fan_in` and `fan_out` at 5). **Recommended for `rules-v2`, from dev only:** `fan_out` N = 8 to 10 (365 to 1,072 a day instead of 6,653), and decide whether `structuring` earns its place.

## How to tune without test-period labels

1. **Freeze the split first.** The test period's rows and labels are not read by the tuning script (`dev_period` in `rules.yaml`); they're scored once, at the end.
2. **Set an alert budget from capacity:** analysts × cases per analyst per day. A threshold is unacceptable if its volume exceeds its share of that budget, however good its precision.
3. **On dev only, sweep each threshold** and read volume against a quality proxy: here, the share of alerts touching known dev laundering. Without any labels, use proxies that need none: alert concentration (alerts per account), overlap with other rules, and the share of alerts on accounts with KYC inconsistencies (0023).
4. **Pick the knee:** the point where tightening the threshold cuts volume much faster than it improves the proxy. For `fan_in` that's N ≈ 5 to 6; for `fan_out`, N ≈ 8 to 10.
5. **Check stability within dev, day by day.** A threshold whose volume or proxy swings between days is fitting noise.
6. **Freeze the result as a new `version`** in `rules.yaml`, then score the test period once. If the test result disappoints, the fix is a new dev-period analysis, never a threshold adjusted against test labels.

## Alternatives

- **Sliding windows ending at each new transaction, with the key from that window.** Every later transaction in an episode gets a new key, and so a new alert.
- **Fixed calendar windows (per day).** They miss patterns that cross midnight.
- **REST reads of history.** Thousands of calls per batch for data the replayer may read directly.
- **The sync client, one alert at a time.** A batch with hundreds of hits would stall the replay.
- **A constant score.** It gives the queue nothing to sort by.
- **One structuring threshold for all currencies.** USD 10,000 and JPY 10,000 aren't the same money.
- **Applying the same thresholds to hubs.** They'd flood the queue from 15 accounts.
- **A random dev/test split.** Schemes leak across it.
- **Tuning on the whole period.** Every reported number would be optimistic by construction.

## Consequences

- At `rules-v1`'s thresholds, dev produces about 10,800 alerts a day across rules, two thirds of them from `fan_out`. That's far beyond any analyst budget, which is the point of the sweep: tightening `fan_out` is the first `rules-v2` decision.
- **The 30-minute replay** (alerts per rule, rule-to-alert lag p95) **has not been run yet.** On the development Mac, free disk was 657 MB, with 3.2 GB of swap used by other applications; the run writes about 1.2 GB into Docker. It's the next step once there is space. `aml replay --limit 3600000` against a migrated stack, with `aml api` running the current code.
- `scan()` is O(window × triggers) per account. That's fine for non-hub accounts (at most 394 transactions); hubs would need an incremental implementation, and are skipped.
