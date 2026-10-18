"""Tests can't reach beyond this machine (pytest-socket, configured in pyproject.toml)."""

import socket

import pytest
from pytest_socket import SocketConnectBlockedError


@pytest.mark.filterwarnings("ignore:A test tried to use socket:UserWarning")  # the expected block
def test_connecting_to_the_internet_is_blocked() -> None:
    with pytest.raises(SocketConnectBlockedError), socket.create_connection(("1.1.1.1", 443)):
        pass


def test_localhost_is_allowed() -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        with socket.create_connection(server.getsockname()):
            pass
