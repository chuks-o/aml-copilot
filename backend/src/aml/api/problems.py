"""RFC 9457 problem responses, and the mapping from bad input to the status codes in openapi.yaml.

| Bad input | Status |
| --- | --- |
| Path parameter, malformed header, missing or invalid ``Idempotency-Key`` | 400 |
| Missing ``If-Match`` | 428 |
| Query parameter or request body (including malformed JSON) | 422, with ``errors`` |

Rationale: docs/decisions/0019-stub-routes-and-contract-tests.md.
"""

from collections.abc import Sequence
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from aml.api.schemas import Error, Problem, ValidationProblem
from aml.common import get_logger

PROBLEM_JSON = "application/problem+json"
# RFC 3986 path characters (pchar plus "/"); everything else is percent-encoded.
_PATH_SAFE = "/:@!$&'()*+,;=-._~"

log = get_logger(__name__)


class ProblemError(Exception):
    """Raise from a route to answer with a problem response."""

    def __init__(
        self, status: int, detail: str | None = None, *, errors: Sequence[Error] | None = None
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.errors = errors


def problem_response(
    request: Request,
    status: int,
    detail: str | None = None,
    *,
    errors: Sequence[Error] | None = None,
) -> JSONResponse:
    fields: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        # Re-encoded: the decoded path can hold characters a uri-reference may not (found by
        # Schemathesis: GET /accounts/%C2%84 echoed a raw U+0084).
        "instance": quote(request.url.path, safe=_PATH_SAFE),
    }
    body = (
        ValidationProblem(**fields, errors=list(errors))
        if errors is not None
        else Problem(**fields)
    )
    return JSONResponse(
        body.model_dump(mode="json", exclude_none=True), status_code=status, media_type=PROBLEM_JSON
    )


def _pointer(loc: Sequence[str | int]) -> str:
    """('body', 'alert_ids', 0) -> '/body/alert_ids/0' (RFC 6901 escaping)."""
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in loc)


def _is_missing_if_match(error: dict[str, Any]) -> bool:
    return error.get("type") == "missing" and tuple(error.get("loc", ())) == ("header", "If-Match")


def _status_for(errors: Sequence[dict[str, Any]]) -> int:
    """400 for a bad path or header, else 428 for a missing If-Match, else 422."""
    if any(e["loc"][0] in {"path", "header"} and not _is_missing_if_match(e) for e in errors):
        return 400
    if any(_is_missing_if_match(e) for e in errors):
        return 428
    return 422


async def _on_validation_error(request: Request, exc: Exception) -> JSONResponse:
    errors = list(cast(RequestValidationError, exc).errors())
    status = _status_for(errors)
    detail = "; ".join(f"{_pointer(e['loc'])}: {e['msg']}" for e in errors)
    if status == 422:
        return problem_response(
            request,
            status,
            detail,
            errors=[Error(location=_pointer(e["loc"]), message=e["msg"]) for e in errors],
        )
    return problem_response(request, status, detail)


async def _on_problem(request: Request, exc: Exception) -> JSONResponse:
    problem = cast(ProblemError, exc)
    return problem_response(request, problem.status, problem.detail, errors=problem.errors)


async def _on_http_error(request: Request, exc: Exception) -> JSONResponse:
    http_error = cast(StarletteHTTPException, exc)
    response = problem_response(request, http_error.status_code, str(http_error.detail))
    if http_error.headers:
        response.headers.update(http_error.headers)
    return response


async def _on_unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", path=request.url.path)
    return problem_response(request, 500, "Unexpected server error.")


def install(app: FastAPI) -> None:
    """Answer every error from ``app`` with application/problem+json.

    Starlette types handlers as taking ``Exception``; each one is registered for exactly the
    type it casts to.
    """
    app.add_exception_handler(RequestValidationError, _on_validation_error)
    app.add_exception_handler(ProblemError, _on_problem)
    app.add_exception_handler(StarletteHTTPException, _on_http_error)
    app.add_exception_handler(Exception, _on_unexpected)
