"""Contract test: Schemathesis against a live server, with openapi.yaml as the spec.

Opt-in (``-m contract``, ``make contract``) because it sends thousands of requests.
Config (checks, seed, example budget) is in ``schemathesis.toml``.
"""

import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from aml.api.app import app

BACKEND = Path(__file__).resolve().parents[1]
SCHEMATHESIS = Path(sys.executable).parent / "schemathesis"


@pytest.fixture(scope="module")
def live_server() -> Iterator[str]:
    """The real app on a free local port, served by uvicorn in a background thread."""
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_config=None, access_log=False)
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.mark.contract
def test_api_conforms_to_openapi(live_server: str) -> None:
    command = [str(SCHEMATHESIS), "run", "openapi.yaml", "--url", live_server]
    if seed := os.environ.get("SCHEMATHESIS_SEED"):
        command += ["--seed", seed]
    # Output goes straight to the terminal (pytest -s), so the summary is visible.
    result = subprocess.run(command, cwd=BACKEND, check=False)  # noqa: S603

    assert result.returncode == 0, "Schemathesis found contract violations (see output above)"
