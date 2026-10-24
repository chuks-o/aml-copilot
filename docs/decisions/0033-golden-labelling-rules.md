# 0033 — Golden-set labelling rules, from the labeller's answers

**Status:** Accepted · **Ticket:** T17 · **Date:** 2026-10-24 · **Supersedes:** [0032](0032-golden-set.md) decision 6 (what gets recorded)

## Context

0032 recorded provisional rules: an ESCALATE takes one of the 8 typologies or `UNLISTED`, and any visible transactions can be key. T17 asks for `LABELLING_RULES.md` from the labeller's answers to edge-case questions. The answers were:
1. collection without onward movement: ESCALATE;
2. a suspicious counterparty: ESCALATE;
3. a combined pattern: the name for the whole picture;
4. nothing fits: free text, not `UNLISTED`;
5. a KYC mismatch alone: ESCALATE;
6. undecided: skip;
7. key transactions for a CLOSE: the cited ones;
8. a reminder after 2 minutes.

## Decision

1. **`backend/data/golden/LABELLING_RULES.md`** states all eight rules, with the typology shapes and how to use the tool. Rules 1, 2, 3, 5 and 6 are judgement rules; the tool can't check them.
2. **`OTHER` replaces `UNLISTED` for the labeller.** An ESCALATE takes one of the 8 listed typologies or `OTHER`. `OTHER` requires a description of up to 80 characters, stored in a new field, `typology_other`; other typologies forbid one. When golden labels are compared with the automatic labels, `OTHER` corresponds to `UNLISTED` (0029).
3. **A CLOSE's key transactions come from the rule's cited ones.** When the rule cited fewer than 3 (pass-through cites 2), all of them must be included, topped up with other visible transactions to reach 3. An ESCALATE may cite any visible transactions. The answer to question 7 didn't cover rules citing fewer than 3, so this is the minimal extension that keeps the 3-to-8 count.
4. **After 120 seconds on one alert, the screen shows a reminder** on every redraw. It doesn't stop the labeller.
5. **Prompts are escaped before Rich renders them.** Rich read `[Y/n]` and bracketed note text as markup and dropped them.

## Alternatives

- **Keeping `UNLISTED`.** Rejected by the labeller (question 4): free text keeps the description of what was seen.
- **Free text in `typology` itself.** It mixes the 8 names with arbitrary strings in one field, which every later analysis would have to untangle.
- **Allowing any transaction for a CLOSE.** Rejected by the labeller (question 7).
- **A hard time limit.** It would force rushed decisions; question 8 asked for a reminder.

## Consequences

- Labels from before this change don't exist (none had been recorded), so no migration is needed.
- Comparing golden typologies with automatic ones maps `OTHER` to `UNLISTED`, and keeps `typology_other` as context for error analysis.
