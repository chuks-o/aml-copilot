"""``aml download``: fetch only the HI-Small files from Kaggle into backend/data/raw/.

The Kaggle dataset holds Small, Medium and Large variants (about 8 GB); we need three small
files, so they are requested one at a time. Credentials are the Kaggle library's own sources:
``KAGGLE_API_TOKEN`` (or ~/.kaggle/access_token), then ``KAGGLE_USERNAME``/``KAGGLE_KEY`` (or
~/.kaggle/kaggle.json). Rationale: docs/decisions/0023-seed-and-download.md.
"""

import os
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from aml.data import dataset

KAGGLE_DATASET = "ealtman2019/ibm-transactions-for-anti-money-laundering-aml"
FILES = (dataset.TRANSACTIONS_FILE, dataset.PATTERNS_FILE, dataset.ACCOUNTS_FILE)
MIN_FREE_BYTES = 5 * 1024**3


class KaggleClient(Protocol):
    def dataset_download_file(self, dataset: str, file_name: str, path: str) -> object: ...


@dataclass(frozen=True)
class FileReport:
    name: str
    status: str  # "downloaded" or "present"
    size_bytes: int
    rows: int


def kaggle_client(credentials: dict[str, str] | None = None) -> KaggleClient:
    """The real client. ``credentials`` (from .env) fill in the environment variables the kaggle
    library reads, without overriding ones already set. Imported here, not at module level:
    ``import kaggle`` authenticates as a side effect."""
    for name, value in (credentials or {}).items():
        os.environ.setdefault(name, value)
    from kaggle.api.kaggle_api_extended import KaggleApi

    api: KaggleClient = KaggleApi()
    api.authenticate()  # type: ignore[attr-defined]  # not part of our Protocol
    return api


def count_rows(path: Path) -> int:
    """Data rows: CSV lines minus the header; pattern lines minus BEGIN/END markers."""
    with path.open(newline="") as f:
        if path.name == dataset.PATTERNS_FILE:
            return sum(1 for line in f if line.strip() and "LAUNDERING ATTEMPT" not in line)
        return sum(1 for _ in f) - 1


def _unzip(raw_dir: Path, name: str) -> None:
    archive = raw_dir / f"{name}.zip"
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            z.extract(name, raw_dir)
        archive.unlink()


def download(
    raw_dir: Path,
    *,
    client: Callable[[], KaggleClient] = kaggle_client,
    echo: Callable[[str], None] = print,
) -> list[FileReport]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(raw_dir).free
    if free < MIN_FREE_BYTES:
        echo(f"warning: only {free / 1024**3:.1f} GB free on {raw_dir} (5 GB recommended)")
    api: KaggleClient | None = None
    reports = []
    for name in FILES:
        path = raw_dir / name
        status = "present"
        if not path.is_file():
            api = api or client()
            echo(f"downloading {name} …")
            api.dataset_download_file(KAGGLE_DATASET, name, path=str(raw_dir))
            _unzip(raw_dir, name)
            if not path.is_file():
                raise FileNotFoundError(f"Kaggle did not produce {path}")
            status = "downloaded"
        report = FileReport(name, status, path.stat().st_size, count_rows(path))
        size_mb = report.size_bytes / 1024**2
        echo(f"{report.name}: {report.status}, {size_mb:,.1f} MB, {report.rows:,} rows")
        reports.append(report)
    return reports
