# Data

| Folder | Contents | In git? |
| --- | --- | --- |
| `raw/` | IBM AML HI-Small files from Kaggle | No (git-ignored, ~475 MB) |
| `typology_cards/` | Short write-ups of each laundering pattern, for the investigator | Yes |
| `golden/` | Hand-checked expected outputs for evaluations | Yes |

## Downloading `raw/`

Source: [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml). Only three HI-Small files are fetched, one at a time. The whole dataset, with its Medium and Large variants, is about 8 GB.

| File | Rows | Used for |
| --- | --- | --- |
| `HI-Small_Trans.csv` | 5,078,345 | transactions |
| `HI-Small_Patterns.txt` | 3,209 | typology of laundering rows (0003) |
| `HI-Small_accounts.csv` | 518,581 | bank and entity per account: the real part of each KYC profile |

1. Copy the repo-root `.env.example` to `.env` and set `KAGGLE_API_TOKEN`. `KAGGLE_USERNAME` + `KAGGLE_KEY`, or `~/.kaggle/`, also work.
2. Run `make download`. It skips files already present, warns under 5 GB free, and prints each file's size and row count.

Or download the three files in a browser and place them in `backend/data/raw/`.

## Loading the database

With the stack up (`make up`), run `make seed`. It loads accounts (with KYC profiles), transactions and `settings` in a single transaction. It's idempotent: run it again and the data, and the fingerprints it prints, are identical. It needs about twice the dataset's size in free disk while it runs, because the old rows are kept until the new load commits. How it works, and why: [decision 0023](../../docs/decisions/0023-seed-and-download.md).

## Replaying instead of seeding

`aml replay` loads the same transactions gradually, as if they were arriving live:

```bash
uv run aml seed --accounts-only     # accounts and settings; transactions left empty
uv run aml replay                   # 2,000 rows/s in (ts, id) order
uv run aml replay --compression 600 --corrupt-rate 0.01   # 10 dataset minutes per second
```

Malformed rows go to `ingest_quarantine` with the reason. Progress is printed every 10 s. A stopped replay resumes where it left off (`--from-start` starts over). `aml replay` streams a time-sorted copy of the file (`data/raw/.replay-cache/`, about 500 MB, built once per source file in about 50 s), so it needs about 350 MB of memory. `aml seed` still loads the whole file (about 2.3 GB), so close memory-hungry apps first on a small machine: swap uses the same disk. How it works, and why: [decision 0026](../../docs/decisions/0026-replayer.md).
