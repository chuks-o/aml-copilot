"""Background worker process (``aml worker``).

For now the loop only proves it is alive: after every iteration it touches a
heartbeat file, which the container healthcheck requires to be recent. Real job
handling (consuming RabbitMQ) slots into ``_run_once``; because the heartbeat is
touched *after* each iteration, a stuck job makes the container unhealthy.
"""

import signal
import threading
from pathlib import Path
from types import FrameType

from aml.common import get_logger

log = get_logger(__name__)


def _run_once() -> None:
    """One unit of work. Nothing to do until the queue consumer exists."""


def run(heartbeat_path: Path, interval: float, stop: threading.Event) -> None:
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("worker_started", heartbeat=str(heartbeat_path), interval=interval)
    while not stop.is_set():
        _run_once()
        heartbeat_path.touch()
        stop.wait(interval)
    log.info("worker_stopped")


def run_until_signalled(heartbeat_path: Path, interval: float) -> None:
    """Run until SIGTERM (``docker stop``) or SIGINT (Ctrl-C), then exit cleanly."""
    stop = threading.Event()

    def _request_stop(signum: int, _frame: FrameType | None) -> None:
        log.info("worker_stopping", signal=signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    run(heartbeat_path, interval, stop)
