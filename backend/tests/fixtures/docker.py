"""Docker availability for container fixtures."""

import docker
import pytest
from docker.errors import DockerException

# Credentials for throwaway test containers only; never used outside tests.
TEST_USER = "aml"
TEST_PASSWORD = "test-only"  # noqa: S105


def require_docker() -> None:
    """Fail (never skip) when Docker is unavailable: a skipped integration suite looks green."""
    try:
        docker.from_env().ping()
    except DockerException as exc:
        pytest.fail(f"Integration tests need a running Docker daemon: {exc}", pytrace=False)
