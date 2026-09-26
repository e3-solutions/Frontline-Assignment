"""Evaluation tests fail closed on accidental network access."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_live_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("Live network access is forbidden in the offline evaluation suite")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
