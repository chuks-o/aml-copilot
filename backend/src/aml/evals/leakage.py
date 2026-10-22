"""Guard against time leakage: no feature or prompt input may encode the date or the day's
position in the period.

Laundering keeps going after normal activity stops, and its share rises across HI-Small's
days (0023). A feature like "day 9 of 10" would therefore look predictive for a reason that
won't exist in production. Every builder of model features or prompt inputs is registered
in ``INPUTS``; ``tests/unit/test_leakage.py`` runs each on sample data and fails if
``find_time_leaks`` finds anything. Rationale: docs/decisions/0029-labels-and-time-split.md.
"""

import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from aml.ingest import monitor, rules

# Keys that name a time or a position in time, as whole words: "ts", "day_of_period", ...
_TIME_KEY = re.compile(
    r"(^|_)(dates?|days?|ts|times?|timestamps?|datetime|weekdays?|hours?|minutes?|weeks?|"
    r"months?|years?|period|position|elapsed|age|since)(_|$)",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b")


def find_time_leaks(value: Any, path: str = "$") -> list[str]:
    """Paths in ``value`` (nested dicts, lists, models) that look like a date or time."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    elif hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump()
    leaks: list[str] = []
    if isinstance(value, datetime | date | timedelta):
        leaks.append(f"{path}: {type(value).__name__} value")
    elif isinstance(value, str) and _ISO_DATE.search(value):
        leaks.append(f"{path}: date-like text {value!r}")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if _TIME_KEY.search(str(key)):
                leaks.append(f"{path}.{key}: time-named key")
            leaks += find_time_leaks(item, f"{path}.{key}")
    elif isinstance(value, list | tuple | set | frozenset):
        for n, item in enumerate(value):
            leaks += find_time_leaks(item, f"{path}[{n}]")
    return leaks


# ------------------------------------------------------------------------------ registry
#
# name -> a function returning a representative built input. Add every feature builder
# (scoring) and prompt-input builder (investigator) here as it is written.

_T0 = datetime(2022, 9, 2, 9, 0, tzinfo=UTC)


def _sample_hits() -> list[rules.Hit]:
    config = rules.load_config().rules
    inflow = [
        rules.Tx(_T0 + timedelta(minutes=10 * n), n + 1, f"20:{n:08X}", "IN", Decimal("250"), "USD")
        for n in range(6)
    ]
    passing = [
        rules.Tx(_T0, 100, "30:00000001", "IN", Decimal("1000"), "USD"),
        rules.Tx(_T0 + timedelta(hours=1), 101, "30:00000002", "OUT", Decimal("980"), "USD"),
    ]
    hits = rules.scan("fan_in", config, inflow, inflow, since=None)
    hits += rules.scan("new_counterparty_burst", config, inflow, inflow, since=None)
    hits += rules.scan("pass_through", config, passing, passing, since=None)
    return hits


def _alert_payloads() -> list[Any]:
    return [monitor.alert_body("10:8000000A1", hit, "rules-v1") for hit in _sample_hits()]


INPUTS: dict[str, Callable[[], Any]] = {
    # Rule alerts: their reason, score and typology become the investigator's first evidence.
    "rule alert payloads (POST /alerts)": _alert_payloads,
}
