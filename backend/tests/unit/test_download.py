import shutil
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from aml.data import dataset
from aml.data import download as dl

DATA = Path(__file__).resolve().parents[1] / "fixtures" / "data"


class FakeKaggle:
    """Copies fixture files instead of calling Kaggle; records what was asked for."""

    def __init__(self) -> None:
        self.requested: list[tuple[str, str]] = []

    def dataset_download_file(self, dataset: str, file_name: str, path: str) -> object:
        self.requested.append((dataset, file_name))
        shutil.copy(DATA / file_name, Path(path) / file_name)
        return True


def _client(fake: FakeKaggle) -> Callable[[], dl.KaggleClient]:
    return lambda: fake


def test_downloads_only_the_hi_small_files_one_at_a_time(tmp_path: Path) -> None:
    fake = FakeKaggle()

    reports = dl.download(tmp_path, client=_client(fake), echo=lambda _: None)

    assert fake.requested == [(dl.KAGGLE_DATASET, name) for name in dl.FILES]
    assert {r.name: (r.status, r.rows) for r in reports} == {
        dataset.TRANSACTIONS_FILE: ("downloaded", 126),
        dataset.PATTERNS_FILE: ("downloaded", 2),
        dataset.ACCOUNTS_FILE: ("downloaded", 15),
    }


def test_files_already_present_are_skipped_without_contacting_kaggle(tmp_path: Path) -> None:
    for name in dl.FILES:
        shutil.copy(DATA / name, tmp_path / name)

    def no_client() -> dl.KaggleClient:
        raise AssertionError("Kaggle contacted although every file is present")

    reports = dl.download(tmp_path, client=no_client, echo=lambda _: None)

    assert {r.status for r in reports} == {"present"}


def test_zipped_downloads_are_unpacked(tmp_path: Path) -> None:
    class ZippingKaggle(FakeKaggle):
        def dataset_download_file(self, dataset: str, file_name: str, path: str) -> object:
            archive = shutil.make_archive(str(tmp_path / "staging"), "zip", DATA, file_name)
            shutil.move(archive, Path(path) / f"{file_name}.zip")
            return True

    dl.download(tmp_path, client=_client(ZippingKaggle()), echo=lambda _: None)

    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(dl.FILES)


def test_warns_when_disk_is_low(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Usage(NamedTuple):
        total: int
        used: int
        free: int

    monkeypatch.setattr("aml.data.download.shutil.disk_usage", lambda _: Usage(0, 0, 2 * 1024**3))
    for name in dl.FILES:
        shutil.copy(DATA / name, tmp_path / name)
    lines: list[str] = []

    dl.download(tmp_path, client=_client(FakeKaggle()), echo=lines.append)

    assert lines[0].startswith("warning: only 2.0 GB free")
