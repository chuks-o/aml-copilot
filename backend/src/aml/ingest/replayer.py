"""``aml replay``: stream HI-Small into Postgres as if it were arriving live.

Rows go in ``(ts, id)`` order, streamed from a sorted copy of the file (never the whole file in
memory, 0027). A row is due when both the rate cap (``rate`` rows/s) and the
time compression (``compression`` dataset seconds per wall second) allow it; either can be 0
for "off". Due rows are written in batches of up to ``batch_size``, flushed early once the
oldest has waited ``flush_after`` seconds. Each batch is one transaction:

1. Format checks in Python (``aml.data.dataset``'s mappings). Failures go to quarantine.
2. COPY the rest into a session TEMP staging table.
3. One statement moves rows whose accounts exist into ``transactions``
   (``ON CONFLICT DO NOTHING``: already present counts as a duplicate) and quarantines the
   rest with "unknown account".
4. The watermark ``settings.REPLAY_POSITION`` is set to the batch's last ``(ts, id)``, so a
   restart resumes exactly after it.

Rationale: docs/decisions/0026-replayer.md.
"""

import csv
import heapq
import io
import json
import statistics
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg

from aml import db
from aml.common import get_logger
from aml.data import dataset

log = get_logger(__name__)

STAGING = "replay_staging"
POSITION_KEY = "REPLAY_POSITION"
# Corruption kinds, applied round-robin to the chosen rows (by file position).
CORRUPTIONS = ("currency", "amount", "timestamp")
BAD_CURRENCY = "Dogecoin"
BAD_TIMESTAMP = "2022/13/45 25:99"
COLUMNS = (
    "id",
    "ts",
    "from_account",
    "to_account",
    "amount_paid",
    "currency_paid",
    "amount_received",
    "currency_received",
    "payment_format",
    "is_laundering",
    "pattern",
)


@dataclass(frozen=True)
class ReplayConfig:
    rate: float = 2_000.0  # rows per second; 0 = no cap
    compression: float = 0.0  # dataset seconds per wall second; 0 = off
    corrupt_rate: float = 0.0
    seed: int = 42
    limit: int | None = None  # replay at most this many rows (after resuming)
    batch_size: int = 5_000
    flush_after: float = 1.0  # seconds a due row may wait for its batch to fill
    report_every: float = 10.0
    from_start: bool = False  # ignore the stored watermark


@dataclass
class ReplayReport:
    committed: int = 0
    quarantined: int = 0
    duplicates: int = 0
    batches: int = 0
    seconds: float = 0.0
    corrupted_ids: list[int] = field(default_factory=list)
    position: dict[str, Any] | None = None


# ------------------------------------------------------------------------- loading
#
# Never the whole file in memory (0027): an external sort writes a time-ordered copy once
# (sorted runs of RUN_ROWS, merged with heapq), then each replay streams that copy in chunks.

CACHE_DIR = ".replay-cache"
RUN_ROWS = 250_000  # rows sorted in memory at a time while building the cache
READ_ROWS = 50_000  # rows read from the cache at a time while replaying
_KEY = ("ts_raw", "id")


def sorted_copy(raw_dir: Path, *, echo: Callable[[str], None] = print) -> Path:
    """``(ts, id)``-ordered copy of the transactions file, with ``id`` (file position) added.

    Built once, then reused until the source file's SHA-256 changes. Memory: one run.
    """
    source = raw_dir / dataset.TRANSACTIONS_FILE
    cache = raw_dir / CACHE_DIR
    out, meta = cache / "transactions_sorted.csv", cache / "transactions_sorted.json"
    digest = dataset.sha256(source)
    if out.is_file() and meta.is_file() and json.loads(meta.read_text()).get("sha256") == digest:
        return out
    echo(f"sorting {source.name} by (ts, id) into {out} (once per source file)")
    cache.mkdir(parents=True, exist_ok=True)
    names = dataset.transaction_columns(source)
    columns = ["id", *names]
    runs: list[Path] = []
    offset = 0
    for chunk in dataset.read_transactions_chunks(source, RUN_ROWS):
        chunk.insert(0, "id", np.arange(offset + 1, offset + len(chunk) + 1))
        offset += len(chunk)
        # "YYYY/MM/DD HH:MM" sorts correctly as text; id breaks ties.
        run = cache / f"run_{len(runs):04d}.csv"
        chunk.sort_values(list(_KEY), kind="stable").to_csv(run, header=False, index=False)
        runs.append(run)
    handles = [run.open(newline="") for run in runs]
    try:
        readers = [csv.reader(h) for h in handles]
        ts_at, id_at = columns.index("ts_raw"), columns.index("id")
        merged = heapq.merge(*readers, key=lambda row: (row[ts_at], int(row[id_at])))
        partial = out.with_suffix(".partial")
        with partial.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(merged)
        partial.replace(out)  # never leave a half-written cache behind
    finally:
        for handle in handles:
            handle.close()
        for run in runs:
            run.unlink()
    meta.write_text(json.dumps({"sha256": digest, "rows": offset}))
    return out


def stream_ordered(
    raw_dir: Path, *, echo: Callable[[str], None] = print, rows: int = READ_ROWS
) -> Iterator[pd.DataFrame]:
    """Chunks of rows in ``(ts, id)`` order, as raw text plus ``id``, ``pattern``, ``sort_ts``."""
    patterns = dataset.read_patterns(raw_dir / dataset.PATTERNS_FILE)
    keys = list(dataset.JOIN_KEY)
    lookup = patterns[[*keys, "pattern"]]
    for chunk in pd.read_csv(
        sorted_copy(raw_dir, echo=echo), dtype=str, keep_default_na=False, chunksize=rows
    ):
        chunk["id"] = chunk["id"].astype("int64")
        labelled = chunk.merge(lookup, on=keys, how="left").set_axis(chunk.index)
        laundering = chunk["is_laundering_raw"] == "1"
        pattern = labelled["pattern"].where(labelled["pattern"].notna(), None)
        chunk["pattern"] = pattern.where(~(laundering & pattern.isna()), dataset.UNLISTED)
        chunk["sort_ts"] = pd.to_datetime(chunk["ts_raw"], format="%Y/%m/%d %H:%M", utc=True)
        yield chunk


def load_ordered(raw_dir: Path) -> pd.DataFrame:
    """All rows in order, in memory: for small files (tests). Replays use ``stream_ordered``."""
    return pd.concat(list(stream_ordered(raw_dir, echo=lambda _: None)), ignore_index=True)


def _unit(ids: "np.ndarray[Any, Any]", seed: int, salt: int) -> "np.ndarray[Any, Any]":
    """A uniform number in [0, 1) per id, from (seed, salt, id) alone (splitmix64)."""
    x = ids.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15)
    x ^= np.uint64((seed * 1_000_003 + salt) & 0xFFFFFFFFFFFFFFFF)
    for shift, multiplier in ((30, 0xBF58476D1CE4E5B9), (27, 0x94D049BB133111EB)):
        x = (x ^ (x >> np.uint64(shift))) * np.uint64(multiplier)
    x ^= x >> np.uint64(31)
    return np.asarray((x >> np.uint64(11)).astype(np.float64) / float(1 << 53))


def corrupt(rows: pd.DataFrame, rate: float, seed: int) -> list[int]:
    """Damage about ``rate`` of the rows in place; returns their ids.

    Whether a row is damaged, and how, depends only on (seed, its id), so --limit, resuming
    and chunking never change it.
    """
    if rate <= 0 or rows.empty:
        return []
    ids = rows["id"].to_numpy()
    positions = np.flatnonzero(_unit(ids, seed, 0) < rate)
    kinds = (_unit(ids, seed, 1) * len(CORRUPTIONS)).astype(int)
    for position in positions:
        index, kind = rows.index[int(position)], CORRUPTIONS[kinds[position]]
        if kind == "currency":
            rows.at[index, "currency_paid_name"] = BAD_CURRENCY
        elif kind == "amount":
            rows.at[index, "amount_paid"] = "-" + str(rows.at[index, "amount_paid"])
        else:
            rows.at[index, "ts_raw"] = BAD_TIMESTAMP
    return sorted(int(i) for i in ids[positions])


# ---------------------------------------------------------------------- validation


def _first_error(
    errors: "pd.Series[Any]", bad: "pd.Series[bool]", message: "pd.Series[str] | str"
) -> "pd.Series[Any]":
    """Keep each row's first error; record ``message`` where ``bad`` and none yet."""
    return errors.where(errors.notna() | ~bad, message)


def validate(batch: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(rows ready for COPY, rows to quarantine with their ``error``). Format checks only;
    unknown accounts are caught by the move statement."""
    errors: pd.Series[Any] = pd.Series(None, index=batch.index, dtype=object)
    ts = pd.to_datetime(batch["ts_raw"], format="%Y/%m/%d %H:%M", errors="coerce", utc=True)
    errors = _first_error(errors, ts.isna(), "unparsable timestamp '" + batch["ts_raw"] + "'")
    for column, label in (("amount_paid", "Amount Paid"), ("amount_received", "Amount Received")):
        text = batch[column]
        negative = text.str.startswith("-")
        errors = _first_error(errors, negative, "negative amount '" + text + f"' in {label}")
        malformed = ~negative & ~text.str.fullmatch(dataset.AMOUNT)
        errors = _first_error(errors, malformed, "not a decimal amount '" + text + f"' in {label}")
    codes = {}
    for column, label in (
        ("currency_paid_name", "Payment Currency"),
        ("currency_received_name", "Receiving Currency"),
    ):
        codes[column] = batch[column].map(dataset.CURRENCIES)
        errors = _first_error(
            errors, codes[column].isna(), "unknown currency '" + batch[column] + f"' in {label}"
        )
    formats = batch["payment_format_name"].map(dataset.PAYMENT_FORMATS)
    errors = _first_error(
        errors, formats.isna(), "unknown payment format '" + batch["payment_format_name"] + "'"
    )
    labels = batch["is_laundering_raw"]
    errors = _first_error(errors, ~labels.isin(["0", "1"]), "Is Laundering must be 0 or 1")

    ok = errors.isna()
    good = batch[ok]
    valid = pd.DataFrame(
        {
            "id": good["id"],
            "ts": ts[ok].astype(str),
            "from_account": dataset.normalise_bank(good["from_bank"])
            + ":"
            + good["from_account_number"],
            "to_account": dataset.normalise_bank(good["to_bank"]) + ":" + good["to_account_number"],
            "amount_paid": good["amount_paid"],
            "currency_paid": codes["currency_paid_name"][ok],
            "amount_received": good["amount_received"],
            "currency_received": codes["currency_received_name"][ok],
            "payment_format": formats[ok],
            "is_laundering": labels[ok] == "1",
            "pattern": good["pattern"],
            "raw": [json.dumps(_raw(row)) for row in good.to_dict("records")],
        }
    )
    rejected = batch[~ok].assign(error=errors[~ok])
    return valid, rejected


def _raw(row: dict[Any, Any]) -> dict[str, Any]:
    """The row as received: the CSV fields (by our column names) and its id."""
    fields = {k: row[k] for k in dataset.JOIN_KEY} | {"is_laundering_raw": row["is_laundering_raw"]}
    return {"id": int(row["id"]), **fields}


# ------------------------------------------------------------------------- writing

_MOVE = f"""
    WITH moved AS (
        INSERT INTO transactions ({", ".join(COLUMNS)})
        SELECT {", ".join(f"s.{c}" for c in COLUMNS)}
        FROM {STAGING} s
        WHERE EXISTS (SELECT 1 FROM accounts WHERE id = s.from_account)
          AND EXISTS (SELECT 1 FROM accounts WHERE id = s.to_account)
        ON CONFLICT (id, ts) DO NOTHING
        RETURNING 1
    ), orphans AS (
        INSERT INTO ingest_quarantine (raw, error)
        SELECT s.raw, 'unknown account ' || CASE
                   WHEN NOT EXISTS (SELECT 1 FROM accounts WHERE id = s.from_account)
                   THEN s.from_account ELSE s.to_account END
        FROM {STAGING} s
        WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE id = s.from_account)
           OR NOT EXISTS (SELECT 1 FROM accounts WHERE id = s.to_account)
        RETURNING 1
    )
    SELECT (SELECT count(*) FROM moved), (SELECT count(*) FROM orphans),
           (SELECT count(*) FROM {STAGING})
"""


class BatchWriter:
    """One connection, one TEMP staging table, one transaction per batch."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._db = connection
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TEMP TABLE IF NOT EXISTS {STAGING} "
                "(LIKE transactions INCLUDING DEFAULTS, raw jsonb) ON COMMIT DELETE ROWS"
            )
        connection.commit()

    def position(self) -> dict[str, Any] | None:
        with self._db.cursor() as cursor:
            cursor.execute("SELECT value FROM settings WHERE key = %s", (POSITION_KEY,))
            row = cursor.fetchone()
        self._db.commit()
        return row[0] if row else None

    def write(self, batch: pd.DataFrame) -> tuple[int, int, int]:
        """(committed, quarantined, duplicates) for one batch, in one transaction."""
        valid, rejected = validate(batch)
        last = batch.iloc[-1]
        position = {"ts": last["sort_ts"].isoformat(), "id": int(last["id"])}
        with self._db.cursor() as cursor:
            if len(valid):
                buffer = io.StringIO()
                valid.to_csv(buffer, header=False, index=False)
                columns = ", ".join((*COLUMNS, "raw"))
                with cursor.copy(f"COPY {STAGING} ({columns}) FROM STDIN (FORMAT csv)") as copy:
                    copy.write(buffer.getvalue())
                cursor.execute(_MOVE)
                moved, orphans, staged = cursor.fetchone() or (0, 0, 0)
            else:
                moved = orphans = staged = 0
            if len(rejected):
                cursor.executemany(
                    "INSERT INTO ingest_quarantine (raw, error) VALUES (%s, %s)",
                    [(json.dumps(_raw(row)), row["error"]) for row in rejected.to_dict("records")],
                )
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (POSITION_KEY, json.dumps(position)),
            )
        self._db.commit()
        return int(moved), int(orphans) + len(rejected), int(staged) - int(moved) - int(orphans)


# ------------------------------------------------------------------------- pacing


@dataclass
class _Window:
    """What happened since the last progress report."""

    start: float
    rows: int = 0
    latencies: list[float] = field(default_factory=list)


def due_times(
    sort_ts: "pd.Series[pd.Timestamp]",
    config: ReplayConfig,
    *,
    first_ts: pd.Timestamp | None = None,
    offset: int = 0,
) -> "np.ndarray[Any, Any]":
    """Seconds after start at which each row may be sent: the later of its rate slot and its
    compressed dataset time. Non-decreasing, since both are. ``offset`` is how many rows came
    before these and ``first_ts`` the replay's first timestamp, so chunks line up."""
    n = len(sort_ts)
    by_rate = (offset + np.arange(n)) / config.rate if config.rate > 0 else np.zeros(n)
    if config.compression > 0 and n:
        origin = sort_ts.iloc[0] if first_ts is None else first_ts
        by_time = (sort_ts - origin).dt.total_seconds().to_numpy() / config.compression
    else:
        by_time = np.zeros(n)
    return np.asarray(np.maximum(by_rate, by_time), dtype=np.float64)


class _Pending:
    """Rows read but not yet written, refilled from the stream a chunk at a time."""

    def __init__(self, chunks: Iterator[pd.DataFrame], config: ReplayConfig, report: ReplayReport):
        self._chunks, self._config, self._report = chunks, config, report
        self.rows = pd.DataFrame()
        self.due: np.ndarray[Any, Any] = np.zeros(0)
        self.exhausted = False
        self._consumed = 0  # rows taken from the stream so far (for rate slots and --limit)
        self._first_ts: pd.Timestamp | None = None

    def fill(self, at_least: int) -> None:
        """Read chunks until ``at_least`` rows are pending or the stream (or --limit) ends."""
        limit = self._config.limit
        while len(self.rows) < at_least and not self.exhausted:
            chunk = next(self._chunks, None)
            if chunk is not None and limit is not None:
                chunk = chunk.iloc[: max(0, limit - self._consumed)]
            if chunk is None or chunk.empty:
                self.exhausted = True
                break
            chunk = chunk.reset_index(drop=True)
            if self._first_ts is None:
                self._first_ts = chunk["sort_ts"].iloc[0]
            self._report.corrupted_ids += corrupt(
                chunk, self._config.corrupt_rate, self._config.seed
            )
            due = due_times(
                chunk["sort_ts"], self._config, first_ts=self._first_ts, offset=self._consumed
            )
            self._consumed += len(chunk)
            self.rows = pd.concat([self.rows, chunk], ignore_index=True)
            self.due = np.concatenate([self.due, due])

    def take(self, count: int) -> pd.DataFrame:
        batch = self.rows.iloc[:count]
        self.rows, self.due = self.rows.iloc[count:].reset_index(drop=True), self.due[count:]
        return batch


def _resumed(
    chunks: Iterator[pd.DataFrame], position: dict[str, Any] | None
) -> Iterator[pd.DataFrame]:
    """Drop rows at or before the watermark (the stream is ordered, so only early chunks)."""
    if position is None:
        yield from chunks
        return
    ts, row_id = pd.Timestamp(position["ts"]), int(position["id"])
    for chunk in chunks:
        later = (chunk["sort_ts"] > ts) | ((chunk["sort_ts"] == ts) & (chunk["id"] > row_id))
        if later.any():
            yield chunk[later]


def replay(
    raw_dir: Path,
    config: ReplayConfig | None = None,
    *,
    echo: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> ReplayReport:
    config = config or ReplayConfig()
    with db.connect() as connection:
        writer = BatchWriter(connection)
        resume = None if config.from_start else writer.position()
        if resume is not None:
            echo(f"resuming after {resume['ts']} id {resume['id']}")
        report = ReplayReport()
        pending = _Pending(_resumed(stream_ordered(raw_dir, echo=echo), resume), config, report)
        pending.fill(config.batch_size)

        start = clock()
        window = _Window(start=start)

        def emit(final: bool = False) -> None:
            now = clock()
            span = max(now - window.start, 1e-9)
            latencies = window.latencies or [0.0]
            fields = {
                "rows_per_s": round(window.rows / span, 1),
                "committed": report.committed,
                "quarantined": report.quarantined,
                "duplicates": report.duplicates,
                "batch_ms_p50": round(statistics.median(latencies), 1),
                "batch_ms_p95": round(_p95(latencies), 1),
                "position": report.position,
            }
            log.info("replay_finished" if final else "replay_progress", **fields)
            echo(
                f"{'done' if final else 'progress'}: {fields['rows_per_s']:,} rows/s, "
                f"{report.committed:,} committed, {report.quarantined:,} quarantined, "
                f"{report.duplicates:,} duplicates, batch p50 {fields['batch_ms_p50']} ms "
                f"p95 {fields['batch_ms_p95']} ms"
            )
            window.start, window.rows, window.latencies = now, 0, []

        while len(pending.rows):
            elapsed = clock() - start
            n = len(pending.rows)
            ready = int(np.searchsorted(pending.due, elapsed, side="right"))
            end = min(n, config.batch_size, ready)
            waited = elapsed - pending.due[0] if end > 0 else 0.0
            last_rows = pending.exhausted and end == n
            if end > 0 and (end >= config.batch_size or last_rows or waited >= config.flush_after):
                batch = pending.take(end)
                batch_start = clock()
                committed, quarantined, duplicates = writer.write(batch)
                window.latencies.append((clock() - batch_start) * 1000)
                window.rows += len(batch)
                report.committed += committed
                report.quarantined += quarantined
                report.duplicates += duplicates
                report.batches += 1
                last = batch.iloc[-1]
                report.position = {"ts": last["sort_ts"].isoformat(), "id": int(last["id"])}
                pending.fill(config.batch_size)
                if clock() - window.start >= config.report_every:
                    emit()
                continue
            next_due = pending.due[end] if end < n else float("inf")
            flush_at = pending.due[0] + config.flush_after if end > 0 else float("inf")
            sleep(max(0.0, min(next_due, flush_at) - (clock() - start)))
        report.corrupted_ids.sort()
        report.seconds = round(clock() - start, 2)
        emit(final=True)
    return report


def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20)[18] if len(values) >= 2 else values[0]
