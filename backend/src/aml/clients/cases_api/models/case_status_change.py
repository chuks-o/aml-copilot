from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.case_status import CaseStatus
from ..types import UNSET, Unset


T = TypeVar("T", bound="CaseStatusChange")


@_attrs_define
class CaseStatusChange:
    """
    Attributes:
        status (CaseStatus): See `PATCH /cases/{case_id}/status` for the allowed transitions.
        reason (str | Unset): Optional note stored with the transition.
    """

    status: CaseStatus
    reason: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        status = self.status.value

        reason = self.reason

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "status": status,
            }
        )
        if reason is not UNSET:
            field_dict["reason"] = reason

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = CaseStatus(d.pop("status"))

        reason = d.pop("reason", UNSET)

        case_status_change = cls(
            status=status,
            reason=reason,
        )

        return case_status_change
