from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast
from uuid import UUID


T = TypeVar("T", bound="CaseCreate")


@_attrs_define
class CaseCreate:
    """
    Attributes:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
            upper-case hex.
             Example: 10:8000EBD30.
        alert_ids (list[UUID]):
    """

    account_id: str
    alert_ids: list[UUID]

    def to_dict(self) -> dict[str, Any]:
        account_id = self.account_id

        alert_ids = []
        for alert_ids_item_data in self.alert_ids:
            alert_ids_item = str(alert_ids_item_data)
            alert_ids.append(alert_ids_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "account_id": account_id,
                "alert_ids": alert_ids,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        account_id = d.pop("account_id")

        alert_ids = []
        _alert_ids = d.pop("alert_ids")
        for alert_ids_item_data in _alert_ids:
            alert_ids_item = UUID(alert_ids_item_data)

            alert_ids.append(alert_ids_item)

        case_create = cls(
            account_id=account_id,
            alert_ids=alert_ids,
        )

        return case_create
