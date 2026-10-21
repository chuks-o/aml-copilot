# 0027 — Replay streams a sorted copy instead of loading the file

**Status:** Accepted · **Ticket:** T14 follow-up · **Date:** 2026-10-21 · **Supersedes:** [0026](0026-replayer.md) decisions 3 and 8

## Context

0026 sorted all 5,078,345 rows in memory: a peak resident size of **2.33 GB**. On the development Mac, with Docker's VM holding 4 GB, every full-file load pushed about 1.1 GB into macOS swap. Swap lives on the same disk, so free space fell by the same amount. That caused the repeated low-disk incidents since T11, one of which took Docker Desktop down.

The replayer only needs the file *in order*. Its writes were already batched, so holding everything in memory was a property of how it sorted, not something replay needs.

## Decision

1. **External sort, once per source file.**
   - `sorted_copy()` reads `HI-Small_Trans.csv` in chunks of 250,000 rows. Each chunk gets its `id` (file position), is sorted by `(ts text, id)`, and is written as a run file.
   - `heapq.merge` then merges the runs into `data/raw/.replay-cache/transactions_sorted.csv`, written to a `.partial` file and renamed when complete, so an interrupted build never leaves a half file. The runs are deleted afterwards.
   - The `YYYY/MM/DD HH:MM` timestamp text sorts correctly as text.
   - The copy is reused until the source's SHA-256, recorded in `transactions_sorted.json`, changes.
   - **Rejected:** shelling out to `sort`. Apple's and GNU's differ in flags and locale behaviour, and the Compose `replayer` service runs GNU.
2. **Streaming.**
   - `stream_ordered()` reads the sorted copy 50,000 rows at a time, and adds each chunk's pattern labels from the small patterns file (3,209 rows; a left merge on the 0003 key, with `UNLISTED` for other laundering rows).
   - The replay loop keeps a buffer of pending rows, refilled whenever fewer than a batch remain.
   - Due times use the running row count and the replay's first timestamp, so pacing is continuous across chunks.
   - Resuming drops rows at or before the watermark chunk by chunk, and `--limit` truncates the stream.
3. **Corruption depends only on `(seed, id)`.** A splitmix64 hash of the id gives a uniform number per row: below `--corrupt-rate` means damaged, and a second hash picks the kind. That's deterministic under `--limit`, resuming and chunking, which is what 0026 decision 8 needed.
   - 0026's "round-robin in file order" counted over the whole file, which a stream can't do, so the kinds are now **approximately even**, not exactly: the 20,000-row test gets each kind at more than a fifth of the corrupted rows.

## Evidence

The full file, built and streamed without a database (`/usr/bin/time -l`):

| | 0026 (in-memory sort) | 0027 (sorted copy, streamed) |
| --- | --- | --- |
| Peak resident memory | 2,328 MB | **353 MB** |
| macOS swap growth | +1.1 GB | +136 MB |
| Disk | — | 496 MB sorted copy, once (about 1 GB at peak while the runs exist) |
| Time | load + sort ≈ 22 s per replay | build 47.7 s once; stream 15.5 s per replay |

All 5,078,345 streamed rows were in `(ts, id)` order.

Unit tests check:
- 13 tiny runs (`RUN_ROWS` = 7) merge to exactly the in-memory order;
- the copy is reused, rebuilt when the source changes, and leaves no run files behind;
- corruption is the same for the whole stream and for a prefix.

The four replayer integration tests (0026) pass unchanged, except for the evenness assertion.

## Alternatives

- **A lighter in-memory load** (fewer columns, pyarrow strings). Perhaps half the memory, but still proportional to the file: a mitigation, not a guarantee.
- **Sorting in Postgres** (bulk-load raw rows into a staging table, read back `ORDER BY`). Constant memory too, but about 1 GB more inside Docker's disk image, the space that ran out before.
- **Leaving it, and asking for more memory.** That fixes the machine, not the design.

## Consequences

- The first replay after a new download spends about 50 s building the copy, and needs about 1 GB free during the build (500 MB afterwards).
- `aml seed` still loads the whole file (0023). It needs whole-dataset totals (activity counts, the high-volume cut, `ANALYSIS_END`), so streaming it means a first pass for those, which is a separate change.
- `data/raw/.replay-cache/` lives under the git-ignored `data/raw/`.
