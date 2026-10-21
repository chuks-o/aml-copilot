"""Monitoring rules: positive, negative and boundary cases per rule, and scan semantics."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from aml.ingest import rules
from aml.ingest.rules import Tx

T0 = datetime(2022, 9, 1, tzinfo=UTC)
CONFIG = rules.RulesConfig.model_validate(
    {
        "fan_in": {"window_hours": 24, "min_counterparties": 5},
        "fan_out": {"window_hours": 24, "min_counterparties": 5},
        "pass_through": {"window_hours": 2, "tolerance": 0.05},
        "structuring": {
            "window_hours": 48,
            "min_count": 3,
            "band": 0.10,
            "thresholds": {"USD": 10000},
        },
        "new_counterparty_burst": {"window_hours": 6, "min_new": 5},
    }
)


def tx(
    minutes: float,
    counterparty: str,
    direction: rules.Direction = "IN",
    amount: str = "100",
    currency: str = "USD",
    tx_id: int | None = None,
) -> Tx:
    return Tx(
        ts=T0 + timedelta(minutes=minutes),
        id=tx_id if tx_id is not None else int(minutes * 10) + 1,
        counterparty=counterparty,
        direction=direction,
        amount=Decimal(amount),
        currency=currency,
    )


def senders(count: int, every_minutes: float = 60, direction: rules.Direction = "IN") -> list[Tx]:
    return [tx(n * every_minutes, f"10:{n:08X}", direction) for n in range(count)]


# ------------------------------------------------------------------- fan in / fan out


@pytest.mark.parametrize(("rule", "direction"), [(rules.fan_in, "IN"), (rules.fan_out, "OUT")])
def test_fan_fires_at_n_distinct_counterparties(rule: object, direction: rules.Direction) -> None:
    window = senders(5, direction=direction)
    hit = rule(window, CONFIG.fan_in)  # type: ignore[operator]

    assert hit is not None
    assert (hit.observed, hit.threshold, hit.score) == (5, 5, 0.5)
    assert hit.typology == ("FAN_IN" if direction == "IN" else "FAN_OUT")
    assert len(hit.cited) == 5


@pytest.mark.parametrize(("rule", "direction"), [(rules.fan_in, "IN"), (rules.fan_out, "OUT")])
def test_fan_boundary_one_short_does_not_fire(rule: object, direction: rules.Direction) -> None:
    assert rule(senders(4, direction=direction), CONFIG.fan_in) is None  # type: ignore[operator]


def test_fan_in_counts_distinct_senders_not_payments() -> None:
    repeated = [tx(n, "10:00000001") for n in range(10)] + senders(3)

    assert rules.fan_in(repeated, CONFIG.fan_in) is None  # 4 distinct senders


def test_fan_in_ignores_outgoing_payments() -> None:
    assert rules.fan_in(senders(6, direction="OUT"), CONFIG.fan_in) is None


def test_fan_in_scan_respects_the_24h_window() -> None:
    spread = senders(5, every_minutes=6 * 60 + 1)  # 5 senders over 24 h 4 min: never 5 in 24 h
    inside = senders(5, every_minutes=6 * 60 - 1)  # 5 senders over 23 h 56 min

    assert rules.scan("fan_in", CONFIG, spread, spread, since=None) == []
    assert len(rules.scan("fan_in", CONFIG, inside, inside, since=None)) == 1


# --------------------------------------------------------------------- pass-through


def test_pass_through_matches_in_then_out_within_tolerance() -> None:
    window = [tx(0, "10:A", "IN", "1000"), tx(90, "20:B", "OUT", "960")]

    hit = rules.pass_through(window, CONFIG.pass_through)

    assert hit is not None
    assert hit.cited == (window[0].id, window[1].id)
    assert hit.observed == pytest.approx(0.04)


@pytest.mark.parametrize(
    ("amount_out", "fires"),
    [("1050", True), ("950", True), ("1050.01", False), ("949.99", False)],
)
def test_pass_through_boundary_is_exactly_5_percent(amount_out: str, fires: bool) -> None:
    window = [tx(0, "10:A", "IN", "1000"), tx(30, "20:B", "OUT", amount_out)]

    assert (rules.pass_through(window, CONFIG.pass_through) is not None) is fires


def test_pass_through_needs_the_same_currency_and_out_after_in() -> None:
    other_currency = [tx(0, "10:A", "IN", "1000", "EUR"), tx(30, "20:B", "OUT", "1000", "USD")]
    out_first = [tx(0, "20:B", "OUT", "1000"), tx(30, "10:A", "IN", "1000")]

    assert rules.pass_through(other_currency, CONFIG.pass_through) is None
    assert rules.pass_through(out_first, CONFIG.pass_through) is None


def test_pass_through_scan_needs_out_within_2h() -> None:
    late = [tx(0, "10:A", "IN", "1000"), tx(121, "20:B", "OUT", "1000")]
    on_time = [tx(0, "10:A", "IN", "1000"), tx(119, "20:B", "OUT", "1000")]

    assert rules.scan("pass_through", CONFIG, late, late, since=None) == []
    assert len(rules.scan("pass_through", CONFIG, on_time, on_time, since=None)) == 1


# ---------------------------------------------------------------------- structuring


def test_structuring_fires_on_three_amounts_just_below_the_threshold() -> None:
    window = [
        tx(n * 60, f"20:{n}", "OUT", amount) for n, amount in enumerate(["9500", "9900", "9001"])
    ]

    hit = rules.structuring(window, CONFIG.structuring)

    assert hit is not None
    assert hit.observed == 3


@pytest.mark.parametrize(
    ("amounts", "fires"),
    [
        (["9000", "9000", "9000"], True),  # exactly 10% below: inside the band
        (["8999.99", "9500", "9500"], False),  # one just outside the band
        (["10000", "9500", "9500"], False),  # at the threshold is not below it
        (["9500", "9500"], False),  # only two
    ],
)
def test_structuring_boundaries(amounts: list[str], fires: bool) -> None:
    window = [tx(n * 60, f"20:{n}", "OUT", a) for n, a in enumerate(amounts)]

    assert (rules.structuring(window, CONFIG.structuring) is not None) is fires


def test_structuring_only_checks_currencies_with_a_threshold() -> None:
    window = [tx(n * 60, f"20:{n}", "OUT", "9500", "JPY") for n in range(3)]

    assert rules.structuring(window, CONFIG.structuring) is None


# ----------------------------------------------------------- new-counterparty burst


def test_burst_fires_on_five_never_seen_counterparties() -> None:
    window = senders(5, every_minutes=30)

    hit = rules.new_counterparty_burst(window, CONFIG.new_counterparty_burst, frozenset())

    assert hit is not None
    assert hit.observed == 5


def test_burst_ignores_counterparties_seen_before_the_window() -> None:
    window = senders(5, every_minutes=30)
    known = frozenset({window[0].counterparty})

    assert rules.new_counterparty_burst(window, CONFIG.new_counterparty_burst, known) is None


def test_burst_scan_uses_the_whole_earlier_history() -> None:
    old = [tx(-3 * 24 * 60, "10:00000000")]  # three days before: outside the 6 h window
    burst = senders(5, every_minutes=30)

    assert rules.scan("new_counterparty_burst", CONFIG, old + burst, burst, since=None) == []
    fresh = senders(6, every_minutes=30)
    assert len(rules.scan("new_counterparty_burst", CONFIG, old + fresh, fresh, since=None)) == 1


# ---------------------------------------------------------------------------- scan


def test_one_episode_makes_one_alert() -> None:
    episode = senders(12, every_minutes=30)  # 12 senders within 6 h: the condition holds 8 times

    hits = rules.scan("fan_in", CONFIG, episode, episode, since=None)

    assert len(hits) == 2  # at the 5th sender, then again only after 5 more fresh ones
    assert hits[0].trigger == episode[4]
    assert hits[1].trigger == episode[9]
    assert hits[1].window_start == episode[4].ts  # nothing at or before the last trigger counts


def test_hits_do_not_depend_on_how_transactions_were_batched() -> None:
    txs = senders(30, every_minutes=50)
    all_at_once = rules.scan("fan_in", CONFIG, txs, txs, since=None)

    batched, since = [], None
    for end in range(7, len(txs) + 7, 7):
        new = rules.scan("fan_in", CONFIG, txs[:end], txs[end - 7 : end], since)
        batched += new
        since = new[-1].trigger.ts if new else since

    assert batched == all_at_once


def test_the_window_starts_24h_before_the_trigger_unless_an_alert_came_since() -> None:
    episode = senders(5)

    (hit,) = rules.scan("fan_in", CONFIG, episode, episode, since=None)

    assert hit.window_start == episode[-1].ts - timedelta(hours=24)
