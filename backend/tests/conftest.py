"""Test-wide setup: environment, tier markers, shared fixtures.

Tiers live in directories, and each test gets its tier's marker from its path:

| Directory | Marker | Run by |
| --- | --- | --- |
| ``tests/unit/`` | ``unit`` | ``make test`` |
| ``tests/contract/`` | ``contract`` | ``make test`` (and ``make contract``) |
| ``tests/integration/`` | ``integration`` | ``make test-integration`` (needs Docker) |

``slow`` is applied by hand. Rationale: docs/decisions/0020-test-infrastructure.md.
"""

import os
from pathlib import Path

import pytest

# Set before any test module is imported, because ``aml.api.app`` builds its app (and reads
# settings) at import time. Real environment variables win over the developer's .env.
os.environ.update(
    {
        "AML_ENV": "test",
        "POSTGRES_PASSWORD": "test-only",
        "RABBITMQ_DEFAULT_PASS": "test-only",
    }
)

pytest_plugins = ["tests.fixtures.postgres", "tests.fixtures.rabbitmq", "tests.fixtures.fake_llm"]

TESTS = Path(__file__).resolve().parent
TIERS = ("unit", "integration", "contract")


def tier_of(path: Path) -> str:
    """The tier a test file belongs to: the first directory under tests/."""
    tier = path.resolve().relative_to(TESTS).parts[0]
    if tier not in TIERS:
        raise pytest.UsageError(
            f"{path}: tests must live in tests/unit, tests/integration or tests/contract"
        )
    return tier


@pytest.hookimpl(tryfirst=True)  # before pytest's -m deselection sees the items
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        tier = tier_of(item.path)
        declared = {m.name for m in item.iter_markers() if m.name in TIERS}
        if declared - {tier}:
            raise pytest.UsageError(
                f"{item.nodeid}: marked {sorted(declared)} but lives in tests/{tier}/"
            )
        item.add_marker(getattr(pytest.mark, tier))
