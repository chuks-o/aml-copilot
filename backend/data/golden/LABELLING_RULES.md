# Labelling rules: golden set v1

How to label the 80 alerts in `golden_v1_sample.json`. The rules come from the labeller's answers to the edge-case questions in T17. Follow them even where your instinct differs, because a golden set is only useful if every alert is judged the same way. If a rule seems wrong, raise it, and the change goes into a new decision record and a new golden version, not into quiet exceptions.

## Before you start

- Start the stack on the current code: `make up` (it rebuilds the API).
- Label: `make -C backend golden-label`. Press `q` to stop at any point. The next run continues where you stopped.
- **Don't open `golden_v1_sample.json` or query the database while labelling.** The sample file says which group each alert was drawn from, and the database holds the answers. Either one spoils the judgement you're recording.
- About an hour a day. Commit `golden_v1.jsonl` at the end of each session.

## What you're deciding

Imagine you're an analyst seeing this alert the moment it fired. The screen shows only what existed then: the account's transactions up to the alert, its counterparties over the 72 hours before, and its KYC profile.

- **ESCALATE**: worth a closer investigation as possible money laundering.
- **CLOSE**: explained by ordinary activity; no further action.

## The rules

1. **Money arriving from many senders is enough to ESCALATE**, even if it never moves on in what you can see. An account that collects from many unrelated payers in a short time is treated as a collection point.
2. **A suspicious counterparty is enough to ESCALATE**, even when the alerted account's own behaviour looks ordinary. Being part of a suspicious account's flow is a reason to look.
3. **When the activity fits more than one pattern, name the pattern that covers the whole picture.** Money collected from many accounts and then sent out to many is `GATHER_SCATTER`, not `FAN_IN` plus `FAN_OUT`.
4. **When it's suspicious but no listed pattern fits, choose `OTHER` and describe it** in a few words (80 characters at most), for example "round amounts bounced between two accounts".
5. **A big mismatch with the KYC profile is enough to ESCALATE**, even when nothing else looks odd. For example, an expected monthly volume of 1,000–9,999 and six figures moved in days, or activity that doesn't fit the stated business.
   - The KYC fields are synthetic, marked `(synthetic)`, and about 1 in 10 profiles was deliberately made inconsistent. Judge them as if they were real: the point is how a mismatch should be treated, not whether this one was planted.
6. **If you can't decide, skip it (`s`).** Skipped alerts come back after all the others. Don't force a decision you'd write "unsure" on.
7. **Key transactions:**
   - For an **ESCALATE**, pick the 3 to 8 transactions that best show the pattern.
   - For a **CLOSE**, pick 3 to 8 **of the transactions the rule cited** (marked `*`). If the rule cited fewer than 3 (pass-through alerts cite 2), include all of them and add the nearest other transactions that explain why it's ordinary.
8. **Two minutes is the soft limit.** After two minutes on one alert, the screen reminds you. Decide, or skip and come back to it.

## The typologies

These are the names used in the dataset's patterns file.

| Typology | Shape |
| --- | --- |
| `FAN_IN` | Many accounts pay one account. |
| `FAN_OUT` | One account pays many accounts. |
| `GATHER_SCATTER` | Many pay one, which then pays out to many. |
| `SCATTER_GATHER` | One pays many intermediaries, which all pay one final account. |
| `CYCLE` | Money travels through a chain of accounts and returns to where it started. |
| `BIPARTITE` | One group of accounts pays another group. |
| `STACK` | Layers of bipartite flows: group to group to group. |
| `RANDOM` | Money hops along an irregular path through several accounts. |
| `OTHER` | Suspicious, but none of the above. Describe it. |

A CLOSE has no typology.

## Recording

For each alert the tool asks, in order:
1. the typology (ESCALATE only);
2. the key transaction ids, separated by spaces or commas;
3. a short note: one or two sentences on *why*, in your own words (at most 500 characters).

It then shows a summary to confirm. The time spent is measured automatically, without pauses (`z`).

**To change a label later:** `uv run aml golden-label --revise <alert id>`. The new answer is added as a new line and replaces the old one. Nothing is deleted.

## Screen commands

`n` / `p`: next or previous page of transactions · `g 3`: go to page 3 · `e`: ESCALATE · `c`: CLOSE · `s`: skip for now · `z`: pause the clock · `q`: stop. Pressing Enter on an empty prompt goes back to the screen.
