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
