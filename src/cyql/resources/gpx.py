# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""GPX route read accessors (official ``gpxRoutes`` / ``gpxRouteById``)."""

from __future__ import annotations

from collections.abc import Iterator

from cyql.client import CyqlClient
from cyql.models import GpxRoute
from cyql.resources._pagination import DEFAULT_PAGE_SIZE, fetch_paginated

__all__ = ["fetch_gpx_route_by_id", "fetch_gpx_routes"]

_GPX_ROUTE_FIELDS = (
    "id title description distance altitude createdAt updatedAt downloadUrl isPublic"
)

GPX_ROUTES_QUERY = f"""
query GpxRoutes($page: Int, $pageSize: Int, $search: String) {{
  gpxRoutes(page: $page, pageSize: $pageSize, search: $search) {{
    items {{ {_GPX_ROUTE_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""

GPX_ROUTE_BY_ID_QUERY = f"""
query GpxRouteById($gpxRouteId: UUID!) {{
  gpxRouteById(gpxRouteId: $gpxRouteId) {{ {_GPX_ROUTE_FIELDS} }}
}}
"""


def fetch_gpx_routes(
    client: CyqlClient,
    *,
    search: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[GpxRoute]:
    """Yield GPX routes, optionally filtered by a search term."""
    return fetch_paginated(
        client,
        GPX_ROUTES_QUERY,
        "gpxRoutes",
        GpxRoute,
        {"search": search},
        page_size=page_size,
    )


def fetch_gpx_route_by_id(client: CyqlClient, gpx_route_id: str) -> GpxRoute | None:
    """Return a single GPX route by id, or ``None`` if it does not exist."""
    data = client.execute(GPX_ROUTE_BY_ID_QUERY, {"gpxRouteId": gpx_route_id})
    route = data.get("gpxRouteById")
    return GpxRoute.model_validate(route) if route else None
