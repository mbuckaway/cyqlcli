# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Named specialized queries for the ``cyql query`` command.

Importing this package registers every query module below.
"""

from __future__ import annotations

from cyql.queries.active_ride_leaders import ACTIVE_RIDE_LEADERS
from cyql.queries.registry import QUERIES, QuerySpec, get_query, list_queries, register

__all__ = [
    "ACTIVE_RIDE_LEADERS",
    "QUERIES",
    "QuerySpec",
    "get_query",
    "list_queries",
    "register",
]
