"""Alert labels and the frozen dev/test time split (``aml label``, ``aml label --check``).

- **Label**: positive if the alerted account has a laundering transaction, on either side,
  in ``(triggered_at - 72 h, triggered_at]``. ``triggered_at`` is dataset time (0029).
- **typology_label**: the most common *listed* pattern among those transactions (ties
  alphabetical), ``UNLISTED`` if all are unlisted, null for negatives.
- **heldout_cycle**: a positive whose laundering transactions are all ``CYCLE``. Never trained
  or tuned on: an unseen-typology check.
- **split**: by ``triggered_at`` within the normal-activity period, from the first data day up
  to ``ANALYSIS_END``. The first 60% of its calendar days are ``dev``, the rest ``test``.

``backend/data/splits.json`` records the period, counts, positive rates and a SHA-256 of the
sorted ``(alert_id, label, split)`` list; ``--check`` fails if the database no longer matches.
Labels are ground truth: never exposed by the API (0014) and never model inputs.
Rationale: docs/decisions/0029-labels-and-time-split.md.
"""

import hashlib
import json
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

LABEL_WINDOW = timedelta(hours=72)
DEV_SHARE = 0.6
UNLISTED = "UNLISTED"
CYCLE = "CYCLE"
SPLITS_FILE = Path(__file__).resolve().parents[3] / "data" / "splits.json"


class LabelError(RuntimeError):
    """The data breaks a labelling rule, or no longer matches the frozen splits."""


# ------------------------------------------------------------------------ pure rules


@dataclass(frozen=True)
class Period:
    """The normal-activity period and its dev/test boundary (all UTC midnights)."""

    start: datetime
    dev_end: datetime  # exclusive end of dev, start of test
    end: datetime  # ANALYSIS_END, exclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days


def split_period(
    data_start: datetime, analysis_end: datetime, dev_share: float = DEV_SHARE
) -> Period:
    """Calendar days from the first data day up to ANALYSIS_END; the first floor(share x days)
    are dev. ANALYSIS_END is a UTC midnight (0023)."""
    start = datetime(data_start.year, data_start.month, data_start.day, tzinfo=UTC)
    days = (analysis_end - start).days
    if days < 2 or analysis_end != start + timedelta(days=days):
        raise LabelError(f"cannot split {start} .. {analysis_end} into whole days")
    return Period(
        start=start, dev_end=start + timedelta(days=math.floor(days * dev_share)), end=analysis_end
    )


def split_of(triggered_at: datetime, period: Period) -> str:
    if not period.start <= triggered_at < period.end:
        raise LabelError(
            f"alert triggered at {triggered_at} is outside {period.start} .. {period.end}"
        )
    return "dev" if triggered_at < period.dev_end else "test"


@dataclass(frozen=True)
class Label:
    label: bool
    typology_label: str | None
    heldout_cycle: bool


def label_from(patterns: Sequence[str]) -> Label:
    """From the patterns of the laundering transactions in the alert's 72 h window."""
    if not patterns:
        return Label(label=False, typology_label=None, heldout_cycle=False)
    listed = Counter(p for p in patterns if p != UNLISTED)
    if listed:
        top = max(listed.values())
        typology = min(p for p, n in listed.items() if n == top)  # ties: alphabetical
    else:
        typology = UNLISTED
    return Label(
        label=True,
        typology_label=typology,
        heldout_cycle=all(p == CYCLE for p in patterns),
    )


@dataclass(frozen=True)
class AlertLabel:
    alert_id: UUID
    label: bool
    typology_label: str | None
    split: str
    heldout_cycle: bool


def _sha256(rows: Iterable[tuple[UUID, bool, str]]) -> str:
    lines = sorted(f"{alert_id},{str(label).lower()},{split}" for alert_id, label, split in rows)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def fingerprint(labels: Sequence[AlertLabel]) -> str:
    """SHA-256 of the sorted ``(alert_id, label, split)`` list."""
    return _sha256((a.alert_id, a.label, a.split) for a in labels)


def summary(labels: Sequence[AlertLabel], period: Period) -> dict[str, Any]:
    splits: dict[str, Any] = {}
    for name in ("dev", "test"):
        rows = [a for a in labels if a.split == name]
        positives = sum(a.label for a in rows)
        splits[name] = {
            "alerts": len(rows),
            "positives": positives,
            "positive_rate": round(positives / len(rows), 6) if rows else None,
            "heldout_cycle": sum(a.heldout_cycle for a in rows),
        }
    return {
        "period": {
            "start": period.start.isoformat(),
            "dev_end": period.dev_end.isoformat(),
            "end": period.end.isoformat(),
            "days": period.days,
            "dev_share": DEV_SHARE,
        },
        "label_window_hours": LABEL_WINDOW.total_seconds() / 3600,
        "splits": splits,
        "sha256": fingerprint(labels),
    }


# --------------------------------------------------------------------------- database

_WINDOW_PATTERNS = """
    SELECT a.id, a.triggered_at,
           coalesce(array_agg(w.pattern) FILTER (WHERE w.pattern IS NOT NULL), '{}')
    FROM alerts a
    LEFT JOIN LATERAL (
        SELECT pattern FROM transactions
        WHERE from_account = a.account_id AND is_laundering
          AND ts > a.triggered_at - %(window)s AND ts <= a.triggered_at
        UNION ALL
        SELECT pattern FROM transactions
        WHERE to_account = a.account_id AND from_account <> a.account_id AND is_laundering
          AND ts > a.triggered_at - %(window)s AND ts <= a.triggered_at
    ) w ON true
    GROUP BY a.id, a.triggered_at
"""


def _period(conn: psycopg.Connection[Any]) -> Period:
    row = conn.execute("SELECT value FROM settings WHERE key = 'ANALYSIS_END'").fetchone()
    if row is None:
        raise LabelError("settings.ANALYSIS_END is missing: run `aml seed` first")
    analysis_end = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
    first = conn.execute("SELECT min(ts) FROM transactions").fetchone()
    if first is None or first[0] is None:
        raise LabelError("no transactions")
    return split_period(first[0], analysis_end)


def assert_no_alert_after(conn: psycopg.Connection[Any], analysis_end: datetime) -> None:
    """Nothing may alert past ANALYSIS_END (0023); a violation stops labelling."""
    row = conn.execute(
        "SELECT count(*), min(triggered_at) FROM alerts WHERE triggered_at >= %s", (analysis_end,)
    ).fetchone()
    if row and row[0]:
        raise LabelError(
            f"{row[0]} alerts triggered at or after ANALYSIS_END {analysis_end} (earliest {row[1]})"
        )


def compute(conn: psycopg.Connection[Any]) -> tuple[list[AlertLabel], Period]:
    period = _period(conn)
    assert_no_alert_after(conn, period.end)
    labels = []
    for alert_id, triggered_at, patterns in conn.execute(
        _WINDOW_PATTERNS, {"window": LABEL_WINDOW}
    ):
        result = label_from(patterns)
        labels.append(
            AlertLabel(alert_id=alert_id, split=split_of(triggered_at, period), **asdict(result))
        )
    return labels, period


def apply(conn: psycopg.Connection[Any], labels: Sequence[AlertLabel]) -> None:
    """Write every alert's label columns in one statement."""
    conn.execute(
        "UPDATE alerts a SET label = v.label, typology_label = v.typology_label, split = v.split, "
        "heldout_cycle = v.heldout "
        "FROM unnest(%s::uuid[], %s::bool[], %s::text[], %s::text[], %s::bool[]) "
        "AS v(id, label, typology_label, split, heldout) WHERE a.id = v.id",
        (
            [a.alert_id for a in labels],
            [a.label for a in labels],
            [a.typology_label for a in labels],
            [a.split for a in labels],
            [a.heldout_cycle for a in labels],
        ),
    )


def run(conn: psycopg.Connection[Any], *, path: Path = SPLITS_FILE) -> dict[str, Any]:
    """Label every alert, store it, and write ``splits.json``. One transaction."""
    labels, period = compute(conn)
    apply(conn, labels)
    result = summary(labels, period)
    conn.commit()
    path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def check(conn: psycopg.Connection[Any], *, path: Path = SPLITS_FILE) -> dict[str, Any]:
    """Recompute without writing; fail if the stored labels or the frozen file disagree."""
    if not path.is_file():
        raise LabelError(f"{path} does not exist: nothing is frozen yet (run `aml label`)")
    frozen = json.loads(path.read_text())
    labels, period = compute(conn)
    current = summary(labels, period)
    stored = conn.execute(
        "SELECT id, coalesce(label, false), coalesce(split, '') FROM alerts"
    ).fetchall()
    conn.rollback()
    stored_hash = _sha256(stored)
    problems = []
    if current["sha256"] != frozen.get("sha256"):
        problems.append("recomputed labels differ from splits.json")
    if stored_hash != frozen.get("sha256"):
        problems.append("labels stored on alerts differ from splits.json")
    if current["period"] != frozen.get("period"):
        problems.append("the split period differs from splits.json")
    if problems:
        raise LabelError(
            "; ".join(problems) + ". If the change is intended, run `aml label` and commit "
            "the new splits.json with a decision record."
        )
    return current
