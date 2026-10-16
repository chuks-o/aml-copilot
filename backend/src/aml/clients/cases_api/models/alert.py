from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.alert_status import AlertStatus
from ..models.typology import Typology
from typing import cast
from uuid import UUID
import datetime


T = TypeVar("T", bound="Alert")


@_attrs_define
class Alert:
    """
    Attributes:
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
            upper-case hex.
             Example: 10:8000EBD30.
        score (float): Model score; higher is more suspicious. Example: 0.93.
        reason (str): Why the model raised the alert, in a sentence. Example: Received from 14 accounts within 6 hours,
            then sent out within 2 hours..
        transaction_ids (list[int]): The transactions that triggered the alert.
        model_version (str):  Example: gbm-2026-10-01.
        typology (None | Typology): The model's guess at the pattern, if it makes one.
        id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        status (AlertStatus): `OPEN` until grouped into a case (`IN_CASE`) or dismissed (`DISMISSED`).
        case_id (None | UUID): The case this alert belongs to, once `IN_CASE`.
        created_at (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
    """

    account_id: str
    score: float
    reason: str
    transaction_ids: list[int]
    model_version: str
    typology: None | Typology
    id: UUID
    status: AlertStatus
    case_id: None | UUID
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        account_id = self.account_id

        score = self.score

        reason = self.reason

        transaction_ids = self.transaction_ids

        model_version = self.model_version

        typology: None | str
        if isinstance(self.typology, Typology):
            typology = self.typology.value
        else:
            typology = self.typology

        id = str(self.id)

        status = self.status.value

        case_id: None | str
        if isinstance(self.case_id, UUID):
            case_id = str(self.case_id)
        else:
            case_id = self.case_id

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "account_id": account_id,
                "score": score,
                "reason": reason,
                "transaction_ids": transaction_ids,
                "model_version": model_version,
                "typology": typology,
                "id": id,
                "status": status,
                "case_id": case_id,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        account_id = d.pop("account_id")

        score = d.pop("score")

        reason = d.pop("reason")

        transaction_ids = cast(list[int], d.pop("transaction_ids"))

        model_version = d.pop("model_version")

        def _parse_typology(data: object) -> None | Typology:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                typology_type_0 = Typology(data)

                return typology_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Typology, data)

        typology = _parse_typology(d.pop("typology"))

        id = UUID(d.pop("id"))

        status = AlertStatus(d.pop("status"))

        def _parse_case_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                case_id_type_0 = UUID(data)

                return case_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        case_id = _parse_case_id(d.pop("case_id"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        alert = cls(
            account_id=account_id,
            score=score,
            reason=reason,
            transaction_ids=transaction_ids,
            model_version=model_version,
            typology=typology,
            id=id,
            status=status,
            case_id=case_id,
            created_at=created_at,
        )

        alert.additional_properties = d
        return alert

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
