"""Monitoring rules: pure functions over one account's transactions.

Each rule looks at a *trailing* window, the transactions in ``(trigger.ts - window,
trigger.ts]`` ending at a trigger transaction, and returns a ``Hit`` or None. ``scan`` walks
an account's new transactions in ``(ts, id)`` order and fires a rule at the first trigger
where it holds. After that, only transactions after the trigger count towards the next alert
(one episode, one alert). The windows only look backwards, so the same data gives the same
hits however it was batched: live replay and offline tuning agree.

No database, clock, or I/O here. Rationale: docs/decisions/0028-monitoring-rules.md.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["IN", "OUT"]
MAX_CITED = 500  # POST /alerts accepts at most 500 transaction ids


@dataclass(frozen=True, order=True)
class Tx:
    """One transaction from the monitored account's side (self-transfers excluded)."""

    ts: datetime
    id: int
    counterparty: str
    direction: Direction
    amount: Decimal  # what this account paid (OUT) or received (IN)
    currency: str


@dataclass(frozen=True)
class Hit:
    rule_id: str
    trigger: Tx
    window_start: datetime  # exclusive lower bound of the trailing window
    cited: tuple[int, ...]  # transaction ids, oldest first
    observed: float  # the measured quantity (counterparties, matches, ...)
    threshold: float  # what it had to reach
    score: float  # severity in [0, 1], for queue ordering only
    reason: str
    typology: str | None


# ---------------------------------------------------------------------- configuration


class _Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_hours: float = Field(gt=0)

    @property
    def window(self) -> timedelta:
        return timedelta(hours=self.window_hours)


class FanConfig(_Rule):
    min_counterparties: int = Field(ge=1)


class PassThroughConfig(_Rule):
    tolerance: float = Field(ge=0, lt=1)  # |out - in| ≤ tolerance * in


class StructuringConfig(_Rule):
    min_count: int = Field(ge=1)
    band: float = Field(gt=0, lt=1)  # amounts in [(1 - band) * threshold, threshold)
    thresholds: dict[str, Decimal]  # per currency; other currencies aren't checked


class BurstConfig(_Rule):
    min_new: int = Field(ge=1)


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fan_in: FanConfig
    fan_out: FanConfig
    pass_through: PassThroughConfig
    structuring: StructuringConfig
    new_counterparty_burst: BurstConfig


class Period(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: datetime
    end: datetime  # exclusive


class MonitorConfig(BaseModel):
    """The whole rules.yaml."""

    model_config = ConfigDict(extra="forbid")
    version: str
    dev_period: Period
    skip_high_volume: bool
    rules: RulesConfig


DEFAULT_CONFIG = Path(__file__).with_name("rules.yaml")


def load_config(path: Path | None = None) -> MonitorConfig:
    """rules.yaml (shipped with the package), or another file in the same shape."""
    data = yaml.safe_load((path or DEFAULT_CONFIG).read_text())
    return MonitorConfig.model_validate(data)


# ------------------------------------------------------------------------------ rules


def _severity(observed: float, threshold: float) -> float:
    """0.5 at the threshold, 1.0 at twice it."""
    return round(min(1.0, observed / (2 * threshold)), 4)


def _cite(txs: Sequence[Tx]) -> tuple[int, ...]:
    return tuple(t.id for t in sorted(txs)[-MAX_CITED:])


def _fan(window: Sequence[Tx], cfg: FanConfig, direction: Direction, rule_id: str) -> Hit | None:
    side = [t for t in window if t.direction == direction]
    counterparties = {t.counterparty for t in side}
    if not side or len(counterparties) < cfg.min_counterparties:
        return None
    verb = "Received from" if direction == "IN" else "Sent to"
    noun = "senders" if direction == "IN" else "receivers"
    return Hit(
        rule_id=rule_id,
        trigger=window[-1],
        window_start=window[-1].ts - cfg.window,
        cited=_cite(side),
        observed=len(counterparties),
        threshold=cfg.min_counterparties,
        score=_severity(len(counterparties), cfg.min_counterparties),
        reason=f"{verb} {len(counterparties)} distinct {noun} within {cfg.window_hours:g} h.",
        typology="FAN_IN" if direction == "IN" else "FAN_OUT",
    )


def fan_in(window: Sequence[Tx], cfg: FanConfig) -> Hit | None:
    """Distinct senders ≥ N within the window."""
    return _fan(window, cfg, "IN", "fan_in")


def fan_out(window: Sequence[Tx], cfg: FanConfig) -> Hit | None:
    """Distinct receivers ≥ N within the window."""
    return _fan(window, cfg, "OUT", "fan_out")


def pass_through(window: Sequence[Tx], cfg: PassThroughConfig) -> Hit | None:
    """Money in, then out within the window at nearly the same amount (same currency).

    The trigger must be the outgoing leg; it is matched with the most recent incoming one
    within tolerance.
    """
    out = window[-1]
    if out.direction != "OUT":
        return None
    for incoming in reversed(window[:-1]):
        if incoming.direction != "IN" or incoming.currency != out.currency or incoming.amount <= 0:
            continue
        difference = abs(out.amount - incoming.amount) / incoming.amount
        if difference <= Decimal(str(cfg.tolerance)):
            minutes = (out.ts - incoming.ts).total_seconds() / 60
            return Hit(
                rule_id="pass_through",
                trigger=out,
                window_start=out.ts - cfg.window,
                cited=(incoming.id, out.id),
                observed=float(difference),
                threshold=cfg.tolerance,
                score=round(0.5 + 0.5 * (1 - float(difference) / cfg.tolerance), 4)
                if cfg.tolerance
                else 1.0,
                reason=(
                    f"Received {incoming.amount} {incoming.currency} and sent {out.amount} "
                    f"{out.currency} {minutes:.0f} min later ({float(difference):.1%} apart)."
                ),
                typology=None,
            )
    return None


def structuring(window: Sequence[Tx], cfg: StructuringConfig) -> Hit | None:
    """At least ``min_count`` amounts just below a reporting threshold, in one currency."""
    for currency, limit in cfg.thresholds.items():
        floor = limit * (1 - Decimal(str(cfg.band)))
        near = [t for t in window if t.currency == currency and floor <= t.amount < limit]
        if len(near) >= cfg.min_count and window[-1] in near:
            return Hit(
                rule_id="structuring",
                trigger=window[-1],
                window_start=window[-1].ts - cfg.window,
                cited=_cite(near),
                observed=len(near),
                threshold=cfg.min_count,
                score=_severity(len(near), cfg.min_count),
                reason=(
                    f"{len(near)} amounts between {floor:.0f} and {limit:.0f} {currency} "
                    f"within {cfg.window_hours:g} h."
                ),
                typology=None,
            )
    return None


def new_counterparty_burst(
    window: Sequence[Tx], cfg: BurstConfig, seen_before: frozenset[str]
) -> Hit | None:
    """At least ``min_new`` counterparties within the window that the account had never
    dealt with before it (``seen_before``: every counterparty from earlier history)."""
    first_seen: dict[str, Tx] = {}
    for t in window:
        if t.counterparty not in seen_before:
            first_seen.setdefault(t.counterparty, t)
    if len(first_seen) < cfg.min_new or window[-1] not in first_seen.values():
        return None
    return Hit(
        rule_id="new_counterparty_burst",
        trigger=window[-1],
        window_start=window[-1].ts - cfg.window,
        cited=_cite(list(first_seen.values())),
        observed=len(first_seen),
        threshold=cfg.min_new,
        score=_severity(len(first_seen), cfg.min_new),
        reason=f"{len(first_seen)} never-seen counterparties within {cfg.window_hours:g} h.",
        typology=None,
    )


# ------------------------------------------------------------------------------- scan

RULE_IDS = ("fan_in", "fan_out", "pass_through", "structuring", "new_counterparty_burst")

# Each rule as (its config, window, seen-before counterparties) -> Hit | None.
_RULES: dict[str, Callable[[RulesConfig, Sequence[Tx], frozenset[str]], Hit | None]] = {
    "fan_in": lambda c, w, _: fan_in(w, c.fan_in),
    "fan_out": lambda c, w, _: fan_out(w, c.fan_out),
    "pass_through": lambda c, w, _: pass_through(w, c.pass_through),
    "structuring": lambda c, w, _: structuring(w, c.structuring),
    "new_counterparty_burst": lambda c, w, seen: new_counterparty_burst(
        w, c.new_counterparty_burst, seen
    ),
}


def scan(
    rule_id: str,
    config: RulesConfig,
    history: Sequence[Tx],
    triggers: Sequence[Tx],
    since: datetime | None,
) -> list[Hit]:
    """Hits for one rule and account, checking each trigger in ``(ts, id)`` order.

    ``history`` is everything the account has done up to the last trigger, including the
    triggers. ``since`` is the previous alert's trigger time (None if never alerted):
    transactions at or before it never count again.
    """
    window_length: timedelta = getattr(config, rule_id).window
    check = _RULES[rule_id]
    hits: list[Hit] = []
    ordered = sorted(history)
    for trigger in sorted(triggers):
        floor = trigger.ts - window_length
        if since is not None and since > floor:
            floor = since
        window = [t for t in ordered if floor < t.ts and t <= trigger]
        if not window or window[-1] != trigger:
            continue
        seen_before = frozenset(t.counterparty for t in ordered if t.ts <= floor)
        hit = check(config, window, seen_before)
        if hit is not None:
            hits.append(replace(hit, window_start=floor))
            since = trigger.ts
    return hits
