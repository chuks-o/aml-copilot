from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.decision_action import DecisionAction
from ..models.outcome import Outcome
from typing import cast
from uuid import UUID
import datetime


T = TypeVar("T", bound="Decision")


@_attrs_define
class Decision:
    """
    Attributes:
        id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        case_id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        action (DecisionAction):
        outcome (Outcome): What should happen to the case.
        reason (str): Required, for the audit trail. Example: Counterparties are payroll accounts of the same employer;
            pattern is benign..
        analyst_id (str): Who decided. Supplied by the caller until authentication exists. Example: analyst-07.
        created_at (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
    """

    id: UUID
    case_id: UUID
    action: DecisionAction
    outcome: Outcome
    reason: str
    analyst_id: str
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        case_id = str(self.case_id)

        action = self.action.value

        outcome = self.outcome.value

        reason = self.reason

        analyst_id = self.analyst_id

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "case_id": case_id,
                "action": action,
                "outcome": outcome,
                "reason": reason,
                "analyst_id": analyst_id,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        case_id = UUID(d.pop("case_id"))

        action = DecisionAction(d.pop("action"))

        outcome = Outcome(d.pop("outcome"))

        reason = d.pop("reason")

        analyst_id = d.pop("analyst_id")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        decision = cls(
            id=id,
            case_id=case_id,
            action=action,
            outcome=outcome,
            reason=reason,
            analyst_id=analyst_id,
            created_at=created_at,
        )

        decision.additional_properties = d
        return decision

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
