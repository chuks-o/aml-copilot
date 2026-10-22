"""No feature or prompt input may encode the date or the day's position in the period (0029)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from aml.evals import leakage


@pytest.mark.parametrize("name", sorted(leakage.INPUTS))
def test_registered_inputs_carry_no_time(name: str) -> None:
    built = leakage.INPUTS[name]()

    assert built, f"{name} built nothing to check"
    assert leakage.find_time_leaks(built) == []


def test_the_registry_is_not_empty() -> None:
    assert leakage.INPUTS


@pytest.mark.parametrize(
    "planted",
    [
        {"score": 0.5, "triggered": datetime(2022, 9, 9, tzinfo=UTC)},
        {"amounts": [1, 2], "first": date(2022, 9, 1)},
        {"reason": "Seen on 2022-09-09 by the rule."},
        {"day_of_period": 9},
        {"features": {"hours_since_start": 200}},
        {"window": timedelta(hours=24)},
        [{"ok": 1}, {"position": 0.9}],
    ],
)
def test_the_guard_catches_planted_time(planted: object) -> None:
    assert leakage.find_time_leaks(planted)


@pytest.mark.parametrize(
    "clean",
    [
        {"account_id": "10:8000EBD30", "score": 0.93, "typology": "FAN_IN"},
        {"reason": "Received from 7 distinct senders within 24 h."},
        {"transaction_ids": [1, 2, 3], "model_version": "rules-v1:fan_in"},
    ],
)
def test_the_guard_passes_clean_inputs(clean: object) -> None:
    assert leakage.find_time_leaks(clean) == []
