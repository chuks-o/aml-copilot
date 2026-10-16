"""Typed configuration read from environment variables.

App settings use the ``AML_`` prefix. Credentials use the same unprefixed names
the Postgres and RabbitMQ images read (``POSTGRES_PASSWORD`` …), so each secret
appears in ``.env`` once. Real environment variables win over ``.env``; the
``.env`` file is looked up in the current directory and its parent, so the
repo-root ``.env`` is found from the root or from ``backend/``.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AML_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = "local"
    log_level: LogLevel = "INFO"

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # Where callers reach the API (aml.clients). Differs from api_host/port in containers.
    cases_api_url: str = "http://127.0.0.1:8000"
    cases_api_timeout: float = 10.0

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = Field(default="aml", validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="aml", validation_alias="POSTGRES_DB")

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = Field(default="aml", validation_alias="RABBITMQ_DEFAULT_USER")
    rabbitmq_password: SecretStr = Field(validation_alias="RABBITMQ_DEFAULT_PASS")

    migrations_dir: Path = Path("migrations")
    worker_heartbeat_path: Path = Path("/tmp/aml/worker.heartbeat")  # noqa: S108
    worker_heartbeat_interval: float = 5.0

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
