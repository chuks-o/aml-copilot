from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.outcome import Outcome
from typing import Literal, cast


T = TypeVar("T", bound="OverrideDecision")


@_attrs_define
class OverrideDecision:
    """
    Attributes:
        action (Literal['OVERRIDE']):
        outcome (Outcome): What should happen to the case.
        reason (str): Required, for the audit trail. Example: Counterparties are payroll accounts of the same employer;
            pattern is benign..
        analyst_id (str): Who decided. Supplied by the caller until authentication exists. Example: analyst-07.
    """

    action: Literal["OVERRIDE"]
    outcome: Outcome
    reason: str
    analyst_id: str

    def to_dict(self) -> dict[str, Any]:
        action = self.action

        outcome = self.outcome.value

        reason = self.reason

        analyst_id = self.analyst_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
                "outcome": outcome,
                "reason": reason,
                "analyst_id": analyst_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = cast(Literal["OVERRIDE"], d.pop("action"))
        if action != "OVERRIDE":
            raise ValueError(f"action must match const 'OVERRIDE', got '{action}'")

        outcome = Outcome(d.pop("outcome"))

        reason = d.pop("reason")

        analyst_id = d.pop("analyst_id")

        override_decision = cls(
            action=action,
            outcome=outcome,
            reason=reason,
            analyst_id=analyst_id,
        )

        return override_decision
