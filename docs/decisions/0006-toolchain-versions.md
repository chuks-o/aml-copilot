# 0006 — Toolchain versions

**Status:** Accepted · **Ticket:** T02 · **Date:** 2026-10-15 · **Supersedes:** 0001 decision 3

| Tool | Choice | Why / rejected |
| --- | --- | --- |
| Python | **3.12** (`backend/.python-version`, `requires-python >=3.12,<3.13`), uv | As specified. T01's 3.14 venv and `requirements.txt` are removed. Notebook dependencies are the uv group `notebooks` (`make -C backend notebooks`), so `aml` itself doesn't pull in Jupyter. _Rejected:_ a separate notebook venv. |
| Node | **Target 22** (`web/.nvmrc`, `engines >=22`, `@types/node@22`, `ES2023`) | CI uses 22. The local machine runs 24.1, which runs Node-22 code. |
| TypeScript | **~6.0** | `latest` is 7.0 (the native Go port); typescript-eslint 8 supports only `<6.1`. _Rejected:_ TS 7 without type-aware linting. |
| ESLint | **9.x** | eslint-config-next's React, a11y and import plugins declare peer `eslint <=9`. npm now marks 9.x as deprecated since 10 is out. _Rejected:_ ESLint 10 with unmet peers. Upgrade when the Next.js plugins support it. |
| pnpm | **9.12.1** (`packageManager`) | What's installed. _Rejected:_ upgrading the global tool now. |
| Test HTTP client | **httpx2** | Starlette 1.8's `TestClient` deprecates `httpx` in favour of `httpx2`. |
| Next.js / React / urql / TanStack Query / graphql | 16.4 / 19.3 / 5.0 / 5.104 / 17.0 | Current stable at scaffold time. |

## Consequences

TypeScript 7 and ESLint 10 are blocked on upstream plugin support; retry periodically.
