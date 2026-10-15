"""The ``aml`` command-line entrypoint."""

from typing import Annotated

import typer
import uvicorn

from aml.common import get_settings

app = typer.Typer(help="aml-copilot backend.", no_args_is_help=True, add_completion=False)


def _not_implemented(command: str) -> None:
    typer.echo(f"aml {command}: not implemented")


@app.command()
def api(
    host: Annotated[str | None, typer.Option(help="Bind address [default: AML_API_HOST]")] = None,
    port: Annotated[int | None, typer.Option(help="Port [default: AML_API_PORT]")] = None,
    reload: Annotated[bool, typer.Option(help="Restart on code changes")] = False,
) -> None:
    """Serve the HTTP API."""
    settings = get_settings()
    uvicorn.run(
        "aml.api.app:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
        log_config=None,
    )


@app.command()
def worker() -> None:
    """Run background jobs (scoring, investigations)."""
    _not_implemented("worker")


@app.command()
def replay() -> None:
    """Replay historical transactions as if live."""
    _not_implemented("replay")


@app.command()
def migrate() -> None:
    """Apply database migrations."""
    _not_implemented("migrate")


@app.command()
def seed() -> None:
    """Load starter data."""
    _not_implemented("seed")


@app.command()
def train() -> None:
    """Train the scoring model."""
    _not_implemented("train")


@app.command(name="eval")
def eval_(
    smoke: Annotated[bool, typer.Option(help="Run the quick smoke subset")] = False,
) -> None:
    """Run evaluations."""
    _not_implemented("eval --smoke" if smoke else "eval")
