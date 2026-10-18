import pytest
from fastapi.testclient import TestClient

from aml.api.app import app


def test_healthz() -> None:
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "aml-api", "version": "0.0.0"}


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_does_not_publish_a_generated_schema(path: str) -> None:
    assert TestClient(app).get(path).status_code == 404
