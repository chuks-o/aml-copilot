"""RabbitMQ container: the app user can log in, definitions are imported, messages flow."""

import json

import httpx
import pika

from tests.fixtures.rabbitmq import DEFINITIONS, RabbitMQ


def _get(rabbitmq: RabbitMQ, path: str) -> httpx.Response:
    return httpx.get(f"{rabbitmq.management_url}{path}", auth=(rabbitmq.user, rabbitmq.password))


def test_app_user_exists_with_the_default_vhost(rabbitmq: RabbitMQ) -> None:
    # The T03 bug: importing definitions at boot skipped creating this user and vhost.
    assert _get(rabbitmq, "/api/whoami").json()["name"] == rabbitmq.user
    assert "/" in {vhost["name"] for vhost in _get(rabbitmq, "/api/vhosts").json()}


def test_definitions_file_is_imported(rabbitmq: RabbitMQ) -> None:
    expected = json.loads(DEFINITIONS.read_text())
    broker = _get(rabbitmq, "/api/definitions").json()

    for kind in ("queues", "exchanges", "bindings"):
        wanted = {json.dumps(item, sort_keys=True) for item in expected.get(kind, [])}
        present = {json.dumps(item, sort_keys=True) for item in broker.get(kind, [])}
        assert wanted <= present, kind


def test_publish_and_consume_round_trip(rabbitmq: RabbitMQ) -> None:
    params = pika.ConnectionParameters(
        host=rabbitmq.host,
        port=rabbitmq.amqp_port,
        credentials=pika.PlainCredentials(rabbitmq.user, rabbitmq.password),
    )
    with pika.BlockingConnection(params) as connection:
        channel = connection.channel()
        queue = channel.queue_declare(queue="", exclusive=True).method.queue
        channel.basic_publish(exchange="", routing_key=queue, body=b"investigate case 1")

        _, _, body = channel.basic_get(queue, auto_ack=True)

    assert body == b"investigate case 1"
