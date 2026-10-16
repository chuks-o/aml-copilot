from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.direction import Direction
from ..models.payment_format import PaymentFormat
from typing import cast
import datetime

if TYPE_CHECKING:
    from ..models.money import Money


T = TypeVar("T", bound="Transaction")


@_attrs_define
class Transaction:
    """One payment. `amount_paid` leaves the payer; `amount_received` reaches the payee. They
    differ when the currencies differ. The dataset's laundering label is deliberately not
    exposed: it is ground truth for evaluation, not evidence.

        Attributes:
            id (int):  Example: 1048576.
            ts (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
            from_account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
                upper-case hex.
                 Example: 10:8000EBD30.
            to_account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
                upper-case hex.
                 Example: 10:8000EBD30.
            direction (Direction): Relative to the account in the path. `SELF` is a transfer to itself.
            amount_paid (Money):
            amount_received (Money):
            payment_format (PaymentFormat):
    """

    id: int
    ts: datetime.datetime
    from_account_id: str
    to_account_id: str
    direction: Direction
    amount_paid: Money
    amount_received: Money
    payment_format: PaymentFormat
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.money import Money  # noqa: PLC0415

        id = self.id

        ts = self.ts.isoformat()

        from_account_id = self.from_account_id

        to_account_id = self.to_account_id

        direction = self.direction.value

        amount_paid = self.amount_paid.to_dict()

        amount_received = self.amount_received.to_dict()

        payment_format = self.payment_format.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "ts": ts,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "direction": direction,
                "amount_paid": amount_paid,
                "amount_received": amount_received,
                "payment_format": payment_format,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.money import Money  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        ts = datetime.datetime.fromisoformat(d.pop("ts"))

        from_account_id = d.pop("from_account_id")

        to_account_id = d.pop("to_account_id")

        direction = Direction(d.pop("direction"))

        amount_paid = Money.from_dict(d.pop("amount_paid"))

        amount_received = Money.from_dict(d.pop("amount_received"))

        payment_format = PaymentFormat(d.pop("payment_format"))

        transaction = cls(
            id=id,
            ts=ts,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            direction=direction,
            amount_paid=amount_paid,
            amount_received=amount_received,
            payment_format=payment_format,
        )

        transaction.additional_properties = d
        return transaction

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
