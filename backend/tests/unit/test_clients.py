import json
from uuid import UUID

import httpx
import pytest

from aml.clients import cases_api_client
from aml.clients.cases_api.api.cases import get_case
from aml.clients.cases_api.models import Problem
from aml.common import get_settings

CASE_ID = UUID("0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b")


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AML_CASES_API_URL", "http://api.test")
    get_settings.cache_clear()


def test_client_targets_the_configured_url() -> None:
    httpx_client = cases_api_client().get_async_httpx_client()

    assert str(httpx_client.base_url) == "http://api.test"


async def test_async_call_parses_problem_json() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = {"type": "about:blank", "title": "Not Found", "status": 404}
        return httpx.Response(
            404, content=json.dumps(body), headers={"content-type": "application/problem+json"}
        )

    client = cases_api_client()
    client.set_async_httpx_client(
        httpx.AsyncClient(base_url="http://api.test", transport=httpx.MockTransport(handler))
    )

    result = await get_case.asyncio(CASE_ID, client=client)

    assert [str(r.url) for r in seen] == [f"http://api.test/cases/{CASE_ID}"]
    assert isinstance(result, Problem)
    assert result.status == 404
