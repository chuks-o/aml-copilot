"""Keeps the import-linter contracts in pyproject.toml in sync with the package.

Forbidden contracts list modules explicitly, so a new top-level module would
silently escape them. These tests fail until it is added.
"""

import tomllib
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
PACKAGE = BACKEND / "src" / "aml"


def _top_level_modules() -> set[str]:
    names = {p.name for p in PACKAGE.iterdir() if (p / "__init__.py").exists()}
    names |= {p.stem for p in PACKAGE.glob("*.py") if p.stem != "__init__"}
    return {f"aml.{name}" for name in names}


def _contract(contract_id: str) -> dict[str, Any]:
    config = tomllib.loads((BACKEND / "pyproject.toml").read_text())
    contracts: list[dict[str, Any]] = config["tool"]["importlinter"]["contracts"]
    return next(c for c in contracts if c["id"] == contract_id)


def test_every_module_is_barred_from_importing_evals() -> None:
    contract = _contract("evals-is-a-leaf")

    assert set(contract["source_modules"]) == _top_level_modules() - {"aml.evals"}


def test_common_is_barred_from_every_other_module() -> None:
    contract = _contract("common-is-foundation")

    assert set(contract["forbidden_modules"]) == _top_level_modules() - {"aml.common"}


def test_only_api_and_entry_points_may_import_db() -> None:
    contract = _contract("db-belongs-to-api")
    allowed = {"aml.api", "aml.cli", "aml.__main__", "aml.db"}

    assert set(contract["source_modules"]) == _top_level_modules() - allowed


def test_only_clients_may_import_httpx() -> None:
    contract = _contract("http-only-via-clients")

    assert set(contract["source_modules"]) == _top_level_modules() - {"aml.clients"}
