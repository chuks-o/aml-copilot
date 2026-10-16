# Data

| Folder | Contents | In git? |
| --- | --- | --- |
| `raw/` | IBM AML HI-Small files from Kaggle | No (git-ignored, ~475 MB) |
| `typology_cards/` | Short write-ups of each laundering pattern, for the investigator | Yes |
| `golden/` | Hand-checked expected outputs for evaluations | Yes |

## Downloading `raw/`

Source: [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), files `HI-Small_Trans.csv`, `HI-Small_Patterns.txt` and `HI-Small_accounts.csv` (bank and entity per account; the source of the API's account profile).

1. Copy the repo-root `.env.example` to `.env` and set `KAGGLE_API_TOKEN`.
2. From `backend/`:

```bash
set -a; source ../.env; set +a
for f in HI-Small_Trans.csv HI-Small_Patterns.txt HI-Small_accounts.csv; do
  uv run --group notebooks kaggle datasets download \
    -d ealtman2019/ibm-transactions-for-anti-money-laundering-aml -f "$f" -p data/raw
done
```

Or download the three files in a browser and place them in `backend/data/raw/`.
