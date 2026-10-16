import pytest
from pydantic import ValidationError

from aml.common import Settings


def test_reads_prefixed_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AML_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AML_API_PORT", "9001")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.api_port == 9001


def test_credentials_use_the_image_variable_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_USER", "alice")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p%w@d")
    monkeypatch.setenv("POSTGRES_DB", "cases")
    monkeypatch.setenv("AML_POSTGRES_HOST", "postgres")

    url = Settings(_env_file=None).database_url

    assert url.render_as_string(hide_password=False) == (
        "postgresql+psycopg://alice:p%25w%40d@postgres:5432/cases"
    )


def test_passwords_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD")

    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
        Settings(_env_file=None)


def test_passwords_are_hidden_in_repr() -> None:
    assert "test-only" not in repr(Settings(_env_file=None))


def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AML_LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
