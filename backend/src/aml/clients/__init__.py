"""HTTP clients for aml.api, used by ingest, investigator, scoring, evals and the worker.

``cases_api`` is generated from ``openapi.yaml`` by ``make codegen``; never edit it by hand.
This package is the only one allowed to import httpx (import-linter ``http-only-via-clients``).
"""

import httpx

from aml.clients.cases_api import Client
from aml.common import get_settings

__all__ = ["Client", "cases_api_client"]


def cases_api_client() -> Client:
    """A Cases API client for the configured URL. Use its ``asyncio`` endpoint functions.

    Unexpected status codes (not declared in openapi.yaml) raise instead of returning None.
    """
    settings = get_settings()
    return Client(
        base_url=settings.cases_api_url,
        timeout=httpx.Timeout(settings.cases_api_timeout),
        raise_on_unexpected_status=True,
    )
