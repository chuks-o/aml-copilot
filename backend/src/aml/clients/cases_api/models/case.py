from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.case_status import CaseStatus
from ..models.typology import Typology
from typing import cast
from uuid import UUID
import datetime

if TYPE_CHECKING:
    from ..models.decision import Decision
    from ..models.recommendation import Recommendation


T = TypeVar("T", bound="Case")


@_attrs_define
class Case:
    """
    Attributes:
        id (UUID):  Example: 0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b.
        version (int): Goes up by one on every change. Sent as `ETag`. Example: 3.
        status (CaseStatus): See `PATCH /cases/{case_id}/status` for the allowed transitions.
        typology (None | Typology): Assigned during the investigation; `null` until then.
        account_id (str): `"<bank>:<account>"`. The bank code has no leading zeros; the account number is
            upper-case hex.
             Example: 10:8000EBD30.
        alert_ids (list[UUID]):
        recommendation (None | Recommendation):
        decision (Decision | None): The analyst's decision, once recorded.
        created_at (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
        updated_at (datetime.datetime):  Example: 2022-09-01T00:20:00Z.
    """

    id: UUID
    version: int
    status: CaseStatus
    typology: None | Typology
    account_id: str
    alert_ids: list[UUID]
    recommendation: None | Recommendation
    decision: Decision | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.decision import Decision  # noqa: PLC0415
        from ..models.recommendation import Recommendation  # noqa: PLC0415

        id = str(self.id)

        version = self.version

        status = self.status.value

        typology: None | str
        if isinstance(self.typology, Typology):
            typology = self.typology.value
        else:
            typology = self.typology

        account_id = self.account_id

        alert_ids = []
        for alert_ids_item_data in self.alert_ids:
            alert_ids_item = str(alert_ids_item_data)
            alert_ids.append(alert_ids_item)

        recommendation: dict[str, Any] | None
        if isinstance(self.recommendation, Recommendation):
            recommendation = self.recommendation.to_dict()
        else:
            recommendation = self.recommendation

        decision: dict[str, Any] | None
        if isinstance(self.decision, Decision):
            decision = self.decision.to_dict()
        else:
            decision = self.decision

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "version": version,
                "status": status,
                "typology": typology,
                "account_id": account_id,
                "alert_ids": alert_ids,
                "recommendation": recommendation,
                "decision": decision,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.decision import Decision  # noqa: PLC0415
        from ..models.recommendation import Recommendation  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        version = d.pop("version")

        status = CaseStatus(d.pop("status"))

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

        account_id = d.pop("account_id")

        alert_ids = []
        _alert_ids = d.pop("alert_ids")
        for alert_ids_item_data in _alert_ids:
            alert_ids_item = UUID(alert_ids_item_data)

            alert_ids.append(alert_ids_item)

        def _parse_recommendation(data: object) -> None | Recommendation:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                recommendation_type_0 = Recommendation.from_dict(data)

                return recommendation_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Recommendation, data)

        recommendation = _parse_recommendation(d.pop("recommendation"))

        def _parse_decision(data: object) -> Decision | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                decision_type_0 = Decision.from_dict(data)

                return decision_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(Decision | None, data)

        decision = _parse_decision(d.pop("decision"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        case = cls(
            id=id,
            version=version,
            status=status,
            typology=typology,
            account_id=account_id,
            alert_ids=alert_ids,
            recommendation=recommendation,
            decision=decision,
            created_at=created_at,
            updated_at=updated_at,
        )

        case.additional_properties = d
        return case

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
