from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aml.cli import app
from aml.common import get_settings
from aml.data.dataset import ActivityGap
from aml.data.seed import SeedReport

runner = CliRunner()


def test_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["api", "worker", "replay", "migrate", "download", "seed", "train", "eval"]:
        assert command in result.output


# Never add seed, download or replay here: invoking them for real would read data/raw and write to
# the configured database or call Kaggle. Their tests below replace the work functions.
@pytest.mark.parametrize("command", ["train", "eval"])
def test_stub_commands_say_not_implemented(command: str) -> None:
    result = runner.invoke(app, [command])

    assert result.exit_code == 0
    assert result.output == f"aml {command}: not implemented\n"


def test_eval_smoke_flag() -> None:
    result = runner.invoke(app, ["eval", "--smoke"])

    assert result.output == "aml eval --smoke: not implemented\n"


def test_api_starts_uvicorn_with_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(target: str, **kwargs: object) -> None:
        calls.append({"target": target, **kwargs})

    monkeypatch.setattr("aml.cli.uvicorn.run", fake_run)

    result = runner.invoke(app, ["api", "--port", "9100"])

    assert result.exit_code == 0
    assert calls == [
        {
            "target": "aml.api.app:app",
            "host": "127.0.0.1",
            "port": 9100,
            "reload": False,
            "log_config": None,
        }
    ]


def test_migrate_upgrades_to_head_from_configured_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr("aml.cli.db.upgrade_to_head", calls.append)

    result = runner.invoke(app, ["migrate"])

    assert result.exit_code == 0
    assert [str(c) for c in calls] == ["migrations"]


def test_seed_runs_against_the_configured_raw_dir_and_prints_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def fake_seed(raw_dir: Path, *, echo: Callable[[str], None], accounts_only: bool) -> SeedReport:
        calls.append(raw_dir)
        return SeedReport(
            tables={"accounts": 2, "transactions": 3},
            partitions={"transactions_2022_09": 3},
            analysis_end=datetime(2022, 9, 11, tzinfo=UTC),
            after_end={"rows": 1, "laundering": 1, "clean": 0},
            gap=ActivityGap(below=394, above=6468),
            high_volume_banks={"70": 1},
            unlisted_by_format={"CASH": 1},
            inconsistent_percent={"laundering accounts": 10.0, "other accounts": 10.0},
            fingerprints={"accounts": "2 rows, md5 x"},
        )

    monkeypatch.setattr("aml.data.seed.seed", fake_seed)

    result = runner.invoke(app, ["seed"])

    assert result.exit_code == 0, result.output
    assert calls == [Path("data/raw")]
    assert "ANALYSIS_END: 2022-09-11T00:00:00+00:00" in result.output
    assert "no account between 394 and 6,468 transactions" in result.output


def test_download_passes_env_credentials_to_kaggle(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_download(raw_dir: Path, *, client: Callable[[], object], echo: object) -> list[object]:
        seen["raw_dir"] = raw_dir
        seen["client"] = client
        return []

    monkeypatch.setenv("KAGGLE_API_TOKEN", "tok-123")
    monkeypatch.setattr("aml.data.download.download", fake_download)
    monkeypatch.setattr(
        "aml.data.download.kaggle_client", lambda credentials: seen.update(credentials=credentials)
    )
    get_settings.cache_clear()

    result = runner.invoke(app, ["download"])
    client = seen["client"]
    assert callable(client)
    client()

    assert result.exit_code == 0, result.output
    assert seen["raw_dir"] == Path("data/raw")
    assert seen["credentials"] == {"KAGGLE_API_TOKEN": "tok-123"}
    get_settings.cache_clear()
