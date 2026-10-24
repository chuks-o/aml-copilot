# 0032 — Golden set v1: a blind, stratified sample labelled in the terminal

**Status:** Accepted; decision 6 superseded by [0033](0033-golden-labelling-rules.md) · **Ticket:** T17 · **Date:** 2026-10-24

## Context

The 72 h label (0029) is automatic: it says whether laundering happened near an alert, not what an analyst would decide, or why. Evaluating the investigator agent needs that human judgement: a decision, a typology, the transactions that matter, and a note.

T17 asks for 80 dev alerts, labelled by hand at about an hour a day:
- 40 positives: about 32 across 6 or more listed typologies, and about 8 `UNLISTED`, non-ACH;
- 40 negatives, at least 20 of them hard, including the T01 collector accounts;
- no high-volume accounts, and a fixed seed.

## Decision

1. **The sample** (`aml golden-sample`; `backend/data/golden/golden_v1_sample.json`, seed 17), drawn only from dev, never `is_high_volume`, never `heldout_cycle` (0029: those are never tuned on), and at most one alert per account:

   | Stratum | Alerts | Rule |
   | --- | ---: | --- |
   | `positive_listed` | 32 | spread evenly over the 8 listed typologies; a typology with fewer accounts gives its place to the largest pool |
   | `positive_unlisted_non_ach` | 8 | `UNLISTED`, with no ACH among the window's laundering transactions |
   | `negative_t01` | 4 | one alert per T01 hard-negative account (0004) with dev alerts |
   | `negative_high_score` | 8 | score ≥ 0.9, no laundering on the account at any time |
   | `negative_near_miss` | 8 | negative, but the account has laundering outside the 72 h window; fills the 20 hard negatives |
   | `negative_ordinary` | 20 | score < 0.9, a clean account, spread by rule in proportion to dev volume |

   - Listed typologies drawn: GATHER_SCATTER 5, SCATTER_GATHER 5, BIPARTITE, FAN_IN, FAN_OUT, RANDOM and STACK 4 each, CYCLE 2. CYCLE's 3 dev alerts (outside `heldout_cycle`) sit on 2 accounts.
   - **`4726:808FAF7C0`, the third T01 collector, has alerts only in test**, so it isn't sampled. The sample file says so (`t01_without_dev_alerts`).
   - Candidates are sorted by id before the seeded draw, so the database's row order can't change the sample. The labelling order is shuffled, so the strata come mixed.
   - The draw first runs `aml label --check` and records the frozen `splits.json` hash, so it only ever samples from the frozen labels. `aml golden-sample --check` (`make -C backend golden-sample`) redraws it and fails on any difference. Writing it twice is refused.
   - **The sample file stores each alert's stratum,** which reveals ground truth. The tool never reads it, and LABELLING_RULES.md says not to open the file while labelling. Keeping it makes the composition checkable without a database.
   - **Equal shares, not proportional ones,** for the listed typologies. Proportional shares would give BIPARTITE and CYCLE one alert each, too few to say anything per typology.
2. **Blind by construction.** The screen (`aml.evals.label_cli`) reads only through the Cases API with the generated client. The API never exposes `is_laundering`, `pattern`, `label`, `typology_label` or `split` (0014), so no stratum or answer can reach the screen, whatever the screen code does. Only sampling, which needs the labels, uses the database connection the CLI injects (as `aml label` does).
3. **No look-ahead.** The screen shows what an analyst had when the alert fired:
   - the account's transactions up to `window_end`;
   - counterparties for the 72 h up to it;
   - the activity count for those transactions only.

   The profile's whole-history counts, which include later activity, aren't shown.
4. **Contract 0.4.0 (additive):**
   - `Alert.triggered_at`, `window_start` and `window_end`;
   - `Account.kyc` (`KycProfile`: the synthetic fields and the `synthetic` list, never `kyc_seed`);
   - **`GET /accounts/{id}` reads the database** (it was a placeholder), with 404 for an unknown account.

   The investigator agent will need the same view.
5. **What you see per alert:** the rule, its reason, score and cited transactions; the KYC profile, with synthetic fields marked; the counterparty summary; and transactions 20 to a page, oldest first, with cited rows starred, opening on the page of the first cited one.
6. **What gets recorded:** `ESCALATE` or `CLOSE`; a typology (one of the 8 or `UNLISTED` for an escalation, none for a close); 3 to 8 key transaction ids, each visible on this alert's screen; a note under 500 characters; seconds on screen, minus pauses (`z`), up to the moment of saving; the labeller; and the wall-clock time.
   - **These rules are provisional until LABELLING_RULES.md is written** from the labeller's answers. If they change, this record is superseded.
7. **Append-only and resumable.**
   - Each label is one line in `golden_v1.jsonl`, written, flushed and `fsync`ed before the screen moves on. A crash loses at most the alert on screen, and a torn final line is ignored when the file is read.
   - The next run starts at the first unlabelled alert. Skipped alerts (`s`) come back after the rest.
   - `--revise <alert>` appends a new line marked `revises`, and the last line wins. Nothing is ever rewritten.
8. **Rich, not Textual.** Rich is already installed (through Typer) and covers panels, tables and prompts. A session runs on an injected `read` function and console, so the tests drive it with scripted answers and a fake clock. Textual would be a new dependency and an event loop for a form.

## Alternatives

- **A random sample of dev alerts.** At a 3.2% positive rate, it gives about 3 positives in 80.
- **Reading display data straight from the database.** Fewer files, but blindness would then depend on every query avoiding the ground-truth columns.
- **Showing the full history.** It shows laundering after the alert, which is look-ahead.
- **Several alerts per account.** One busy collector could fill a stratum.
- **Rewriting the JSONL on each save.** A crash mid-rewrite can lose every label.
- **Including the test-only T01 collector.** It would put a test alert in a dev golden set.

## Consequences

- Labelling needs the stack's API on the current code (`make up` rebuilds it) and the replayed database. The first run in a fresh clone also needs a replay (0031).
- `golden_v1.jsonl` is committed by the labeller, in batches; the sample file is fixed.
- A golden set made against other frozen labels needs a new version (`golden_v2`) and a new seed record, never edits to v1.
