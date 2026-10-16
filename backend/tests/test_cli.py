import pytest
from typer.testing import CliRunner

from aml.cli import app

runner = CliRunner()


def test_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["api", "worker", "replay", "migrate", "seed", "train", "eval"]:
        assert command in result.output


@pytest.mark.parametrize("command", ["replay", "seed", "train", "eval"])
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
