# 0001 — Data location, credentials, environment, loading

**Status:** Accepted · **Ticket:** T01 · **Date:** 2026-10-15

## Context
The raw data is ~475 MB from Kaggle and needs an API token to download. The project needs a reproducible Python setup and a notebook that others can read without rerunning.

## Decisions
1. **Raw data in `data/raw/`, git-ignored.** Downloaded per `data/README.md`.
   - *Rejected:* committing the data (too big; it's someone else's dataset). Git LFS (unnecessary while the source is a stable public download).
2. **Kaggle token in a git-ignored `.env`** (`KAGGLE_API_TOKEN`), loaded into the shell with `set -a; source .env` before running the CLI. `.env.example` documents the variable.
   - *Rejected:* `~/.kaggle/access_token`. It's safer by default because it lives outside every repo, but the user preferred per-project configuration. The `.env` is `chmod 600` and ignored before the first commit.
3. **`python -m venv .venv` + pinned `requirements.txt`.**
   - *Rejected:* uv (faster, but one more tool to install); conda (heavy); Poetry (overkill before there is a package).
4. **Load all 5.08M rows with explicit dtypes.** IDs are kept as strings (bank codes have leading zeros), currencies and formats are categoricals, and timestamps are parsed. This takes about 5 s and about 700 MB of RAM.
   - *Rejected:* sampling (a 0.1% positive rate makes samples noisy, and the joins need every row). Parquet caching (that belongs to an ingestion ticket, not exploration).
5. **Notebooks are committed with outputs**, so they read as reports on GitHub.
   - *Rejected:* stripping outputs (cleaner diffs, but unreadable without rerunning against 475 MB of data).

## Consequences
- Anyone reproducing the work needs a Kaggle account.
- Notebook diffs will be noisy. Revisit if notebooks start changing often.
