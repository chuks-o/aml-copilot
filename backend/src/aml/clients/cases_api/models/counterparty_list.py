from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast
import datetime

if TYPE_CHECKING:
    from ..models.counterparty_edge import CounterpartyEdge


T = TypeVar("T", bound="CounterpartyList")


@_attrs_define
class CounterpartyList:
    """
    Attributes:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
            upper-case hex.
             Example: 10:8000EBD30.
        window_start (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
        window_end (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
        items (list[CounterpartyEdge]):
        total_edges (int): Edges in the window before `limit`; more than `items` means truncated.
    """

    account_id: str
    window_start: datetime.datetime
    window_end: datetime.datetime
    items: list[CounterpartyEdge]
    total_edges: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.counterparty_edge import CounterpartyEdge  # noqa: PLC0415

        account_id = self.account_id

        window_start = self.window_start.isoformat()

        window_end = self.window_end.isoformat()

        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        total_edges = self.total_edges

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "account_id": account_id,
                "window_start": window_start,
                "window_end": window_end,
                "items": items,
                "total_edges": total_edges,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.counterparty_edge import CounterpartyEdge  # noqa: PLC0415

        d = dict(src_dict)
        account_id = d.pop("account_id")

        window_start = datetime.datetime.fromisoformat(d.pop("window_start"))

        window_end = datetime.datetime.fromisoformat(d.pop("window_end"))

        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = CounterpartyEdge.from_dict(items_item_data)

            items.append(items_item)

        total_edges = d.pop("total_edges")

        counterparty_list = cls(
            account_id=account_id,
            window_start=window_start,
            window_end=window_end,
            items=items,
            total_edges=total_edges,
        )

        counterparty_list.additional_properties = d
        return counterparty_list

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
