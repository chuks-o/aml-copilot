import pytest
from pydantic import ValidationError

from aml.common import Settings


def test_reads_prefixed_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AML_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AML_API_PORT", "9001")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.api_port == 9001


def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AML_LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
