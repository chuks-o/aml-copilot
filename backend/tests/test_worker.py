import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from aml.worker import run


def _wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_touches_heartbeat_repeatedly_until_stopped(tmp_path: Path) -> None:
    heartbeat = tmp_path / "nested" / "worker.heartbeat"
    stop = threading.Event()
    thread = threading.Thread(target=run, args=(heartbeat, 0.05, stop))

    thread.start()
    assert _wait_for(heartbeat.exists)
    first = heartbeat.stat().st_mtime_ns
    assert _wait_for(lambda: heartbeat.stat().st_mtime_ns > first)
    stop.set()
    thread.join(timeout=2)

    assert not thread.is_alive()


def test_aml_worker_exits_cleanly_on_sigterm(tmp_path: Path) -> None:
    heartbeat = tmp_path / "worker.heartbeat"
    env = {
        **os.environ,
        "AML_WORKER_HEARTBEAT_PATH": str(heartbeat),
        "AML_WORKER_HEARTBEAT_INTERVAL": "0.1",
    }
    proc = subprocess.Popen([sys.executable, "-m", "aml", "worker"], env=env, cwd=tmp_path)
    try:
        assert _wait_for(heartbeat.exists, timeout=15)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=5) == 0
    finally:
        proc.kill()
