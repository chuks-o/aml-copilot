# 0029 — Alert labels and a frozen time split

**Status:** Accepted · **Ticket:** T16 · **Date:** 2026-10-21 · **Amends:** [0022](0022-schema-v1.md) decision 4 (split values), [0025](0025-idempotency.md) decision 9 (`triggered_at`, alert ids), [0028](0028-monitoring-rules.md) decision 8 (dev period)

## Context

Every later evaluation scores something against alerts: the scoring model, the investigator agent and the rule versions. That needs ground truth on each alert, which is whether it was right and which typology, plus a fixed rule for which alerts we may learn from and which we only score on. T16 sets both and freezes them, so that a number reported in week 6 means the same thing as one in week 2.

### Leakage, and why the split is by time

**Leakage** is when information that wouldn't exist at decision time gets into training, tuning or the inputs. The measured performance is then better than the system will ever be in use. It comes in three forms here:

1. **Across the split.** A laundering scheme in HI-Small spans days and several accounts (a fan-in feeds a cycle, which feeds a fan-out). With a random split by alert or account, one scheme lands on both sides. The model then "recognises" a test alert because it trained on that alert's siblings. That's memorisation, not detection.
2. **From the future.** Real monitoring only sees the past. A dev period strictly before the test period reproduces that: anything learned or tuned on dev is applied to days it has never seen, which is the actual deployment situation. It also exposes drift, if the test days behave differently.
3. **Through the inputs.** If a feature or prompt carries the date, or the day's position in the period, a model can learn "late in the period means positive" (laundering density isn't uniform over HI-Small's days). That shortcut separates dev from test perfectly and means nothing in production, where every day is "today".

A time split removes (1) and (2) for anything that doesn't cross the boundary. (3) needs its own guard, decision 7.

## Decision

1. **`triggered_at` is dataset time.** `POST /alerts` sets it to the latest cited transaction's `ts`, not `now()`. A replay runs faster than real time and can be rerun, so wall-clock time says nothing about where an alert falls in the data.
   - Migration `0003` adds `alerts.created_at` (wall clock, default `now()`), which the REST `created_at` now reads.
   - **Amends 0025 decision 9** ("`triggered_at` = now").
2. **Alert ids are deterministic:** `uuid5(ALERT_IDS, idempotency_key)`. A rebuilt database (re-seed, re-replay) gives every alert the same id, so the frozen hash still describes it. With `gen_random_uuid()`, every rebuild would "change" every label.
3. **Label: positive if the alerted account has a laundering transaction on either side in `(triggered_at − 72 h, triggered_at]`.**
   - Either side, because a mule receives and a source sends; both are laundering activity on the account.
   - 72 h covers the longest rule window (48 h structuring) with a margin. Anything older is a different episode.
   - Open at the far end, so exactly 72 h earlier is outside. The integration test pins that boundary.
   - The window ends at the trigger, so the label never looks forward in time.
4. **`typology_label`** is the most common listed pattern in that window, with ties broken alphabetically so it's deterministic. It's `UNLISTED` (laundering not in the patterns file, 0023) if none are listed, and null for negatives.
   - Migration `0003` adds `UNLISTED` to the CHECK, plus `ck_alerts_typology_label_on_positives` (`typology_label IS NULL OR label`). The integration test hit this constraint when it tried to unmark a positive by hand.
5. **The split.** The normal-activity period runs from the first data day (2022-09-01) up to `ANALYSIS_END` (2022-09-11, 0023): 10 calendar days.
   - The first `floor(0.6 × 10)` = 6 days are `dev` (09-01 up to 09-07), the rest `test` (09-07 up to 09-11).
   - Whole UTC days, so the boundary doesn't move with the alert count.
   - The values are `dev` and `test`, replacing 0022's `train` / `validation` / `test` (**amends 0022 decision 4**). There's no separate validation set: whatever tunes against dev does its own cross-validation within dev, by day.
   - An alert at or after `ANALYSIS_END` stops `aml label` with an error. It never gets silently left out.
6. **`heldout_cycle`**: positives whose window laundering is *all* `CYCLE`. They're never trained or tuned on, in either split. This tests a typology the system has never learned from. A mixed window (CYCLE plus FAN_IN) isn't held out, because it also teaches FAN_IN.
7. **The leakage guard** (`aml.evals.leakage`, `tests/unit/test_leakage.py`). `INPUTS` registers a builder for every model or prompt input; today that's the rule alert payloads. `find_time_leaks` walks each input and fails on:
   - any `datetime`, `date` or `timedelta` value;
   - ISO-date text;
   - a key naming time or position (`date`, `day`, `hours_since_start`, `position`, …).

   The test fails if the registry is empty, and a set of planted leaks shows that each kind is caught. Every new feature or prompt builder must be added to `INPUTS` (a CLAUDE.md rule).
   - Durations *between* events in one alert (for example "the out-leg came 40 minutes after the in-leg") are allowed: they're about the behaviour, not about the calendar. They'll go in under a non-time key, and the guard's planted cases will grow with them.
8. **The freeze.** `aml label` computes the labels, writes them to `alerts` and writes `backend/data/splits.json`, in one transaction plus a file write after the commit. The file holds:
   - the period, the window and the dev share;
   - per split: alerts, positives, positive rate and the held-out count;
   - the SHA-256 of the sorted `alert_id,label,split` lines.

   `aml label --check` (`make -C backend check-splits`) fails if the labels recomputed from the data, the labels stored on `alerts`, or the period no longer match the file. A test checks each of the three. Changing labels is allowed, but only deliberately: rerun `aml label`, then commit the new file with a decision record.
9. **`rules.yaml`'s `dev_period` now ends at 2022-09-07** (**amends 0028 decision 8**, which used 09-06). A unit test fails if it differs from the split, or from `splits.json` once that exists. T15's thresholds were tuned on 09-01 up to 09-06, a subset of the new dev period, so none of that work touched test days.
10. **No new import exception:** `aml.evals.labels` takes a psycopg connection from the CLI and never imports `aml.db`. The CLI's existing `aml.cli → aml.evals` exception (0009 decision 1) now also covers submodules (`aml.evals.**`). A planted `aml.ingest → aml.evals` import still breaks the contract.

## Evidence

- **Unit tests** (`test_labels.py`, `test_leakage.py`, 31 tests):
  - the label rules, including ties, all-unlisted and mixed CYCLE;
  - the split arithmetic and its boundaries (09-06 23:59 is dev, 09-07 00:00 is test, `ANALYSIS_END` is an error);
  - the hash ignores row order but changes with any label or split;
  - `rules.yaml` agrees with the split;
  - the leakage cases.
- **Integration** (`test_labels.py`, scratch database): four crafted alerts are labelled `FAN_IN`/dev, `CYCLE`/test/held out, negative at exactly 72 h, and `UNLISTED`/test, with the expected counts in the file.
  - `--check` passes on unchanged data.
  - It fails when a stored split is edited by hand, and when a new laundering transaction would relabel an alert.
  - It refuses before anything is frozen.
  - An alert after `ANALYSIS_END` stops the run, and no file is written.

## Alternatives

- **A random or per-account split.** Leaks schemes across the boundary (form 1 above).
- **A split by alert count** (the first 60% of alerts). The boundary would move every time a rule changed volume, so the split wouldn't stay frozen.
- **A label from the cited transactions only.** It rewards the rule for citing well rather than for being on the right account at the right time, and it changes when the citation cap (500) cuts the list.
- **A forward-looking window** (laundering within 72 h *after* the alert). It uses information not available at decision time.
- **Typology from the first laundering transaction.** Less stable than the vote, and it depends on how ties in `ts` are ordered.
- **Random alert ids.** Every rebuild would invalidate the freeze.
- **`triggered_at = now()`.** It puts the split on the replay's wall clock.
- **Hashing the whole label tuple, typology included.** The ticket specifies `(alert_id, label, split)`. The typology still shows up in `--check`, through the recomputed labels.

## Consequences

- **The real `splits.json` isn't committed yet.** It needs alerts from a full replay with rules, which should be `rules-v2` (the `fan_out` change 0028 recommends), and about 3 GB of free disk. Until then, `make -C backend check-splits` reports "nothing is frozen yet", and the `rules.yaml` test only compares against the constant.
- Once frozen, any change to rules, the window, the period or the data that moves a label fails `--check` until it's re-frozen on purpose.
- A day-level boundary means the test period's first alerts may cite dev-period transactions, in windows that cross 09-07. That's the realistic case: monitoring always looks back. The *labels* still come only from each alert's own window.
- If HI-Small's later, high-laundering days are ever used, they'd need their own period and split; `ANALYSIS_END` keeps them out today (0023).
