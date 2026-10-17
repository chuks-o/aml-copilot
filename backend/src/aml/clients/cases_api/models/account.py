from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.entity_type import EntityType
from typing import cast

if TYPE_CHECKING:
    from ..models.activity_summary import ActivitySummary


T = TypeVar("T", bound="Account")


@_attrs_define
class Account:
    """
    Attributes:
        id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
            upper-case hex.
             Example: 10:8000EBD30.
        bank_id (str):  Example: 10.
        bank_name (str):  Example: Canada Bank #27.
        account_number (str):  Example: 8000EBD30.
        entity_id (str): The account holder. One entity can hold accounts at several banks. Example: 800C998A0.
        entity_name (str):  Example: Corporation #33520.
        entity_type (EntityType): Parsed from the dataset's entity name ("Corporation #33520"). `COUNTRY` and `DIRECT`
            are labels the data generator uses without documenting them; they are passed through.
        activity (ActivitySummary):
    """

    id: str
    bank_id: str
    bank_name: str
    account_number: str
    entity_id: str
    entity_name: str
    entity_type: EntityType
    activity: ActivitySummary
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.activity_summary import ActivitySummary  # noqa: PLC0415

        id = self.id

        bank_id = self.bank_id

        bank_name = self.bank_name

        account_number = self.account_number

        entity_id = self.entity_id

        entity_name = self.entity_name

        entity_type = self.entity_type.value

        activity = self.activity.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "bank_id": bank_id,
                "bank_name": bank_name,
                "account_number": account_number,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "entity_type": entity_type,
                "activity": activity,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.activity_summary import ActivitySummary  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        bank_id = d.pop("bank_id")

        bank_name = d.pop("bank_name")

        account_number = d.pop("account_number")

        entity_id = d.pop("entity_id")

        entity_name = d.pop("entity_name")

        entity_type = EntityType(d.pop("entity_type"))

        activity = ActivitySummary.from_dict(d.pop("activity"))

        account = cls(
            id=id,
            bank_id=bank_id,
            bank_name=bank_name,
            account_number=account_number,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            activity=activity,
        )

        account.additional_properties = d
        return account

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
