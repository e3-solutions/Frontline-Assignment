"""Shared offline configuration and network tripwire for evaluation scenarios."""

from __future__ import annotations

import os
import socket
from contextlib import contextmanager
from unittest.mock import patch


DUMMY_CONFIGURATION = {
    "SUPABASE_URL": "http://test-suite.local",
    "SUPABASE_SERVICE_ROLE_KEY": "test-key",
    "KCH_QUOTE_CLIENT_ID": "not-used",
    "KCH_QUOTE_CLIENT_SECRET": "not-used",
    "KCH_QUOTE_SCOPE": "not-used",
}


@contextmanager
def offline_guard():
    """Provide inert configuration and fail any attempted socket connection."""
    with (
        patch.dict(os.environ, DUMMY_CONFIGURATION, clear=False),
        patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("network access is blocked in offline evals"),
        ),
        patch(
            "socket.create_connection",
            side_effect=AssertionError("network access is blocked in offline evals"),
        ),
    ):
        yield
