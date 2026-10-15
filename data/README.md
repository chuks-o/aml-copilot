# Data

Raw files live in `data/raw/`. They are git-ignored and must be downloaded once.

Source: [IBM Transactions for Anti Money Laundering (AML)](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml), files `HI-Small_Trans.csv` (~475 MB) and `HI-Small_Patterns.txt` (~320 KB).

## Download with the Kaggle CLI

1. Copy `.env.example` to `.env` and set `KAGGLE_API_TOKEN`.
2. From the repo root:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
set -a; source .env; set +a
for f in HI-Small_Trans.csv HI-Small_Patterns.txt; do
  .venv/bin/kaggle datasets download -d ealtman2019/ibm-transactions-for-anti-money-laundering-aml -f "$f" -p data/raw
done
```

Or download the two files from the dataset page in a browser and place them in `data/raw/`.
