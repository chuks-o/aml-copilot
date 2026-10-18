from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from aml.data import dataset

DATA = Path(__file__).resolve().parents[1] / "fixtures" / "data"


@pytest.fixture(scope="module")
def transactions() -> pd.DataFrame:
    raw = dataset.read_transactions(DATA / dataset.TRANSACTIONS_FILE)
    return dataset.normalise(raw, dataset.read_patterns(DATA / dataset.PATTERNS_FILE))


def test_duplicate_account_columns_are_named_by_the_bank_before_them() -> None:
    raw = dataset.read_transactions(DATA / dataset.TRANSACTIONS_FILE)

    assert list(raw.columns[:5]) == [
        "ts_raw", "from_bank", "from_account_number", "to_bank", "to_account_number",
    ]  # fmt: skip
    assert "Account.1" not in raw.columns


def test_bank_codes_stay_text_until_deliberately_normalised() -> None:
    raw = dataset.read_transactions(DATA / dataset.TRANSACTIONS_FILE)

    assert {"010", "0010", "070"} <= set(raw["from_bank"])
    assert dataset.normalise_bank(pd.Series(["010", "0010", "000", "070"])).tolist() == [
        "10", "10", "0", "70",
    ]  # fmt: skip


def test_an_unexpected_header_stops_the_load(tmp_path: Path) -> None:
    bad = tmp_path / dataset.TRANSACTIONS_FILE
    bad.write_text("Timestamp,From Bank,To Bank\n")

    with pytest.raises(dataset.DatasetError, match="unexpected header"):
        dataset.read_transactions(bad)


def test_ids_are_file_positions_and_identical_on_every_read(transactions: pd.DataFrame) -> None:
    again = dataset.normalise(
        dataset.read_transactions(DATA / dataset.TRANSACTIONS_FILE),
        dataset.read_patterns(DATA / dataset.PATTERNS_FILE),
    )

    assert transactions["id"].tolist() == list(range(1, len(transactions) + 1))
    pd.testing.assert_frame_equal(transactions, again)


def test_timestamps_are_utc_minutes(transactions: pd.DataFrame) -> None:
    assert transactions["ts"].iloc[0] == pd.Timestamp("2022-09-01 00:00", tz="UTC")


def test_account_ids_are_bank_plus_number(transactions: pd.DataFrame) -> None:
    ids = set(transactions["from_account"]) | set(transactions["to_account"])

    # One number at two banks stays two accounts; "010" and "0010" are the same bank.
    assert {"10:800000000", "20:800000000", "70:ABC000001"} <= ids
    assert not any(i.startswith("0") for i in ids)


def test_dataset_spellings_map_to_ours(transactions: pd.DataFrame) -> None:
    btc = transactions[transactions["currency_paid"] == "BTC"].iloc[0]

    assert (btc["amount_paid"], btc["payment_format"]) == ("0.000001", "BITCOIN")
    assert set(transactions["payment_format"]) == {"ACH", "CHEQUE", "BITCOIN", "CASH", "WIRE"}


def test_pattern_is_the_typology_unlisted_or_null(transactions: pd.DataFrame) -> None:
    laundering = transactions[transactions["is_laundering"]]

    assert laundering["pattern"].value_counts().to_dict() == {"UNLISTED": 2, "FAN_IN": 2}
    assert transactions.loc[~transactions["is_laundering"], "pattern"].isna().all()


def test_a_pattern_row_matching_nothing_stops_the_load(tmp_path: Path) -> None:
    patterns = tmp_path / dataset.PATTERNS_FILE
    patterns.write_text(
        "BEGIN LAUNDERING ATTEMPT - CYCLE\n"
        "2022/09/09 09:09,010,800000001,020,800000002,1.00,Euro,1.00,Euro,ACH,1\n"
        "END LAUNDERING ATTEMPT - CYCLE\n"
    )
    raw = dataset.read_transactions(DATA / dataset.TRANSACTIONS_FILE)

    with pytest.raises(dataset.DatasetError, match="match no transaction"):
        dataset.normalise(raw, dataset.read_patterns(patterns))


def test_activity_gap_finds_the_hub(transactions: pd.DataFrame) -> None:
    counts = dataset.activity(transactions)
    gap = dataset.activity_gap(counts)

    assert counts["70:ABC000001"] == 120
    assert gap.above == 120
    assert gap.below < 20
    assert counts[counts >= gap.above].index.tolist() == ["70:ABC000001"]


def test_analysis_end_is_the_end_of_the_last_normal_day(transactions: pd.DataFrame) -> None:
    # Clean rows per day: 41, 40, 40, then 1 on 2022-09-05 (under 10% of the median).
    assert dataset.analysis_end(transactions) == datetime(2022, 9, 4, tzinfo=UTC)


def test_real_entity_fields_come_from_the_accounts_file() -> None:
    accounts = dataset.read_accounts(DATA / dataset.ACCOUNTS_FILE).set_index("id")

    assert accounts.loc["70:ABC000001", "bank_name"] == "Test Bank #70"
    assert set(accounts["entity_type"]) <= set(dataset.ENTITY_TYPES.values())
