from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import Literal, cast


T = TypeVar("T", bound="ApproveDecision")


@_attrs_define
class ApproveDecision:
    """
    Attributes:
        action (Literal['APPROVE']):
        reason (str): Required, for the audit trail. Example: Counterparties are payroll accounts of the same employer;
            pattern is benign..
        analyst_id (str): Who decided. Supplied by the caller until authentication exists. Example: analyst-07.
    """

    action: Literal["APPROVE"]
    reason: str
    analyst_id: str

    def to_dict(self) -> dict[str, Any]:
        action = self.action

        reason = self.reason

        analyst_id = self.analyst_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
                "reason": reason,
                "analyst_id": analyst_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = cast(Literal["APPROVE"], d.pop("action"))
        if action != "APPROVE":
            raise ValueError(f"action must match const 'APPROVE', got '{action}'")

        reason = d.pop("reason")

        analyst_id = d.pop("analyst_id")

        approve_decision = cls(
            action=action,
            reason=reason,
            analyst_id=analyst_id,
        )

        return approve_decision
