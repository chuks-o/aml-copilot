# 0023 — `aml download` and `aml seed`: loading HI-Small with synthetic KYC

**Status:** Accepted · **Ticket:** T11 · **Date:** 2026-10-18 · **Supersedes:** [0014](0014-cases-api-contract.md) decision 10 · **Amends:** [0012](0012-working-rules.md) decision 2

## Context

The schema from [0022](0022-schema-v1.md) is empty. T11 adds two commands:
- `aml download` fetches the dataset files from Kaggle;
- `aml seed` loads them: accounts with KYC profiles, transactions with stable ids and pattern labels, the high-volume flag, and `ANALYSIS_END`.

Measured on the real files before deciding:

| Fact | Value |
| --- | --- |
| Accounts in transactions / in `HI-Small_accounts.csv` | 515,088 / 518,581 |
| Largest jump between neighbouring per-account activity counts (sent + received) | 394 → 6,468 (16×); 15 accounts above it, all at bank `70` (`070` in the file) |
| Median daily clean volume; last day ≥ 10% of it | 207,007; 2022-09-10 (207,883). From 11 Sept clean volume is 164 and falling, while laundering continues (232, 170, …) |
| Laundering rows not in the patterns file, by format | 1,968: ACH 1,275, cheque 324, credit card 206, cash 108, Bitcoin 55. **65% ACH**, as 0003 found. The ticket's "every one non-ACH" is wrong, and nothing depends on it. |

## Decision

1. **The KYC profile is real fields plus labelled synthetic fields.** This supersedes 0014 decision 10's "only what the data has".
   - **Real:** `bank_name`, `entity_id` and `entity_name` from `HI-Small_accounts.csv`, plus `entity_type` (the `accounts.entity_type` column) parsed from the entity name.
   - **Synthetic (Faker):** `business_type`, `country`, `expected_monthly_volume_band`, `onboarded_at`.
   - Every profile carries `"synthetic": [those four]` and `"kyc_seed": 42`, so the investigator and the UI can present them as synthetic, not as fact.
   - `aml download` therefore fetches three files, not the ticket's two. The accounts file is 32.5 MB.
2. **Profiles are deterministic per account.**
   - Each account's Faker generator is seeded with `sha256("42:<account id>")`, using one Faker instance re-seeded per account, because constructing one per account is slow.
   - So a profile depends only on its account id and seed 42: not on processing order, the number of accounts, or the process. Python's `hash()` is randomised per process; `sha256` isn't.
   - Faker is pinned (`==40.40.0`), because providers can change output between releases.
3. **The volume band is loosely consistent for 90% and deliberately inconsistent for 10%.**
   - Bands are expected monthly transaction counts: `<10`, `10-99`, `100-999`, `1000-9999`, `10000+`. The actual rate is the account's activity scaled to 30 days over the analysis window.
   - A consistent profile gets its actual band 3 times in 5, otherwise a neighbouring one.
   - The **inconsistent 10% are chosen by `sha256(…id) % 100 < 10`**, the id alone, never the label. Choosing them by label would leak the label into any feature built on KYC.
   - Measured: **10.62%** of accounts involved in laundering and **10.03%** of the rest are inconsistent. `onboarded_at` is always 30–3,650 days before the account's first transaction.
4. **Columns are mapped by name.** The header must equal the expected 11 names exactly. Each `Account` column is named after the bank column before it, `from_account_number` and `to_account_number`, so there's never an `Account.1`. Every column is read as text, so bank codes keep their zeros until they're deliberately normalised (0015) and amounts keep their exact digits.
5. **Spellings map to ours**, and an unknown value stops the seed: 15 currency names to codes (`Bitcoin` → `BTC`), 7 payment formats to the enum, 8 pattern names to typologies (`FAN-IN` → `FAN_IN`), 6 entity kinds. The static file must be fully valid; `ingest_quarantine` is for live replay.
6. **Transaction id = the row's 1-based position in the file.** The SHA-256 of each file goes into `settings.DATASET`, so a changed source file is detectable. `setval('transactions_id_seq', max(id))` runs after the load.
7. **The pattern join is on the 10 non-label columns, compared as raw text** (0003's key, without float parsing). Every pattern row must match exactly one transaction, a patterned row must be laundering, and other laundering rows get `UNLISTED`.
8. **High-volume cut:** the largest ratio between neighbouring distinct activity counts, ignoring counts under 10 (where any step is a big ratio). It's computed, not hard-coded, and stored in `settings.HIGH_VOLUME_CUT`.
9. **`ANALYSIS_END`** is the end (exclusive UTC midnight) of the last day whose clean count is ≥ 10% of the median daily clean count: **`2022-09-11T00:00:00Z`**, with **1,108 rows after it** (655 laundering, 453 clean). It's stored in `settings`.
10. **The reload is one transaction:**
    1. refuse if `alerts` has rows (a reload would destroy workflow data);
    2. `TRUNCATE transactions`;
    3. `DELETE FROM accounts`;
    4. drop transactions' secondary indexes and foreign keys;
    5. `COPY` accounts, then transactions in 50,000-row batches (CSV format);
    6. re-create the indexes and foreign keys;
    7. check the indexes;
    8. write `settings`;
    9. commit.

    Details on the steps:
    - **`DELETE`, not `TRUNCATE`, for accounts:** Postgres refuses to truncate a table referenced by a foreign key even when the referencing table (`alerts`) is empty, and `CASCADE` would hit `case_events`' append-only trigger (0022).
    - **The index and FK definitions are read from the catalog** (`pg_get_indexdef`, `pg_get_constraintdef`), not repeated in code, so they can't drift from the migration.
    - **`pg_get_indexdef` returns `ON ONLY` for a partitioned index.** Re-running that verbatim creates an *invalid* parent index with no partition indexes, which is what happened on the first deferred run: `indexes: 0.0 s`, partition indexes missing, parent `indisvalid = false`. The seed rewrites `ON ONLY` to `ON`, then checks that every index is valid and present on every partition, and fails the load otherwise. `tests/integration/test_seed.py` checks the same.
    - **`accounts.created_at` is set by the seed** to the dataset's first instant (2022-09-01T00:00Z), not left to its `now()` default. Otherwise every reload changes it, and the seed isn't idempotent. The seed-twice integration test caught this.
11. **Why `COPY`, measured.** An `INSERT` is a statement per row: parse, plan, execute and acknowledge, usually with a round trip each. `COPY` streams rows over one statement, and the server parses them in a tight loop. Building indexes and checking foreign keys once at the end, instead of per row, is the other half of the speed.

    | Run | FKs and indexes during the load | Wall clock |
    | --- | --- | --- |
    | 1 | kept (checked and maintained per row) | 1,008 s |
    | 2 | deferred (rebuild then broken by `ON ONLY`) | 149 s (copy 45.1 s) |
    | 3 | deferred, fixed | 155 s (copy 42.6 s, indexes 18.1 s, FKs 4.8 s) |
    | 4 | deferred, fixed | 150 s (copy 38.9 s, indexes 18.4 s, FKs 5.4 s) |

    Runs 3 and 4 finish with all three transactions indexes valid on both partitions. Run 1's own phase timings didn't add up to its wall clock; runs 2–4 time each phase by wall clock, and those sums match the totals.

12. **Idempotency is shown by fingerprints:** per table, the row count plus `md5` over the md5 of every row in key order. They're printed after every run. Runs 3 and 4 on the real data printed the same three:

    | Table | Rows | md5 |
    | --- | --- | --- |
    | accounts | 515,088 | `e5839e9b81d0263ea33e39c01461040a` |
    | transactions | 5,078,345 | `b251bf7cc71671c3c6baddb519f3145d` |
    | settings | 4 | `a59da837bc9835946fd92262fffe8a55` |
 `tests/integration/test_seed.py` also compares full table contents across two seeds of a fixture dataset.
13. **`aml.data` may import `aml.db`**, amending 0012 decision 2 (which foresaw "a later record granting an exception"). Seeding is an offline admin job like `aml migrate`, and `COPY` can't go through REST. The import contract `db-belongs-to-api` and its architecture test list `aml.data` as allowed. `aml.db.connect()` gives a raw psycopg connection, because SQLAlchemy doesn't wrap `COPY`.
14. **Kaggle:**
    - `aml download` fetches only `HI-Small_Trans.csv`, `HI-Small_Patterns.txt` and `HI-Small_accounts.csv`, one call per file, into `backend/data/raw/`.
    - It unzips if Kaggle sends a `.zip`, skips files already present, warns under 5 GB free, and prints size and rows.
    - Credentials come from the kaggle library's own sources. `.env` values (`KAGGLE_API_TOKEN`, or `KAGGLE_USERNAME` + `KAGGLE_KEY`) are read through `Settings` and passed to the library without overriding real environment variables.
    - `kaggle` is imported inside the function, because `import kaggle` authenticates as a side effect.
    - The retry helper CLAUDE.md requires doesn't exist yet. The Kaggle client does its own HTTP, and no ad-hoc retries were added.
15. **Dependencies:**
    - runtime: pandas 3.0.6, Faker 40.40.0 (pinned exactly), kaggle 2.2.4;
    - dev: pandas-stubs 3.0.5.260914;
    - a mypy override for `kaggle`, which has no stubs.

    All are at least two weeks old.

## Alternatives

- **Faker for everything, as the ticket says** (two files, Faker `entity_type`). It discards real entity data and makes the REST `Account`'s `bank_name` and `entity_name` fake.
- **No synthetic fields** (0014 decision 10 unchanged). The ticket's signals need fields the dataset doesn't have.
- **Choosing the inconsistent 10% among laundering accounts.** Label leakage.
- **A global `Faker.seed(42)`.** Every profile then depends on processing order.
- **A bulk-upload REST endpoint instead of the `aml.data` exception.** 5M rows through JSON defeats `COPY`.
- **Upserts (`INSERT … ON CONFLICT`).** Slower, and rows removed from the source would linger.
- **Keeping FKs and indexes during the load.** Measured at 1,008 s.
- **`ALTER TABLE … ADD FOREIGN KEY … NOT VALID` + `VALIDATE`.** Postgres 16 doesn't allow it on a partitioned table. Checked on our 16.15: `cannot add NOT VALID foreign key on partitioned table`. A plain `ADD` validates with one join, which took 6.4 s here.
- **Hard-coding the index DDL in the seed.** It drifts from the migration.
- **`TRUNCATE … CASCADE`.** It reaches `case_events`, which refuses truncation (0022).
- **Unknown values to `ingest_quarantine`.** For live data, not for a file that must be valid.
- **Python `hash()` for seeds.** Randomised per process.

## Consequences

- **A reload needs about twice the dataset's size in free disk.** The old files are kept until commit. That's the cost of all-or-nothing; on this machine it means about 2 GB free.
- **`make seed` refuses once alerts exist.** Reseeding then means `make down && make up`.
- **The investigator and UI must show `synthetic` fields as synthetic.** The profile says which.
- **The 10% inconsistency is noise with respect to the label, by design.** Any feature built on it should score near chance. If it doesn't, something leaks.
- **Ingest of live (replayed) transactions goes through the API and `ingest_quarantine`, not this command.**
