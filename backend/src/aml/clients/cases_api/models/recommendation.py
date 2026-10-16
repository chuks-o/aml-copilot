from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.outcome import Outcome
from typing import cast
import datetime


T = TypeVar("T", bound="Recommendation")


@_attrs_define
class Recommendation:
    """The copilot's proposed outcome, set when the investigation finishes.

    Attributes:
        outcome (Outcome): What should happen to the case.
        summary (str):  Example: Funds from 14 unrelated accounts consolidated and forwarded within 8 hours..
        created_at (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
    """

    outcome: Outcome
    summary: str
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        outcome = self.outcome.value

        summary = self.summary

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "outcome": outcome,
                "summary": summary,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        outcome = Outcome(d.pop("outcome"))

        summary = d.pop("summary")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        recommendation = cls(
            outcome=outcome,
            summary=summary,
            created_at=created_at,
        )

        recommendation.additional_properties = d
        return recommendation

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
