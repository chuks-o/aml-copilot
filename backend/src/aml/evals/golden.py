"""Golden set v1: a fixed, stratified sample of 80 dev alerts, and the labels a person records.

- **Sample** (``aml golden-sample``): 40 positives (4 per listed typology, about 32, plus 8
  ``UNLISTED`` positives without ACH) and 40 negatives (20 hard: one alert per T01 hard-negative
  account, near misses, high scores; 20 ordinary, spread by rule). Dev split only, no
  ``is_high_volume`` accounts, no ``heldout_cycle`` alerts, at most one alert per account. Drawn
  with ``SEED`` from the frozen labels (0029, 0031) and stored in ``golden_v1_sample.json``.
- **Labels** (``aml golden-label``, ``aml.evals.label_cli``): one JSON line per labelled alert in
  ``golden_v1.jsonl``, appended and flushed at once. The last line for an alert wins.

The labeller never sees a stratum or a ground-truth column: the screen reads through the API,
which doesn't expose them (0014). Rationale: docs/decisions/0032-golden-set.md.
"""

import json
import os
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from aml.evals import labels

GOLDEN_DIR = Path(__file__).resolve().parents[3] / "data" / "golden"
SAMPLE_FILE = GOLDEN_DIR / "golden_v1_sample.json"
LABELS_FILE = GOLDEN_DIR / "golden_v1.jsonl"
VERSION = "golden_v1"
SEED = 17

LISTED = (
    "BIPARTITE",
    "CYCLE",
    "FAN_IN",
    "FAN_OUT",
    "GATHER_SCATTER",
    "RANDOM",
    "SCATTER_GATHER",
    "STACK",
)
TYPOLOGIES = (*LISTED, labels.UNLISTED)  # what a labeller may record for ESCALATE
DECISIONS = ("ESCALATE", "CLOSE")
KEY_TRANSACTIONS = (3, 8)
NOTE_MAX = 500

# 0004: the T01 hard negatives. 4726:808FAF7C0 has alerts in test only, so it can't be sampled.
T01_ACCOUNTS = (
    "21611:8051A3FA0",
    "4726:808FAF7C0",
    "14277:80B847A90",
    "12:80010F6E0",
    "211:807661E30",
)
HIGH_SCORE = 0.9

QUOTAS = {
    "positive_listed": 32,  # spread evenly over the listed typologies
    "positive_unlisted_non_ach": 8,
    # One alert per T01 account with dev alerts, HIGH_SCORE_QUOTA high scores, near misses for
    # the rest.
    "negative_hard": 20,
    "negative_ordinary": 20,  # spread by rule in proportion to dev volume
}
HIGH_SCORE_QUOTA = 8


class GoldenError(RuntimeError):
    """The sample can't be drawn as specified, or a label breaks the recording rules."""


# ------------------------------------------------------------------------------ sample


@dataclass(frozen=True)
class Candidate:
    alert_id: UUID
    account_id: str
    group: str  # the typology for listed positives, the rule for ordinary negatives, else ""


@dataclass(frozen=True)
class SampleItem:
    alert_id: UUID
    account_id: str
    stratum: str
    group: str


def equal_shares(total: int, sizes: Mapping[str, int]) -> dict[str, int]:
    """``total`` spread as evenly as the groups allow; a short group's spare goes to the rest."""
    shares = dict.fromkeys(sizes, 0)
    left = total
    while left:
        open_groups = sorted(g for g in sizes if shares[g] < sizes[g])
        if not open_groups:
            raise GoldenError(f"only {total - left} of {total} candidates available")
        each = max(1, left // len(open_groups))
        # Largest pools first, so a remainder lands where there is most to draw from.
        for group in sorted(open_groups, key=lambda g: (-sizes[g], g)):
            take = min(each, sizes[group] - shares[group], left)
            shares[group] += take
            left -= take
            if not left:
                break
    return shares


def proportional_shares(total: int, sizes: Mapping[str, int]) -> dict[str, int]:
    """``total`` spread in proportion to ``sizes`` (largest remainder)."""
    whole = sum(sizes.values())
    if whole < total:
        raise GoldenError(f"only {whole} of {total} candidates available")
    exact = {g: total * n / whole for g, n in sizes.items()}
    shares = {g: int(x) for g, x in exact.items()}
    for g in sorted(sizes, key=lambda g: (-(exact[g] - shares[g]), g))[
        : total - sum(shares.values())
    ]:
        shares[g] += 1
    return shares


def draw(pools: Mapping[str, Sequence[Candidate]], seed: int = SEED) -> list[SampleItem]:
    """The sample from candidate pools, deterministic for a seed; at most one alert per account.

    Strata are filled in ``QUOTAS`` order. Within a group, candidates are sorted by id and then
    drawn by ``random.Random(seed)``, so the database's row order never matters.
    """
    rng = random.Random(seed)  # noqa: S311 - a reproducible draw, not a secret
    taken: set[str] = set()
    sample: list[SampleItem] = []

    def pick(stratum: str, candidates: Iterable[Candidate], n: int) -> int:
        ordered = sorted(candidates, key=lambda c: str(c.alert_id))
        rng.shuffle(ordered)
        got = 0
        for c in ordered:
            if got == n:
                break
            if c.account_id in taken:
                continue
            taken.add(c.account_id)
            sample.append(SampleItem(c.alert_id, c.account_id, stratum, c.group))
            got += 1
        return got

    def by_group(stratum: str) -> dict[str, list[Candidate]]:
        groups: dict[str, list[Candidate]] = {}
        for c in pools.get(stratum, ()):
            groups.setdefault(c.group, []).append(c)
        return groups

    def accounts(cs: Iterable[Candidate]) -> int:
        return len({c.account_id for c in cs} - taken)

    def exactly(stratum: str, candidates: Iterable[Candidate], n: int) -> None:
        if (got := pick(stratum, candidates, n)) < n:
            raise GoldenError(f"{stratum}: {got} of {n} candidates available")

    listed = by_group("positive_listed")
    shares = equal_shares(QUOTAS["positive_listed"], {g: accounts(cs) for g, cs in listed.items()})
    for group in sorted(shares):
        exactly("positive_listed", listed[group], shares[group])
    exactly(
        "positive_unlisted_non_ach",
        pools.get("positive_unlisted_non_ach", ()),
        QUOTAS["positive_unlisted_non_ach"],
    )

    hard = sum(pick("negative_t01", cs, 1) for _, cs in sorted(by_group("negative_t01").items()))
    exactly("negative_high_score", pools.get("negative_high_score", ()), HIGH_SCORE_QUOTA)
    exactly(
        "negative_near_miss",
        pools.get("negative_near_miss", ()),
        QUOTAS["negative_hard"] - hard - HIGH_SCORE_QUOTA,
    )

    ordinary = by_group("negative_ordinary")
    shares = proportional_shares(
        QUOTAS["negative_ordinary"], {g: accounts(cs) for g, cs in ordinary.items()}
    )
    for group in sorted(shares):
        exactly("negative_ordinary", ordinary[group], shares[group])

    rng.shuffle(sample)  # the labeller meets the strata mixed
    return sample


_DEV = """
    FROM alerts al JOIN accounts ac ON ac.id = al.account_id
    WHERE al.split = 'dev' AND NOT al.heldout_cycle AND NOT ac.is_high_volume
"""
_LAUNDERING_EVER = """EXISTS (
    SELECT 1 FROM transactions t WHERE t.from_account = al.account_id AND t.is_laundering
    UNION ALL
    SELECT 1 FROM transactions t WHERE t.to_account = al.account_id AND t.is_laundering)"""
_ACH_IN_WINDOW = """EXISTS (
    SELECT 1 FROM transactions t
    WHERE (t.from_account = al.account_id OR t.to_account = al.account_id) AND t.is_laundering
      AND t.payment_format = 'ACH'
      AND t.ts > al.triggered_at - %(window)s AND t.ts <= al.triggered_at)"""

POOL_QUERIES = {
    "positive_listed": f"SELECT al.id, al.account_id, al.typology_label {_DEV} "
    f"AND al.label AND al.typology_label <> '{labels.UNLISTED}'",
    "positive_unlisted_non_ach": f"SELECT al.id, al.account_id, '' {_DEV} "
    f"AND al.label AND al.typology_label = '{labels.UNLISTED}' AND NOT {_ACH_IN_WINDOW}",
    "negative_t01": f"SELECT al.id, al.account_id, al.account_id {_DEV} "
    "AND NOT al.label AND al.account_id = ANY(%(t01)s)",
    "negative_near_miss": f"SELECT al.id, al.account_id, '' {_DEV} "
    f"AND NOT al.label AND NOT al.account_id = ANY(%(t01)s) AND {_LAUNDERING_EVER}",
    "negative_high_score": f"SELECT al.id, al.account_id, '' {_DEV} "
    f"AND NOT al.label AND NOT al.account_id = ANY(%(t01)s) AND al.score >= %(high)s "
    f"AND NOT {_LAUNDERING_EVER}",
    "negative_ordinary": f"SELECT al.id, al.account_id, al.rule_id {_DEV} "
    f"AND NOT al.label AND NOT al.account_id = ANY(%(t01)s) AND al.score < %(high)s "
    f"AND NOT {_LAUNDERING_EVER}",
}


def pools(conn: psycopg.Connection[Any]) -> dict[str, list[Candidate]]:
    params = {"window": labels.LABEL_WINDOW, "t01": list(T01_ACCOUNTS), "high": HIGH_SCORE}
    result = {
        stratum: [Candidate(UUID(str(r[0])), r[1], r[2]) for r in conn.execute(sql, params)]
        for stratum, sql in POOL_QUERIES.items()
    }
    conn.rollback()
    return result


def sample_document(items: Sequence[SampleItem], frozen_sha256: str) -> dict[str, Any]:
    return {
        "version": VERSION,
        "seed": SEED,
        "splits_sha256": frozen_sha256,
        "quotas": QUOTAS,
        "counts": dict(sorted(Counter(i.stratum for i in items).items())),
        "t01_without_dev_alerts": sorted(
            set(T01_ACCOUNTS) - {i.account_id for i in items if i.stratum == "negative_t01"}
        ),
        "alerts": [{**asdict(i), "alert_id": str(i.alert_id)} for i in items],
    }


def build_sample(
    conn: psycopg.Connection[Any], splits_path: Path = labels.SPLITS_FILE
) -> dict[str, Any]:
    """Draw the sample from the database, which must still match the frozen splits."""
    frozen = labels.check(conn, path=splits_path)  # LabelError if labels moved since the freeze
    return sample_document(draw(pools(conn)), frozen["sha256"])


def write_sample(
    conn: psycopg.Connection[Any],
    path: Path = SAMPLE_FILE,
    splits_path: Path = labels.SPLITS_FILE,
) -> dict[str, Any]:
    if path.exists():
        raise GoldenError(f"{path} exists: the sample is fixed (use --check to verify it)")
    document = build_sample(conn, splits_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n")
    return document


def check_sample(
    conn: psycopg.Connection[Any],
    path: Path = SAMPLE_FILE,
    splits_path: Path = labels.SPLITS_FILE,
) -> dict[str, Any]:
    stored = load_sample_document(path)
    document = build_sample(conn, splits_path)
    if document != stored:
        raise GoldenError(f"{path} no longer matches a fresh draw with seed {SEED}")
    return document


def load_sample_document(path: Path = SAMPLE_FILE) -> dict[str, Any]:
    if not path.is_file():
        raise GoldenError(f"{path} does not exist: run `aml golden-sample` first")
    document: dict[str, Any] = json.loads(path.read_text())
    return document


def load_sample(path: Path = SAMPLE_FILE) -> list[UUID]:
    """The alert ids in labelling order. Strata stay in the file; the screen never needs them."""
    return [UUID(a["alert_id"]) for a in load_sample_document(path)["alerts"]]


# ------------------------------------------------------------------------------ labels


@dataclass(frozen=True)
class GoldenLabel:
    alert_id: UUID
    decision: str
    typology: str | None
    key_transaction_ids: list[int]
    note: str
    seconds: float
    labeller: str
    labelled_at: str  # wall clock, ISO 8601 UTC
    version: str = VERSION
    revises: bool = field(default=False)

    def to_json(self) -> str:
        return json.dumps({**asdict(self), "alert_id": str(self.alert_id)}, sort_keys=True)


def validate(
    decision: str, typology: str | None, key_ids: Sequence[int], note: str, visible: set[int]
) -> list[str]:
    """Every rule a label breaks; empty means it can be saved."""
    problems = []
    if decision not in DECISIONS:
        problems.append(f"decision must be one of {', '.join(DECISIONS)}")
    if decision == "ESCALATE" and typology not in TYPOLOGIES:
        problems.append(f"an ESCALATE needs a typology: one of {', '.join(TYPOLOGIES)}")
    if decision == "CLOSE" and typology is not None:
        problems.append("a CLOSE has no typology")
    low, high = KEY_TRANSACTIONS
    if len(set(key_ids)) != len(key_ids):
        problems.append("key transactions are listed twice")
    if not low <= len(set(key_ids)) <= high:
        problems.append(f"give {low} to {high} key transactions")
    if unknown := sorted(set(key_ids) - visible):
        problems.append(f"not among this alert's visible transactions: {unknown}")
    if not note.strip():
        problems.append("write a short note")
    elif len(note) > NOTE_MAX:
        problems.append(f"keep the note under {NOTE_MAX} characters")
    return problems


def append(label: GoldenLabel, path: Path = LABELS_FILE) -> None:
    """One line, flushed and synced before returning: a crash loses at most the open alert."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(label.to_json() + "\n")
        f.flush()
        os.fsync(f.fileno())


def load_labels(path: Path = LABELS_FILE) -> dict[UUID, GoldenLabel]:
    """The latest label per alert. A torn final line (a crash mid-write) is ignored."""
    if not path.is_file():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    result: dict[UUID, GoldenLabel] = {}
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            if n == len(lines):
                break
            raise GoldenError(f"{path}:{n} is not valid JSON") from exc
        label = GoldenLabel(**{**raw, "alert_id": UUID(raw["alert_id"])})
        result[label.alert_id] = label
    return result
