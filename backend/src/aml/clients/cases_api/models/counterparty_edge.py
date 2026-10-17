from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.counterparty_edge_direction import CounterpartyEdgeDirection
from typing import cast
import datetime

if TYPE_CHECKING:
    from ..models.money import Money


T = TypeVar("T", bound="CounterpartyEdge")


@_attrs_define
class CounterpartyEdge:
    """
    Attributes:
        counterparty_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
            upper-case hex.
             Example: 10:8000EBD30.
        direction (CounterpartyEdgeDirection):
        transaction_count (int):
        total (Money):
        first_ts (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
        last_ts (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
    """

    counterparty_id: str
    direction: CounterpartyEdgeDirection
    transaction_count: int
    total: Money
    first_ts: datetime.datetime
    last_ts: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.money import Money  # noqa: PLC0415

        counterparty_id = self.counterparty_id

        direction = self.direction.value

        transaction_count = self.transaction_count

        total = self.total.to_dict()

        first_ts = self.first_ts.isoformat()

        last_ts = self.last_ts.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "counterparty_id": counterparty_id,
                "direction": direction,
                "transaction_count": transaction_count,
                "total": total,
                "first_ts": first_ts,
                "last_ts": last_ts,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.money import Money  # noqa: PLC0415

        d = dict(src_dict)
        counterparty_id = d.pop("counterparty_id")

        direction = CounterpartyEdgeDirection(d.pop("direction"))

        transaction_count = d.pop("transaction_count")

        total = Money.from_dict(d.pop("total"))

        first_ts = datetime.datetime.fromisoformat(d.pop("first_ts"))

        last_ts = datetime.datetime.fromisoformat(d.pop("last_ts"))

        counterparty_edge = cls(
            counterparty_id=counterparty_id,
            direction=direction,
            transaction_count=transaction_count,
            total=total,
            first_ts=first_ts,
            last_ts=last_ts,
        )

        counterparty_edge.additional_properties = d
        return counterparty_edge

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
