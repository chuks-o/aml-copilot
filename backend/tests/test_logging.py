import json
import logging

import pytest
import structlog

from aml.common import configure_logging, get_logger


def test_emits_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("test-service", "INFO")

    structlog.contextvars.bind_contextvars(case_id="C-1")
    get_logger("t").info("case_opened", alerts=3)
    logging.getLogger("uvicorn.error").warning("from stdlib")

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0]["event"] == "case_opened"
    assert lines[0]["service"] == "test-service"
    assert lines[0]["case_id"] == "C-1"
    assert lines[0]["alerts"] == 3
    assert lines[0]["level"] == "info"
    assert lines[1]["event"] == "from stdlib"
    assert lines[1]["logger"] == "uvicorn.error"
