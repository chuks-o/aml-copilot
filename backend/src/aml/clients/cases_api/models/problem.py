from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset


T = TypeVar("T", bound="Problem")


@_attrs_define
class Problem:
    """RFC 9457 problem details.

    Attributes:
        type_ (str): Identifies the problem type. `about:blank` when only `status` matters. Default: 'about:blank'.
            Example: https://aml-copilot.local/problems/invalid-transition.
        title (str): Short, human-readable summary of the problem type. Example: Invalid status transition.
        status (int):  Example: 409.
        detail (str | Unset): Explanation specific to this occurrence. Example: Case is CLOSED; CLOSED is final..
        instance (str | Unset): The request path that produced the problem. Example:
            /cases/0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b/status.
    """

    title: str
    status: int
    type_: str = "about:blank"
    detail: str | Unset = UNSET
    instance: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_

        title = self.title

        status = self.status

        detail = self.detail

        instance = self.instance

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "title": title,
                "status": status,
            }
        )
        if detail is not UNSET:
            field_dict["detail"] = detail
        if instance is not UNSET:
            field_dict["instance"] = instance

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = d.pop("type")

        title = d.pop("title")

        status = d.pop("status")

        detail = d.pop("detail", UNSET)

        instance = d.pop("instance", UNSET)

        problem = cls(
            type_=type_,
            title=title,
            status=status,
            detail=detail,
            instance=instance,
        )

        problem.additional_properties = d
        return problem

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
