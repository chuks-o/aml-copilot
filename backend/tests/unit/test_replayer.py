import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aml.data import dataset
from aml.ingest import replayer

DATA = Path(__file__).resolve().parents[1] / "fixtures" / "data"


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    """The fixture files in a temp dir: the replayer writes its sort cache next to them."""
    for name in (dataset.TRANSACTIONS_FILE, dataset.PATTERNS_FILE):
        shutil.copy(DATA / name, tmp_path / name)
    return tmp_path


@pytest.fixture
def rows(raw_dir: Path) -> pd.DataFrame:
    return replayer.load_ordered(raw_dir)


def test_rows_come_in_timestamp_then_id_order(rows: pd.DataFrame) -> None:
    keys = list(zip(rows["sort_ts"], rows["id"], strict=True))

    assert keys == sorted(keys)
    assert rows["id"].min() == 1
    assert rows["id"].max() == len(rows)


def test_rate_spaces_rows_evenly() -> None:
    ts = pd.Series(pd.to_datetime(["2022-09-01"] * 4, utc=True))
    due = replayer.due_times(ts, replayer.ReplayConfig(rate=2, compression=0))

    assert due.tolist() == [0.0, 0.5, 1.0, 1.5]


def test_compression_keeps_the_datas_rhythm() -> None:
    ts = pd.Series(
        pd.to_datetime(["2022-09-01 00:00", "2022-09-01 00:10", "2022-09-01 00:10"], utc=True)
    )

    due = replayer.due_times(ts, replayer.ReplayConfig(rate=0, compression=60))

    assert due.tolist() == [0.0, 10.0, 10.0]  # ten dataset minutes in ten wall seconds


def test_the_rate_caps_a_burst_that_compression_would_send_at_once() -> None:
    burst = pd.Series(pd.to_datetime(["2022-09-01 00:00"] * 3, utc=True))

    due = replayer.due_times(burst, replayer.ReplayConfig(rate=0.5, compression=60))

    assert due.tolist() == [0.0, 2.0, 4.0]  # same dataset minute, but at most 0.5 rows/s
    assert np.all(np.diff(due) >= 0)


def test_unthrottled_means_everything_is_due_at_once() -> None:
    ts = pd.Series(pd.to_datetime(["2022-09-01"] * 3, utc=True))

    assert replayer.due_times(ts, replayer.ReplayConfig(rate=0)).tolist() == [0.0, 0.0, 0.0]


def test_corruption_depends_only_on_seed_and_row_id(rows: pd.DataFrame) -> None:
    whole = rows.copy()
    first_half = rows.iloc[: len(rows) // 2].copy()

    picked_whole = replayer.corrupt(whole, rate=0.2, seed=7)
    picked_half = replayer.corrupt(first_half, rate=0.2, seed=7)

    assert picked_whole
    assert set(picked_half) == set(picked_whole) & set(first_half["id"])
    assert replayer.corrupt(rows.copy(), rate=0.2, seed=7) == picked_whole
    assert replayer.corrupt(rows.copy(), rate=0.2, seed=8) != picked_whole


def test_each_corruption_kind_is_quarantined_with_its_reason(rows: pd.DataFrame) -> None:
    damaged = rows.copy()
    picked = replayer.corrupt(damaged, rate=0.5, seed=1)

    valid, rejected = replayer.validate(damaged)

    assert sorted(rejected["id"]) == picked
    assert set(valid["id"]).isdisjoint(picked)
    reasons = {e.split(" '")[0] for e in rejected["error"]}
    assert reasons == {"unknown currency", "negative amount", "unparsable timestamp"}
    assert any("'Dogecoin' in Payment Currency" in e for e in rejected["error"])
    assert any(e == "unparsable timestamp '2022/13/45 25:99'" for e in rejected["error"])


def test_valid_rows_are_normalised_for_copy(rows: pd.DataFrame) -> None:
    valid, rejected = replayer.validate(rows)

    assert rejected.empty
    first = valid.iloc[0]
    assert first["ts"] == "2022-09-01 00:00:00+00:00"
    assert first["from_account"] == "70:ABC000001"  # bank "070" normalised (0015)
    assert first["currency_paid"] == "USD"
    assert first["payment_format"] == "ACH"


def test_the_sorted_copy_is_built_once_and_rebuilt_when_the_source_changes(raw_dir: Path) -> None:
    first = replayer.sorted_copy(raw_dir, echo=lambda _: None)
    built = first.stat().st_mtime_ns
    assert replayer.sorted_copy(raw_dir, echo=lambda _: None).stat().st_mtime_ns == built

    source = raw_dir / dataset.TRANSACTIONS_FILE
    source.write_text(source.read_text() + source.read_text().splitlines()[1] + "\n")
    rebuilt = replayer.sorted_copy(raw_dir, echo=lambda _: None)

    assert rebuilt.stat().st_mtime_ns != built
    assert sum(1 for _ in rebuilt.open()) == sum(1 for _ in source.open())
    assert sorted(p.name for p in rebuilt.parent.iterdir()) == [
        "transactions_sorted.csv",
        "transactions_sorted.json",
    ]  # no leftover runs


def test_streaming_in_small_chunks_matches_one_in_memory_sort(
    raw_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = dataset.read_transactions(raw_dir / dataset.TRANSACTIONS_FILE)
    raw["id"] = np.arange(1, len(raw) + 1)
    expected = raw.sort_values(["ts_raw", "id"], kind="stable")["id"].tolist()
    monkeypatch.setattr(replayer, "RUN_ROWS", 7)  # many tiny sorted runs to merge

    chunks = list(replayer.stream_ordered(raw_dir, echo=lambda _: None, rows=10))

    assert [i for chunk in chunks for i in chunk["id"]] == expected
    assert max(len(c) for c in chunks) == 10
