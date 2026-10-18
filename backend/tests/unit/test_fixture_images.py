"""Test containers run the same images as the Compose stack."""

from pathlib import Path
from typing import Any

import yaml

from tests.fixtures.postgres import POSTGRES_IMAGE
from tests.fixtures.rabbitmq import RABBITMQ_IMAGE

COMPOSE = Path(__file__).resolve().parents[3] / "infra" / "docker-compose.yml"


def test_fixture_images_match_compose() -> None:
    services: dict[str, Any] = yaml.safe_load(COMPOSE.read_text())["services"]

    assert services["postgres"]["image"] == POSTGRES_IMAGE
    assert services["rabbitmq"]["image"] == RABBITMQ_IMAGE
