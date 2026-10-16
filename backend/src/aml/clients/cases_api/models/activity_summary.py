from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast
import datetime


T = TypeVar("T", bound="ActivitySummary")


@_attrs_define
class ActivitySummary:
    """
    Attributes:
        first_seen (datetime.datetime | None): First transaction, or `null` if the account has none.
        last_seen (datetime.datetime | None):
        sent_count (int):
        received_count (int):
    """

    first_seen: datetime.datetime | None
    last_seen: datetime.datetime | None
    sent_count: int
    received_count: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        first_seen: None | str
        if isinstance(self.first_seen, datetime.datetime):
            first_seen = self.first_seen.isoformat()
        else:
            first_seen = self.first_seen

        last_seen: None | str
        if isinstance(self.last_seen, datetime.datetime):
            last_seen = self.last_seen.isoformat()
        else:
            last_seen = self.last_seen

        sent_count = self.sent_count

        received_count = self.received_count

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "first_seen": first_seen,
                "last_seen": last_seen,
                "sent_count": sent_count,
                "received_count": received_count,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_first_seen(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                first_seen_type_0 = datetime.datetime.fromisoformat(data)

                return first_seen_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        first_seen = _parse_first_seen(d.pop("first_seen"))

        def _parse_last_seen(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_seen_type_0 = datetime.datetime.fromisoformat(data)

                return last_seen_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        last_seen = _parse_last_seen(d.pop("last_seen"))

        sent_count = d.pop("sent_count")

        received_count = d.pop("received_count")

        activity_summary = cls(
            first_seen=first_seen,
            last_seen=last_seen,
            sent_count=sent_count,
            received_count=received_count,
        )

        activity_summary.additional_properties = d
        return activity_summary

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
