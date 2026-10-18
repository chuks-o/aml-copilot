"""``aml seed``: load HI-Small into Postgres (accounts with KYC profiles, transactions, settings).

The whole reload is one database transaction: empty the dataset tables, COPY everything back,
write the settings, commit. A failure changes nothing, and because ids, profiles and settings
are all derived deterministically from the files, running it twice leaves identical data.
Rationale: docs/decisions/0023-seed-and-download.md.

Why COPY: an INSERT is a statement per row (parse, plan, execute, acknowledge, often a network
round trip). COPY streams rows over one statement and the server parses them in a tight loop,
which for millions of rows is one to two orders of magnitude faster. Batches bound our memory
and give progress output.
"""

import io
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg import sql

from aml import db
from aml.data import dataset, kyc

BATCH_SIZE = 50_000
TRANSACTION_COLUMNS = (
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
ACCOUNT_COLUMNS = (
    "id",
    "bank_id",
    "account_number",
    "entity_type",
    "kyc_profile",
    "is_high_volume",
    "created_at",
)
REPORTED_TABLES = ("accounts", "transactions", "settings", "ingest_quarantine", "alerts", "cases")


class SeedError(RuntimeError):
    """The seed can't run safely (missing files, or workflow data that a reload would destroy)."""


@dataclass
class SeedReport:
    tables: dict[str, int]
    partitions: dict[str, int]
    analysis_end: datetime
    after_end: dict[str, int]
    gap: dataset.ActivityGap
    high_volume_banks: dict[str, int]
    unlisted_by_format: dict[str, int]
    inconsistent_percent: dict[str, float]
    fingerprints: dict[str, str]
    seconds: dict[str, float] = field(default_factory=dict)


def _require(raw_dir: Path, name: str) -> Path:
    path = raw_dir / name
    if not path.is_file():
        raise SeedError(f"{path} is missing; run `aml download` first")
    return path


def _accounts(
    transactions: pd.DataFrame, real: pd.DataFrame, gap: dataset.ActivityGap, end: datetime
) -> pd.DataFrame:
    """One row per account that appears in a transaction, with its profile."""
    counts = dataset.activity(transactions)
    first_seen = (
        pd.concat(
            [
                transactions[["from_account", "ts"]].rename(columns={"from_account": "id"}),
                transactions[["to_account", "ts"]].rename(columns={"to_account": "id"}),
            ]
        )
        .groupby("id")["ts"]
        .min()
    )
    info = real.set_index("id")
    missing = counts.index.difference(info.index)
    if len(missing):
        raise dataset.DatasetError(f"{len(missing)} accounts are not in {dataset.ACCOUNTS_FILE}")
    # Monthly rate over the analysis window (normal activity stops at ANALYSIS_END).
    days = (end - transactions["ts"].min().floor("D").to_pydatetime()).days
    merged = (
        counts.rename("count")
        .to_frame()
        .join(info, how="left")
        .join(first_seen.rename("first_seen"))
        .rename_axis("id")
        .reset_index()
        .sort_values("id", ignore_index=True)
    )
    profiles = [
        json.dumps(
            kyc.profile(
                str(row["id"]),
                entity_type=str(row["entity_type"]),
                real={
                    "bank_name": str(row["bank_name"]),
                    "entity_id": str(row["entity_id"]),
                    "entity_name": str(row["entity_name"]),
                },
                monthly_transactions=float(row["count"]) * 30 / days,
                first_seen=pd.Timestamp(row["first_seen"]).to_pydatetime(),
            ),
            sort_keys=True,
        )
        for row in merged.to_dict("records")
    ]
    parts = merged["id"].str.split(":", n=1, expand=True)
    return pd.DataFrame(
        {
            "id": merged["id"],
            "bank_id": parts[0],
            "account_number": parts[1],
            "entity_type": merged["entity_type"],
            "kyc_profile": profiles,
            "is_high_volume": merged["count"] >= gap.above,
            # Not the column default now(): a reload must reproduce every value (idempotency).
            # The dataset's first instant, i.e. "known since the data begins".
            "created_at": str(transactions["ts"].min().floor("D")),
        }
    )


def _copy(
    cursor: psycopg.Cursor[Any], table: str, columns: tuple[str, ...], frame: pd.DataFrame
) -> None:
    buffer = io.StringIO()
    frame.to_csv(buffer, columns=list(columns), header=False, index=False)
    statement = sql.SQL("COPY {table} ({columns}) FROM STDIN (FORMAT csv)").format(
        table=sql.Identifier(table), columns=sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with cursor.copy(statement) as copy:
        copy.write(buffer.getvalue())


def _fingerprint(cursor: psycopg.Cursor[Any], table: str, order: str) -> str:
    """Row count plus a content hash of every row, in key order: equal across identical loads."""
    query = sql.SQL(
        "SELECT count(*), md5(string_agg(md5(t::text), '' ORDER BY {order})) FROM {table} t"
    ).format(order=sql.SQL(order), table=sql.Identifier(table))
    cursor.execute(query)
    count, digest = cursor.fetchone() or (0, None)
    return f"{count} rows, md5 {digest}"


def _deferred_definitions(cursor: psycopg.Cursor[Any]) -> tuple[list[str], list[str]]:
    """The exact DDL of transactions' secondary indexes and foreign keys, from the catalog.

    Dropped before the bulk load and re-created after it: building an index once and validating
    a foreign key with one join is much faster than maintaining both for each of 5M rows. Read
    from Postgres (not repeated here) so it can't drift from the migration.
    """
    cursor.execute(
        "SELECT pg_get_indexdef(indexrelid) FROM pg_index "
        "WHERE indrelid = 'transactions'::regclass AND NOT indisprimary ORDER BY indexrelid"
    )
    # pg_get_indexdef says "ON ONLY" for a partitioned index, which would re-create it on the
    # parent alone (invalid, no partition indexes). Without ONLY it cascades to every partition.
    indexes = [row[0].replace(" ON ONLY ", " ON ", 1) for row in cursor.fetchall()]
    cursor.execute(
        "SELECT format('ALTER TABLE transactions ADD CONSTRAINT %I %s', conname, "
        "pg_get_constraintdef(oid)) FROM pg_constraint "
        "WHERE conrelid = 'transactions'::regclass AND contype = 'f' ORDER BY conname"
    )
    foreign_keys = [row[0] for row in cursor.fetchall()]
    return indexes, foreign_keys


def _check_indexes(cursor: psycopg.Cursor[Any]) -> None:
    """Every transactions index is valid and present on every partition, or the load fails."""
    cursor.execute(
        "SELECT p.indexrelid::regclass::text, p.indisvalid, "
        "(SELECT count(*) FROM pg_inherits i WHERE i.inhparent = p.indexrelid), "
        "(SELECT count(*) FROM pg_inherits i WHERE i.inhparent = 'transactions'::regclass) "
        "FROM pg_index p WHERE p.indrelid = 'transactions'::regclass"
    )
    broken = [
        f"{name} (valid={valid}, on {children}/{partitions} partitions)"
        for name, valid, children, partitions in cursor.fetchall()
        if not valid or children != partitions
    ]
    if broken:
        raise SeedError(f"transactions indexes not rebuilt: {', '.join(broken)}")


def _drop_deferred(cursor: psycopg.Cursor[Any]) -> None:
    cursor.execute(
        "SELECT indexrelid::regclass::text FROM pg_index "
        "WHERE indrelid = 'transactions'::regclass AND NOT indisprimary"
    )
    for (index,) in cursor.fetchall():
        cursor.execute(sql.SQL("DROP INDEX {}").format(sql.Identifier(index)))
    cursor.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'transactions'::regclass AND contype = 'f'"
    )
    for (name,) in cursor.fetchall():
        cursor.execute(
            sql.SQL("ALTER TABLE transactions DROP CONSTRAINT {}").format(sql.Identifier(name))
        )


def seed(
    raw_dir: Path, *, echo: Callable[[str], None] = print, batch_size: int = BATCH_SIZE
) -> SeedReport:
    seconds: dict[str, float] = {}
    mark = time.monotonic()

    def lap(name: str) -> None:
        nonlocal mark
        now = time.monotonic()
        seconds[name] = round(now - mark, 1)
        mark = now
        echo(f"  [{name}: {seconds[name]} s]")

    files = {
        name: _require(raw_dir, name)
        for name in (dataset.TRANSACTIONS_FILE, dataset.PATTERNS_FILE, dataset.ACCOUNTS_FILE)
    }
    echo(f"reading {raw_dir}")
    raw = dataset.read_transactions(files[dataset.TRANSACTIONS_FILE])
    patterns = dataset.read_patterns(files[dataset.PATTERNS_FILE])
    transactions = dataset.normalise(raw, patterns)
    end = dataset.analysis_end(transactions)
    gap = dataset.activity_gap(dataset.activity(transactions))
    lap("parse")
    accounts = _accounts(
        transactions, dataset.read_accounts(files[dataset.ACCOUNTS_FILE]), gap, end
    )
    lap("profiles")

    settings = {
        "ANALYSIS_END": end.isoformat().replace("+00:00", "Z"),
        "HIGH_VOLUME_CUT": {"below": gap.below, "above": gap.above},
        "DATASET": {
            "files": {name: dataset.sha256(path) for name, path in files.items()},
            "transactions": len(transactions),
            "accounts": len(accounts),
        },
        "KYC": {
            "seed": kyc.SEED,
            "inconsistent_percent": kyc.INCONSISTENT_SHARE,
            "synthetic_fields": list(kyc.SYNTHETIC_FIELDS),
        },
    }
    out = transactions.assign(ts=transactions["ts"].astype(str))  # "2022-09-01 00:20:00+00:00"
    lap("prepare")

    with db.connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM alerts")
        (alerts,) = cursor.fetchone() or (0,)
        if alerts:
            raise SeedError(
                f"{alerts} alerts reference accounts; a reload would destroy workflow data. "
                "Reset the database (make down && make up) to reseed."
            )
        # Not TRUNCATE accounts: Postgres refuses while any table (alerts) has an FK to it,
        # and CASCADE would hit case_events' append-only trigger. Nothing references
        # transactions; deleting accounts checks FKs only against tables proven empty above.
        cursor.execute("TRUNCATE transactions")
        cursor.execute("DELETE FROM accounts")
        indexes, foreign_keys = _deferred_definitions(cursor)
        _drop_deferred(cursor)
        lap("clear")
        _copy(cursor, "accounts", ACCOUNT_COLUMNS, accounts)
        echo(f"copied {len(accounts):,} accounts")
        for start in range(0, len(out), batch_size):
            _copy(cursor, "transactions", TRANSACTION_COLUMNS, out.iloc[start : start + batch_size])
            done = min(start + batch_size, len(out))
            if done % 1_000_000 < batch_size or done == len(out):
                echo(f"copied {done:,} / {len(out):,} transactions")
        lap("copy")
        for statement in indexes:
            cursor.execute(statement)
        _check_indexes(cursor)
        lap("indexes")
        for statement in foreign_keys:
            cursor.execute(statement)
        lap("foreign keys")
        cursor.execute("SELECT setval('transactions_id_seq', (SELECT max(id) FROM transactions))")
        for key, value in settings.items():
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, json.dumps(value, sort_keys=True)),
            )
        connection.commit()
        lap("commit")

        tables: dict[str, int] = {}
        for table in REPORTED_TABLES:
            cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
            tables[table] = int((cursor.fetchone() or (0,))[0])
        cursor.execute(
            "SELECT tableoid::regclass::text, count(*) FROM transactions GROUP BY 1 ORDER BY 1"
        )
        partitions = {str(name): int(count) for name, count in cursor.fetchall()}
        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_laundering) "
            "FROM transactions WHERE ts >= %s",
            (end,),
        )
        after, after_laundering = (int(n) for n in cursor.fetchone() or (0, 0))
        fingerprints = {
            "accounts": _fingerprint(cursor, "accounts", "id"),
            "transactions": _fingerprint(cursor, "transactions", "id, ts"),
            "settings": _fingerprint(cursor, "settings", "key"),
        }
        lap("report")

    hubs = accounts.loc[accounts["is_high_volume"], "bank_id"].value_counts()
    laundering_accounts = set(
        transactions.loc[transactions["is_laundering"], "from_account"]
    ) | set(transactions.loc[transactions["is_laundering"], "to_account"])
    flagged = accounts["id"].map(kyc.is_inconsistent)
    involved = accounts["id"].isin(laundering_accounts)
    unlisted = transactions.loc[transactions["pattern"] == dataset.UNLISTED, "payment_format"]
    return SeedReport(
        tables=tables,
        partitions=partitions,
        analysis_end=end,
        after_end={
            "rows": after,
            "laundering": after_laundering,
            "clean": after - after_laundering,
        },
        gap=gap,
        high_volume_banks={str(k): int(v) for k, v in hubs.items()},
        unlisted_by_format={str(k): int(v) for k, v in unlisted.value_counts().items()},
        inconsistent_percent={
            "laundering accounts": round(100 * float(flagged[involved].mean()), 2),
            "other accounts": round(100 * float(flagged[~involved].mean()), 2),
        },
        fingerprints=fingerprints,
        seconds=seconds,
    )
