"""RabbitMQ in a container, with infra/rabbitmq/definitions.json imported.

Mirrors docker-compose.yml: the broker boots without definitions (so it creates the app user
and the default vhost), then the topology is imported through the management API (0021).
"""

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from testcontainers.community.rabbitmq import RabbitMqContainer

from tests.fixtures.docker import TEST_PASSWORD, TEST_USER, require_docker

# Same image as infra/docker-compose.yml (tests/unit/test_fixture_images.py keeps them equal).
RABBITMQ_IMAGE = "rabbitmq:3-management"
DEFINITIONS = Path(__file__).resolve().parents[3] / "infra" / "rabbitmq" / "definitions.json"
USER, PASSWORD = TEST_USER, TEST_PASSWORD


@dataclass(frozen=True)
class RabbitMQ:
    host: str
    amqp_port: int
    management_url: str
    user: str
    password: str


def _wait_for_management(url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            if httpx.get(f"{url}/api/overview", auth=(USER, PASSWORD)).status_code == 200:
                return
        except httpx.TransportError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(f"RabbitMQ management API at {url} did not come up")
        time.sleep(0.5)


@pytest.fixture(scope="session")
def rabbitmq() -> Iterator[RabbitMQ]:
    require_docker()
    container = RabbitMqContainer(RABBITMQ_IMAGE, username=USER, password=PASSWORD)
    container.with_exposed_ports(15672)
    with container:
        host = container.get_container_host_ip()
        management_url = f"http://{host}:{container.get_exposed_port(15672)}"
        _wait_for_management(management_url)
        response = httpx.post(
            f"{management_url}/api/definitions",
            json=json.loads(DEFINITIONS.read_text()),
            auth=(USER, PASSWORD),
        )
        response.raise_for_status()
        yield RabbitMQ(
            host=host,
            amqp_port=int(container.get_exposed_port(5672)),
            management_url=management_url,
            user=USER,
            password=PASSWORD,
        )
