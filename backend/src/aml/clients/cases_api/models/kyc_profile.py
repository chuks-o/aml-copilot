from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast
import datetime


T = TypeVar("T", bound="KycProfile")


@_attrs_define
class KycProfile:
    """Synthetic KYC fields (decision 0023): deterministic per account, and about 10% are
    deliberately inconsistent with the account's activity. Each field is `null` when the
    profile lacks it.

        Attributes:
            country (None | str): ISO 3166-1 alpha-2.
            business_type (None | str):
            expected_monthly_volume_band (None | str): The declared monthly volume, as a band of amounts.
            onboarded_at (datetime.date | None):
            synthetic (list[str]): The fields above that are generated rather than taken from the dataset.
    """

    country: None | str
    business_type: None | str
    expected_monthly_volume_band: None | str
    onboarded_at: datetime.date | None
    synthetic: list[str]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        country: None | str
        country = self.country

        business_type: None | str
        business_type = self.business_type

        expected_monthly_volume_band: None | str
        expected_monthly_volume_band = self.expected_monthly_volume_band

        onboarded_at: None | str
        if isinstance(self.onboarded_at, datetime.date):
            onboarded_at = self.onboarded_at.isoformat()
        else:
            onboarded_at = self.onboarded_at

        synthetic = self.synthetic

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "country": country,
                "business_type": business_type,
                "expected_monthly_volume_band": expected_monthly_volume_band,
                "onboarded_at": onboarded_at,
                "synthetic": synthetic,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_country(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        country = _parse_country(d.pop("country"))

        def _parse_business_type(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        business_type = _parse_business_type(d.pop("business_type"))

        def _parse_expected_monthly_volume_band(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        expected_monthly_volume_band = _parse_expected_monthly_volume_band(
            d.pop("expected_monthly_volume_band")
        )

        def _parse_onboarded_at(data: object) -> datetime.date | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                onboarded_at_type_0 = datetime.date.fromisoformat(data)

                return onboarded_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None, data)

        onboarded_at = _parse_onboarded_at(d.pop("onboarded_at"))

        synthetic = cast(list[str], d.pop("synthetic"))

        kyc_profile = cls(
            country=country,
            business_type=business_type,
            expected_monthly_volume_band=expected_monthly_volume_band,
            onboarded_at=onboarded_at,
            synthetic=synthetic,
        )

        kyc_profile.additional_properties = d
        return kyc_profile

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
