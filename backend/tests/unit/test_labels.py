import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from aml.evals import labels
from aml.evals.labels import AlertLabel, LabelError
from aml.ingest.rules import load_config

START = datetime(2022, 9, 1, 0, 20, tzinfo=UTC)  # first data row (any time on the first day)
ANALYSIS_END = datetime(2022, 9, 11, tzinfo=UTC)  # 0023
PERIOD = labels.split_period(START, ANALYSIS_END)


def alert(n: int, label: bool, split: str) -> AlertLabel:
    return AlertLabel(UUID(int=n), label, "FAN_IN" if label else None, split, False)


# ------------------------------------------------------------------------- the label


@pytest.mark.parametrize(
    ("patterns", "expected"),
    [
        ([], (False, None, False)),
        (["FAN_IN", "FAN_IN", "CYCLE"], (True, "FAN_IN", False)),
        (["STACK", "CYCLE"], (True, "CYCLE", False)),  # tie: alphabetical
        (["UNLISTED", "UNLISTED"], (True, "UNLISTED", False)),
        (["UNLISTED", "UNLISTED", "UNLISTED", "FAN_OUT"], (True, "FAN_OUT", False)),  # listed wins
        (["CYCLE", "CYCLE"], (True, "CYCLE", True)),  # all CYCLE: held out
        (["CYCLE", "UNLISTED"], (True, "CYCLE", False)),  # not all CYCLE
    ],
)
def test_label_from_window_patterns(patterns: list[str], expected: tuple[object, ...]) -> None:
    result = labels.label_from(patterns)

    assert (result.label, result.typology_label, result.heldout_cycle) == expected


# ------------------------------------------------------------------------- the split


def test_the_first_60_percent_of_normal_days_are_dev() -> None:
    assert PERIOD.start == datetime(2022, 9, 1, tzinfo=UTC)
    assert PERIOD.days == 10
    assert PERIOD.dev_end == datetime(2022, 9, 7, tzinfo=UTC)  # floor(0.6 x 10) = 6 days


@pytest.mark.parametrize(
    ("triggered_at", "split"),
    [
        (datetime(2022, 9, 1, tzinfo=UTC), "dev"),
        (datetime(2022, 9, 6, 23, 59, tzinfo=UTC), "dev"),
        (datetime(2022, 9, 7, tzinfo=UTC), "test"),
        (datetime(2022, 9, 10, 23, 59, tzinfo=UTC), "test"),
    ],
)
def test_split_boundaries(triggered_at: datetime, split: str) -> None:
    assert labels.split_of(triggered_at, PERIOD) == split


@pytest.mark.parametrize(
    "outside", [ANALYSIS_END, ANALYSIS_END + timedelta(days=3), datetime(2022, 8, 31, tzinfo=UTC)]
)
def test_alerts_outside_the_normal_period_are_an_error(outside: datetime) -> None:
    with pytest.raises(LabelError, match="outside"):
        labels.split_of(outside, PERIOD)


def test_analysis_end_must_be_a_midnight() -> None:
    with pytest.raises(LabelError, match="whole days"):
        labels.split_period(START, ANALYSIS_END + timedelta(hours=5))


def test_the_rules_dev_period_is_the_frozen_split() -> None:
    dev = load_config().dev_period

    assert (dev.start, dev.end) == (PERIOD.start, PERIOD.dev_end)
    if labels.SPLITS_FILE.is_file():  # once frozen, the file must agree too
        frozen = json.loads(labels.SPLITS_FILE.read_text())["period"]
        assert frozen["dev_end"] == PERIOD.dev_end.isoformat()


# ---------------------------------------------------------------------- the freeze


def test_the_hash_ignores_order_but_not_any_label_or_split() -> None:
    rows = [alert(1, True, "dev"), alert(2, False, "dev"), alert(3, False, "test")]
    baseline = labels.fingerprint(rows)

    assert labels.fingerprint(list(reversed(rows))) == baseline
    flipped = [alert(1, False, "dev"), *rows[1:]]
    moved = [rows[0], alert(2, False, "test"), rows[2]]
    assert labels.fingerprint(flipped) != baseline
    assert labels.fingerprint(moved) != baseline
    assert labels.fingerprint(rows[:2]) != baseline


def test_summary_counts_and_rates_per_split() -> None:
    rows = [alert(1, True, "dev"), alert(2, False, "dev"), alert(3, False, "test")]

    result = labels.summary(rows, PERIOD)

    assert result["splits"]["dev"] == {
        "alerts": 2, "positives": 1, "positive_rate": 0.5, "heldout_cycle": 0,
    }  # fmt: skip
    assert result["splits"]["test"]["positive_rate"] == 0.0
    assert result["sha256"] == labels.fingerprint(rows)
    assert result["label_window_hours"] == 72
