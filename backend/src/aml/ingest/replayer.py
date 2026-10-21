"""``aml replay``: stream HI-Small into Postgres as if it were arriving live.

Rows go in ``(ts, id)`` order. A row is due when both the rate cap (``rate`` rows/s) and the
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

import io
import json
import statistics
import time
from collections.abc import Callable
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


def load_ordered(raw_dir: Path) -> pd.DataFrame:
    """Every row as raw text, with its id (file position), pattern and original sort key."""
    raw = dataset.read_transactions(raw_dir / dataset.TRANSACTIONS_FILE)
    patterns = dataset.read_patterns(raw_dir / dataset.PATTERNS_FILE)
    raw["pattern"] = dataset.join_patterns(raw, patterns)
    raw["id"] = np.arange(1, len(raw) + 1)
    raw["sort_ts"] = pd.to_datetime(raw["ts_raw"], format="%Y/%m/%d %H:%M", utc=True)
    return raw.sort_values(["sort_ts", "id"], kind="stable", ignore_index=True)


def corrupt(rows: pd.DataFrame, rate: float, seed: int, total: int) -> list[int]:
    """Damage about ``rate`` of the rows in place; returns their ids.

    Chosen by file position (``seed`` over all ``total`` rows), so --limit and resuming
    never change which rows are damaged.
    """
    if rate <= 0:
        return []
    chosen = np.random.default_rng(seed).random(total) < rate
    kind_of = (np.cumsum(chosen) - 1) % len(CORRUPTIONS)  # round-robin in file order
    ids = rows["id"].to_numpy()
    positions = np.flatnonzero(chosen[ids - 1])
    picked = rows.index[positions]
    for position, index in zip(positions, picked, strict=True):
        kind = CORRUPTIONS[int(kind_of[ids[position] - 1])]
        if kind == "currency":
            rows.at[index, "currency_paid_name"] = BAD_CURRENCY
        elif kind == "amount":
            rows.at[index, "amount_paid"] = "-" + str(rows.at[index, "amount_paid"])
        else:
            rows.at[index, "ts_raw"] = BAD_TIMESTAMP
    return sorted(int(i) for i in rows.loc[picked, "id"])


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


def due_times(sort_ts: "pd.Series[pd.Timestamp]", config: ReplayConfig) -> "np.ndarray[Any, Any]":
    """Seconds after start at which each row may be sent: the later of its rate slot and its
    compressed dataset time. Non-decreasing, since both are."""
    n = len(sort_ts)
    by_rate = np.arange(n) / config.rate if config.rate > 0 else np.zeros(n)
    if config.compression > 0 and n:
        offsets = (sort_ts - sort_ts.iloc[0]).dt.total_seconds().to_numpy()
        by_time = offsets / config.compression
    else:
        by_time = np.zeros(n)
    return np.asarray(np.maximum(by_rate, by_time), dtype=np.float64)


def replay(
    raw_dir: Path,
    config: ReplayConfig | None = None,
    *,
    echo: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> ReplayReport:
    config = config or ReplayConfig()
    rows = load_ordered(raw_dir)
    total = len(rows)
    with db.connect() as connection:
        writer = BatchWriter(connection)
        resume = None if config.from_start else writer.position()
        if resume is not None:
            ts, row_id = pd.Timestamp(resume["ts"]), int(resume["id"])
            later = (rows["sort_ts"] > ts) | ((rows["sort_ts"] == ts) & (rows["id"] > row_id))
            rows = rows[later].reset_index(drop=True)
            echo(f"resuming after {resume['ts']} id {resume['id']}: {len(rows):,} rows left")
        if config.limit is not None:
            rows = rows.iloc[: config.limit].reset_index(drop=True)
        report = ReplayReport(corrupted_ids=corrupt(rows, config.corrupt_rate, config.seed, total))
        due = due_times(rows["sort_ts"], config)

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

        begin, n = 0, len(rows)
        while begin < n:
            elapsed = clock() - start
            ready = int(np.searchsorted(due, elapsed, side="right"))
            end = min(n, begin + config.batch_size, max(ready, begin))
            waited = elapsed - due[begin] if end > begin else 0.0
            if end > begin and (
                end - begin >= config.batch_size or end == n or waited >= config.flush_after
            ):
                batch_start = clock()
                committed, quarantined, duplicates = writer.write(rows.iloc[begin:end])
                window.latencies.append((clock() - batch_start) * 1000)
                window.rows += end - begin
                report.committed += committed
                report.quarantined += quarantined
                report.duplicates += duplicates
                report.batches += 1
                last = rows.iloc[end - 1]
                report.position = {"ts": last["sort_ts"].isoformat(), "id": int(last["id"])}
                begin = end
                if clock() - window.start >= config.report_every:
                    emit()
                continue
            next_due = due[end] if end < n else float("inf")
            flush_at = due[begin] + config.flush_after if end > begin else float("inf")
            sleep(max(0.0, min(next_due, flush_at) - (clock() - start)))
        report.seconds = round(clock() - start, 2)
        emit(final=True)
    return report


def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20)[18] if len(values) >= 2 else values[0]
