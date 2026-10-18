"""FastAPI application. Run with ``aml api``."""

from importlib.metadata import version

from fastapi import FastAPI
from pydantic import BaseModel

from aml.api import problems
from aml.api.routes import accounts, alerts, cases
from aml.common import configure_logging, get_logger, get_settings

SERVICE = "aml-api"


class Health(BaseModel):
    status: str
    service: str
    version: str


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(SERVICE, settings.log_level)
    health = Health(status="ok", service=SERVICE, version=version("aml"))

    # backend/openapi.yaml is the contract (decision 0014); FastAPI must not publish its own.
    app = FastAPI(
        title="aml-copilot API",
        version=health.version,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )

    problems.install(app)
    for module in (alerts, accounts, cases):
        app.include_router(module.router)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> Health:
        """Liveness probe: the process is up. Does not check dependencies."""
        return health

    get_logger(__name__).info("app_created", env=settings.env)
    return app


app = create_app()
