# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""The ``active-ride-leaders`` query — scaffolded until the internal schema exists.

The real query reads the internal ``fetchRides`` ``roadCaptains`` field, which is
not yet captured. Until it is, the runner fails with a clear message instead of
guessing.
"""

from __future__ import annotations

from pydantic import BaseModel

from cyql.client import CyqlClient
from cyql.errors import CyqlError
from cyql.queries.registry import QuerySpec, register

__all__ = ["ACTIVE_RIDE_LEADERS"]

_NOT_AVAILABLE = (
    "query 'active-ride-leaders' is not yet available: "
    "the internal API ride-leader schema has not been captured"
)


def _run(client: CyqlClient) -> list[BaseModel]:
    """Fail with a clear message until the internal query is captured."""
    raise CyqlError(_NOT_AVAILABLE)


ACTIVE_RIDE_LEADERS = register(
    QuerySpec(
        name="active-ride-leaders",
        description="Distinct ride leaders listed on rides in the current year",
        run=_run,
    )
)
