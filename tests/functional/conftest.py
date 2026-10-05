# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Functional-test fixtures: a real local GraphQL service over HTTP."""

import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from wsgiref.simple_server import make_server

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from mockserver.server import make_app

EXPECTED_KEY = "functional-test-key"


@pytest.fixture
def mock_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Start the mock GraphQL server in a background thread; yield its endpoint."""
    server = make_server("127.0.0.1", 0, make_app(EXPECTED_KEY))  # type: ignore[arg-type]
    endpoint = f"http://127.0.0.1:{server.server_port}/graphql"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("CYQL_API_KEY", EXPECTED_KEY)
    monkeypatch.setenv("CYQL_OFFICIAL_ENDPOINT", endpoint)
    try:
        yield endpoint
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
