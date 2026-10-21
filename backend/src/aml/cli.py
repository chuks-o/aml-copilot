"""The ``aml`` command-line entrypoint."""

from typing import Annotated

import typer
import uvicorn

from aml import db
from aml import worker as worker_loop
from aml.common import configure_logging, get_settings

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
    """Run background jobs (scoring, investigations). Touches a heartbeat file every few seconds."""
    settings = get_settings()
    configure_logging("aml-worker", settings.log_level)
    worker_loop.run_until_signalled(
        settings.worker_heartbeat_path, settings.worker_heartbeat_interval
    )


@app.command()
def replay() -> None:
    """Replay historical transactions as if live."""
    _not_implemented("replay")


@app.command()
def migrate() -> None:
    """Apply database migrations (alembic upgrade head)."""
    settings = get_settings()
    configure_logging("aml-migrate", settings.log_level)
    db.upgrade_to_head(settings.migrations_dir)


@app.command()
def download() -> None:
    """Fetch the HI-Small files from Kaggle into the raw data directory (skips files present)."""
    from aml.data.download import download as run
    from aml.data.download import kaggle_client

    settings = get_settings()
    secrets = {"KAGGLE_API_TOKEN": settings.kaggle_api_token, "KAGGLE_KEY": settings.kaggle_key}
    credentials = {name: s.get_secret_value() for name, s in secrets.items() if s is not None}
    if settings.kaggle_username:
        credentials["KAGGLE_USERNAME"] = settings.kaggle_username
    run(settings.raw_data_dir, client=lambda: kaggle_client(credentials), echo=typer.echo)


@app.command()
def seed() -> None:
    """Load HI-Small into the database: accounts with KYC profiles, transactions, settings."""
    from aml.data.seed import seed as run

    settings = get_settings()
    configure_logging("aml-seed", settings.log_level)
    report = run(settings.raw_data_dir, echo=typer.echo)
    echo = typer.echo
    echo("\nrows per table:")
    for table, count in report.tables.items():
        echo(f"  {table:<20} {count:>10,}")
    echo("rows per partition:")
    for partition, count in report.partitions.items():
        echo(f"  {partition:<20} {count:>10,}")
    after = report.after_end
    echo(f"ANALYSIS_END: {report.analysis_end.isoformat()}")
    echo(
        f"  rows after it: {after['rows']:,} "
        f"({after['laundering']:,} laundering, {after['clean']:,} clean)"
    )
    gap = report.gap
    echo(f"high-volume cut: no account between {gap.below:,} and {gap.above:,} transactions")
    echo(f"  high-volume accounts by bank: {report.high_volume_banks}")
    echo(f"UNLISTED laundering rows by payment format: {report.unlisted_by_format}")
    echo(f"inconsistent KYC profiles (%): {report.inconsistent_percent}")
    echo("fingerprints:")
    for table, fingerprint in report.fingerprints.items():
        echo(f"  {table:<13} {fingerprint}")
    echo(f"seconds: {report.seconds}")


@app.command(name="sweep-idempotency-keys")
def sweep_idempotency_keys() -> None:
    """Delete Idempotency-Keys older than 24 hours (run on a schedule once there is one)."""
    from aml.api import database
    from aml.api.idempotency import sweep

    with database.engine().begin() as conn:
        deleted = sweep(conn)
    typer.echo(f"deleted {deleted:,} expired idempotency keys")


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
