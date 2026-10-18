"""The FastAPI routes are exactly the operations in openapi.yaml.

Models are generated from the spec (aml.api.schemas), but the route table and parameter
defaults are written in code; these tests keep them in step with the spec.
"""

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.routing import APIRoute

from aml.api.app import app

SPEC: dict[str, Any] = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "openapi.yaml").read_text()
)
METHODS = {"get", "post", "put", "patch", "delete"}
OPS_ONLY = {"/healthz"}  # served by the process, not part of the contract (0014)


def _resolve(node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        target: Any = SPEC
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def _spec_operations() -> dict[str, tuple[str, str, dict[str, Any]]]:
    return {
        op["operationId"]: (method.upper(), path, op)
        for path, item in SPEC["paths"].items()
        for method, op in item.items()
        if method in METHODS
    }


def _api_routes(routes: Sequence[Any]) -> Iterator[APIRoute]:
    """Every APIRoute, including those of included routers.

    FastAPI 0.143 wraps included routers lazily (``original_router``); older versions copy
    their routes onto the app. Our routers have no prefix, so their paths are final.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif (inner := getattr(route, "original_router", None)) is not None:
            yield from _api_routes(inner.routes)


def _contract_routes() -> list[APIRoute]:
    return [r for r in _api_routes(app.routes) if r.path not in OPS_ONLY]


def _routes() -> dict[str, APIRoute]:
    return {r.operation_id: r for r in _contract_routes() if r.operation_id}


def test_every_operation_has_exactly_one_route() -> None:
    assert sorted(r.operation_id or "" for r in _contract_routes()) == sorted(_spec_operations())


@pytest.mark.parametrize("operation_id", sorted(_spec_operations()))
def test_route_matches_method_path_and_success_status(operation_id: str) -> None:
    method, path, op = _spec_operations()[operation_id]
    route = _routes()[operation_id]
    success = [int(code) for code in op["responses"] if code.startswith("2")]

    assert (route.methods, route.path) == ({method}, path)
    assert [route.status_code or 200] == success


@pytest.mark.parametrize("operation_id", sorted(_spec_operations()))
def test_query_parameters_match_names_requiredness_and_defaults(operation_id: str) -> None:
    _, _, op = _spec_operations()[operation_id]
    spec_params = {
        p["name"]: p for p in (_resolve(p) for p in op.get("parameters", [])) if p["in"] == "query"
    }
    route_params = {f.alias: f for f in _routes()[operation_id].dependant.query_params}

    assert sorted(route_params) == sorted(spec_params)
    for name, param in spec_params.items():
        field = route_params[name]
        default = _resolve(param["schema"]).get("default")
        assert field.field_info.is_required() == param.get("required", False), name
        assert (None if field.field_info.is_required() else field.default) == default, name
