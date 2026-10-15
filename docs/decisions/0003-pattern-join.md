# 0003 — Join pattern names onto transactions by exact full row

**Status:** Accepted · **Ticket:** T01 · **Date:** 2026-10-15

## Context
`HI-Small_Patterns.txt` groups laundering transactions into attempts (`BEGIN LAUNDERING ATTEMPT - <PATTERN>[: detail]` … `END …`). Its rows have the same 11 columns as the CSV but **no transaction ID**, so the only link to the CSV is the row content. Three of the eight pattern headers (BIPARTITE, SCATTER-GATHER, STACK) have no `: detail` suffix.

## Decisions
1. **Join key = all 10 non-label columns.** These are timestamp, both bank/account pairs, both amounts and currencies, and payment format.
2. **Both files are parsed by the same function** (`read_transactions`). Amounts parsed from the same text therefore compare exactly equal as floats.
3. **Each block gets an `attempt_id`** (its order in the file), so a transaction can be traced back to its scheme.
4. **Laundering rows with no match are labelled `UNLISTED`**, not dropped.
5. **The join is checked by assertions:** pattern keys are unique (`validate="many_to_one"`), every pattern row matches the CSV, and the row count is preserved.

## Evidence
- All 3,209 pattern rows match exactly. No transaction belongs to more than one attempt.
- 1,968 of the 5,177 laundering rows (38%) are not in the patterns file.
- Every patterned transaction is ACH. The unlisted ones are 65% ACH, with the rest cheque, credit card, cash and Bitcoin.

## Alternatives rejected
- **Partial key** (timestamp, sender, receiver, amount): no real gain, and it risks false matches between near-identical payments.
- **Treating the patterns file as the full set of positives:** that would discard 38% of the true laundering and every non-ACH case.
- **Inferring typologies from graph shape:** the header is the ground truth. Inference is a possible later feature, not a labelling method.

## Consequences
Pattern-based features and explanations cover only 62% of positives, so the system must handle laundering that has no typology. If the source files change, the assertions in the notebook's Checks section fail loudly.
