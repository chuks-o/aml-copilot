"""HI-Small files: parsing, normalisation, the pattern join, and facts derived from the data.

Pure functions over pandas frames; nothing here touches the network or the database.
Rationale: docs/decisions/0023-seed-and-download.md (and 0002, 0003, 0015 for the rules).
"""

import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pandas as pd

TRANSACTIONS_FILE = "HI-Small_Trans.csv"
PATTERNS_FILE = "HI-Small_Patterns.txt"
ACCOUNTS_FILE = "HI-Small_accounts.csv"

# Header of HI-Small_Trans.csv. "Account" appears twice: after "From Bank" it is the payer's
# account, after "To Bank" the payee's. pandas would silently call the second "Account.1".
TRANSACTION_HEADER = (
    "Timestamp",
    "From Bank",
    "Account",
    "To Bank",
    "Account",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
    "Is Laundering",
)
_RENAME = {
    "Timestamp": "ts_raw",
    "From Bank": "from_bank",
    "To Bank": "to_bank",
    "Amount Received": "amount_received",
    "Receiving Currency": "currency_received_name",
    "Amount Paid": "amount_paid",
    "Payment Currency": "currency_paid_name",
    "Payment Format": "payment_format_name",
    "Is Laundering": "is_laundering_raw",
}
_ACCOUNT_AFTER = {"from_bank": "from_account_number", "to_bank": "to_account_number"}
# The columns that identify a transaction's content: everything except the label (0003).
JOIN_KEY = (
    "ts_raw",
    "from_bank",
    "from_account_number",
    "to_bank",
    "to_account_number",
    "amount_received",
    "currency_received_name",
    "amount_paid",
    "currency_paid_name",
    "payment_format_name",
)
ACCOUNTS_HEADER = ("Bank Name", "Bank ID", "Account Number", "Entity ID", "Entity Name")

CURRENCIES = {
    "US Dollar": "USD",
    "Euro": "EUR",
    "Swiss Franc": "CHF",
    "Yuan": "CNY",
    "Shekel": "ILS",
    "Rupee": "INR",
    "UK Pound": "GBP",
    "Ruble": "RUB",
    "Yen": "JPY",
    "Bitcoin": "BTC",  # no ISO 4217 code (0014)
    "Canadian Dollar": "CAD",
    "Australian Dollar": "AUD",
    "Mexican Peso": "MXN",
    "Saudi Riyal": "SAR",
    "Brazil Real": "BRL",
}
PAYMENT_FORMATS = {
    "ACH": "ACH",
    "Bitcoin": "BITCOIN",
    "Cash": "CASH",
    "Cheque": "CHEQUE",
    "Credit Card": "CREDIT_CARD",
    "Reinvestment": "REINVESTMENT",
    "Wire": "WIRE",
}
TYPOLOGIES = {
    "FAN-IN": "FAN_IN",
    "FAN-OUT": "FAN_OUT",
    "CYCLE": "CYCLE",
    "BIPARTITE": "BIPARTITE",
    "STACK": "STACK",
    "SCATTER-GATHER": "SCATTER_GATHER",
    "GATHER-SCATTER": "GATHER_SCATTER",
    "RANDOM": "RANDOM",
}
UNLISTED = "UNLISTED"
ENTITY_TYPES = {
    "Corporation": "CORPORATION",
    "Partnership": "PARTNERSHIP",
    "Sole Proprietorship": "SOLE_PROPRIETORSHIP",
    "Individual": "INDIVIDUAL",
    "Country": "COUNTRY",
    "Direct": "DIRECT",
}
AMOUNT = r"^(0|[1-9][0-9]{0,17})(\.[0-9]{1,8})?$"  # OpenAPI Money, numeric(26,8)


class DatasetError(ValueError):
    """The raw files don't look like HI-Small; stop rather than load something wrong."""


# ----------------------------------------------------------------------------- reading


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _transaction_names(header: list[str]) -> list[str]:
    """Map the header to our names, by name; each "Account" by the bank column before it."""
    if tuple(header) != TRANSACTION_HEADER:
        raise DatasetError(f"unexpected header {header!r}; expected {list(TRANSACTION_HEADER)!r}")
    names: list[str] = []
    for column in header:
        if column == "Account":
            names.append(_ACCOUNT_AFTER[names[-1]])
        else:
            names.append(_RENAME[column])
    return names


def read_transactions(path: Path) -> pd.DataFrame:
    """The raw CSV, every column as text: bank codes keep their zeros, amounts their digits."""
    with path.open(newline="") as f:
        names = _transaction_names(next(csv.reader(f)))
    return pd.read_csv(path, header=0, names=names, dtype=str, keep_default_na=False)


def read_patterns(path: Path) -> pd.DataFrame:
    """Pattern rows with their typology and attempt number (the block's order in the file)."""
    names = _transaction_names(list(TRANSACTION_HEADER))
    rows: list[list[str]] = []
    pattern: str | None = None
    attempt = 0
    with path.open(newline="") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("BEGIN LAUNDERING ATTEMPT - "):
                name = line.removeprefix("BEGIN LAUNDERING ATTEMPT - ").split(":", 1)[0].strip()
                if name not in TYPOLOGIES:
                    raise DatasetError(f"{path.name}:{line_no}: unknown pattern {name!r}")
                pattern, attempt = TYPOLOGIES[name], attempt + 1
            elif line.startswith("END LAUNDERING ATTEMPT"):
                pattern = None
            elif pattern is None:
                raise DatasetError(f"{path.name}:{line_no}: transaction outside an attempt")
            else:
                fields = next(csv.reader([line]))
                if len(fields) != len(names):
                    raise DatasetError(f"{path.name}:{line_no}: expected {len(names)} fields")
                rows.append([*fields, pattern, str(attempt)])
    frame = pd.DataFrame(rows, columns=[*names, "pattern", "attempt_id"])
    return frame.astype({"attempt_id": "int64"})


def read_accounts(path: Path) -> pd.DataFrame:
    """HI-Small_accounts.csv: bank and entity per account (the real KYC fields)."""
    with path.open(newline="") as f:
        header = tuple(next(csv.reader(f)))
    if header != ACCOUNTS_HEADER:
        raise DatasetError(f"unexpected accounts header {list(header)!r}")
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    entity_kind = raw["Entity Name"].str.replace(r"\s*#\d+$", "", regex=True)
    unknown = sorted(set(entity_kind) - ENTITY_TYPES.keys())
    if unknown:
        raise DatasetError(f"unknown entity types {unknown!r}")
    bank_id = normalise_bank(raw["Bank ID"])
    return pd.DataFrame(
        {
            "id": bank_id + ":" + raw["Account Number"],
            "bank_name": raw["Bank Name"],
            "entity_id": raw["Entity ID"],
            "entity_name": raw["Entity Name"],
            "entity_type": entity_kind.map(ENTITY_TYPES),
        }
    )


# ----------------------------------------------------------------------- normalising


def normalise_bank(codes: "pd.Series[str]") -> "pd.Series[str]":
    """Strip leading zeros, deliberately and as text (0015): "010" and "0010" are bank "10"."""
    stripped = codes.str.lstrip("0")
    return stripped.where(stripped != "", "0")


def _mapped(values: "pd.Series[str]", mapping: dict[str, str], what: str) -> "pd.Series[str]":
    unknown = sorted(set(values.unique()) - mapping.keys())
    if unknown:
        raise DatasetError(f"unknown {what} {unknown!r}")
    return values.map(mapping)


def normalise(raw: pd.DataFrame, patterns: pd.DataFrame) -> pd.DataFrame:
    """Rows ready for the transactions table, in file order, with ids 1..N (their position)."""
    labels = raw["is_laundering_raw"]
    if not labels.isin(["0", "1"]).all():
        raise DatasetError("Is Laundering must be 0 or 1")
    for column in ("amount_paid", "amount_received"):
        bad = ~raw[column].str.fullmatch(AMOUNT)
        if bad.any():
            raise DatasetError(f"{column} not a decimal amount, e.g. {raw[column][bad].iloc[0]!r}")
    pattern = join_patterns(raw, patterns)
    return pd.DataFrame(
        {
            # Deterministic id: the row's 1-based position in the original file.
            "id": pd.RangeIndex(1, len(raw) + 1),
            "ts": pd.to_datetime(raw["ts_raw"], format="%Y/%m/%d %H:%M", utc=True),
            "from_account": normalise_bank(raw["from_bank"]) + ":" + raw["from_account_number"],
            "to_account": normalise_bank(raw["to_bank"]) + ":" + raw["to_account_number"],
            "amount_paid": raw["amount_paid"],
            "currency_paid": _mapped(raw["currency_paid_name"], CURRENCIES, "currencies"),
            "amount_received": raw["amount_received"],
            "currency_received": _mapped(raw["currency_received_name"], CURRENCIES, "currencies"),
            "payment_format": _mapped(
                raw["payment_format_name"], PAYMENT_FORMATS, "payment formats"
            ),
            "is_laundering": labels == "1",
            "pattern": pattern,
        }
    )


def join_patterns(raw: pd.DataFrame, patterns: pd.DataFrame) -> "pd.Series[str]":
    """Pattern name per row: the typology for patterned rows, UNLISTED for other laundering
    rows, None for clean rows. Joined on the full row content as text (0003)."""
    keys = list(JOIN_KEY)
    if patterns.duplicated(keys).any():
        raise DatasetError("a pattern row appears twice")
    merged = raw[keys].merge(
        patterns[[*keys, "pattern"]], on=keys, how="left", validate="many_to_one", indicator=True
    )
    matched = merged["_merge"] == "both"
    if matched.sum() != len(patterns):
        raise DatasetError(f"{len(patterns) - matched.sum()} pattern rows match no transaction")
    laundering = (raw["is_laundering_raw"] == "1").to_numpy()
    if (matched.to_numpy() & ~laundering).any():
        raise DatasetError("a patterned transaction is labelled clean")
    pattern = merged["pattern"].where(matched, None)
    pattern = pattern.where(~(laundering & ~matched.to_numpy()), UNLISTED)
    return pattern.set_axis(raw.index)


# ---------------------------------------------------------------------- derived facts


def activity(transactions: pd.DataFrame) -> "pd.Series[int]":
    """Transactions per account, sent plus received."""
    both = pd.concat([transactions["from_account"], transactions["to_account"]], ignore_index=True)
    return both.value_counts()


@dataclass(frozen=True)
class ActivityGap:
    below: int  # the highest count under the gap
    above: int  # the lowest count over it: the high-volume cut


def activity_gap(counts: "pd.Series[int]", floor: int = 10) -> ActivityGap:
    """The largest ratio between neighbouring distinct activity counts (ignoring counts under
    ``floor``, where any small step is a big ratio). Accounts at or above ``above`` are the
    high-volume population (T01: nobody between roughly 350 and 6,000)."""
    distinct = sorted(int(c) for c in counts.unique() if c >= floor)
    if len(distinct) < 2:
        raise DatasetError("too few active accounts to find an activity gap")
    below, above = max(pairwise(distinct), key=lambda p: p[1] / p[0])
    return ActivityGap(below=below, above=above)


def analysis_end(transactions: pd.DataFrame, share: float = 0.10) -> datetime:
    """End (exclusive, UTC midnight) of the last day whose clean volume is at least ``share`` of
    the median daily clean volume. After it the generator only finishes laundering chains."""
    clean = transactions.loc[~transactions["is_laundering"], "ts"]
    daily = clean.dt.floor("D").value_counts().sort_index()
    if daily.empty:
        raise DatasetError("no clean transactions")
    last_day = daily[daily >= share * daily.median()].index.max()
    return datetime(last_day.year, last_day.month, last_day.day, tzinfo=UTC) + timedelta(days=1)
