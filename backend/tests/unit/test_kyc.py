from datetime import UTC, datetime

from aml.data import kyc

FIRST_SEEN = datetime(2022, 9, 1, tzinfo=UTC)
REAL = {"bank_name": "Test Bank #10", "entity_id": "E1", "entity_name": "Corporation #1"}


def _profile(account_id: str, monthly: float = 50) -> dict[str, object]:
    return kyc.profile(
        account_id,
        entity_type="CORPORATION",
        real=REAL,
        monthly_transactions=monthly,
        first_seen=FIRST_SEEN,
    )


def test_a_profile_depends_only_on_the_account_id() -> None:
    first = _profile("10:8000EBD30")
    _profile("20:00000001")  # other accounts in between change nothing
    _profile("30:00000002")

    assert _profile("10:8000EBD30") == first


def test_real_fields_are_kept_and_synthetic_ones_are_labelled() -> None:
    profile = _profile("10:8000EBD30")

    assert {k: profile[k] for k in REAL} == REAL
    assert profile["synthetic"] == list(kyc.SYNTHETIC_FIELDS)
    assert str(profile["onboarded_at"]) < FIRST_SEEN.date().isoformat()


def test_about_ten_percent_are_inconsistent_chosen_by_id_alone() -> None:
    ids = [f"10:{n:09X}" for n in range(20_000)]
    share = sum(map(kyc.is_inconsistent, ids)) / len(ids)

    assert 0.09 < share < 0.11


def test_consistent_profiles_stay_near_the_actual_band() -> None:
    ids = [f"10:{n:09X}" for n in range(500)]
    for account_id in ids:
        band = kyc.VOLUME_BANDS.index(str(_profile(account_id, 50)["expected_monthly_volume_band"]))
        distance = abs(band - kyc.band_index(50))
        assert distance >= 2 if kyc.is_inconsistent(account_id) else distance <= 1
