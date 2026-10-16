from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar("T", bound="Money")


@_attrs_define
class Money:
    """
    Attributes:
        amount (str): Non-negative decimal, at most 8 fractional digits. Never a JSON number. Example: 3697.34.
        currency (str): ISO 4217 code, or `BTC` for Bitcoin. Example: USD.
    """

    amount: str
    currency: str

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        currency = self.currency

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "amount": amount,
                "currency": currency,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        amount = d.pop("amount")

        currency = d.pop("currency")

        money = cls(
            amount=amount,
            currency=currency,
        )

        return money
