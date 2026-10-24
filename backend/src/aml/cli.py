"""The ``aml`` command-line entrypoint."""

from pathlib import Path
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
def replay(
    rate: Annotated[float, typer.Option(help="Max rows per second; 0 = no cap")] = 2_000.0,
    compression: Annotated[
        float, typer.Option(help="Dataset seconds per wall second; 0 = off (rate alone paces)")
    ] = 0.0,
    corrupt_rate: Annotated[
        float, typer.Option(help="Share of rows to damage on purpose, to test quarantine")
    ] = 0.0,
    seed: Annotated[int, typer.Option(help="Random seed for --corrupt-rate")] = 42,
    limit: Annotated[int | None, typer.Option(help="Replay at most this many rows")] = None,
    batch_size: Annotated[int, typer.Option(help="Rows per COPY batch")] = 5_000,
    from_start: Annotated[
        bool, typer.Option(help="Ignore the stored position and start from the beginning")
    ] = False,
    rules: Annotated[
        bool, typer.Option(help="Run the monitoring rules per batch and POST alerts to the API")
    ] = True,
    rules_config: Annotated[
        Path | None, typer.Option(help="Rules YAML [default: the packaged rules.yaml]")
    ] = None,
) -> None:
    """Replay HI-Small in timestamp order, as if live (after `aml seed --accounts-only`)."""
    from aml.ingest.replayer import ReplayConfig
    from aml.ingest.replayer import replay as run
    from aml.ingest.rules import load_config

    settings = get_settings()
    configure_logging("aml-replay", settings.log_level)
    config = ReplayConfig(
        rate=rate,
        compression=compression,
        corrupt_rate=corrupt_rate,
        seed=seed,
        limit=limit,
        batch_size=batch_size,
        from_start=from_start,
        rules=load_config(rules_config) if rules else None,
    )
    report = run(settings.raw_data_dir, config, echo=typer.echo)
    typer.echo(
        f"replayed {report.committed:,} committed, {report.quarantined:,} quarantined, "
        f"{report.duplicates:,} duplicates in {report.batches:,} batches, {report.seconds} s"
    )
    if config.rules is not None:
        typer.echo(
            f"alerts: {report.alerts:,} (rule-to-alert lag p95 {report.alert_lag_p95_ms()} ms)"
        )
        for rule_id, count in sorted(report.alerts_by_rule.items()):
            typer.echo(f"  {rule_id:<24} {count:>8,}")
        for error in report.alert_errors[:10]:
            typer.echo(f"  alert error: {error}")


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
def seed(
    accounts_only: Annotated[
        bool, typer.Option(help="Load accounts and settings only; leave transactions to replay")
    ] = False,
) -> None:
    """Load HI-Small into the database: accounts with KYC profiles, transactions, settings."""
    from aml.data.seed import seed as run

    settings = get_settings()
    configure_logging("aml-seed", settings.log_level)
    report = run(settings.raw_data_dir, echo=typer.echo, accounts_only=accounts_only)
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
def label(
    check: Annotated[
        bool, typer.Option(help="Recompute without writing; fail if splits.json no longer matches")
    ] = False,
) -> None:
    """Label alerts, freeze the dev/test time split, write backend/data/splits.json."""
    from aml.evals import labels

    settings = get_settings()
    configure_logging("aml-label", settings.log_level)
    with db.connect() as conn:
        try:
            result = labels.check(conn) if check else labels.run(conn)
        except labels.LabelError as exc:
            typer.echo(f"aml label: {exc}", err=True)
            raise typer.Exit(1) from exc
    period = result["period"]
    typer.echo(
        f"{'matches' if check else 'wrote'} {labels.SPLITS_FILE.name}: dev {period['start']} .. "
        f"{period['dev_end']}, test .. {period['end']}"
    )
    for name, split in result["splits"].items():
        typer.echo(
            f"  {name:<5} {split['alerts']:>8,} alerts, {split['positives']:>7,} positive "
            f"({split['positive_rate']}), {split['heldout_cycle']:,} heldout_cycle"
        )
    typer.echo(f"  sha256 {result['sha256']}")


@app.command("golden-sample")
def golden_sample(
    check: Annotated[
        bool, typer.Option(help="Redraw without writing; fail if the stored sample differs")
    ] = False,
) -> None:
    """Draw the 80-alert golden sample from dev into backend/data/golden/ (once; seed fixed)."""
    from aml.evals import golden, labels

    settings = get_settings()
    configure_logging("aml-golden", settings.log_level)
    with db.connect() as conn:
        try:
            document = golden.check_sample(conn) if check else golden.write_sample(conn)
        except (golden.GoldenError, labels.LabelError) as exc:
            typer.echo(f"aml golden-sample: {exc}", err=True)
            raise typer.Exit(1) from exc
    typer.echo(
        f"{'matches' if check else 'wrote'} {golden.SAMPLE_FILE.name}: "
        f"{len(document['alerts'])} alerts, seed {document['seed']}"
    )
    for stratum, n in document["counts"].items():
        typer.echo(f"  {stratum:<28} {n:>3}")


@app.command("golden-label")
def golden_label(
    labeller: Annotated[
        str | None, typer.Option(help="Who is labelling [default: your login name]")
    ] = None,
    revise: Annotated[
        str | None, typer.Option(help="Label this one alert again (the new line wins)")
    ] = None,
) -> None:
    """Label the golden sample in the terminal; resumes where you stopped. Needs `aml api`."""
    import getpass
    from uuid import UUID

    from rich.console import Console
    from rich.markup import escape

    from aml.evals import golden, label_cli

    settings = get_settings()
    configure_logging("aml-golden", "WARNING")  # keep request logs off the labelling screen
    console = Console()
    session = label_cli.Session(
        source=label_cli.ApiSource(),
        console=console,
        read=lambda prompt: console.input(escape(prompt)),  # prompts hold [Y/n], notes
        labeller=labeller or getpass.getuser(),
    )
    try:
        session.run(revise=UUID(revise) if revise else None)
    except golden.GoldenError as exc:
        typer.echo(f"aml golden-label: {exc} (is `aml api` running at {settings.cases_api_url}?)")
        raise typer.Exit(1) from exc
    except (KeyboardInterrupt, EOFError):
        typer.echo("\nStopped; everything saved so far is kept.")


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
