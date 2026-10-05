# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Ride read accessors (official ``rides`` / ``rideById``)."""

from __future__ import annotations

from collections.abc import Iterator

from cyql.client import CyqlClient
from cyql.models import Ride, RideMember
from cyql.resources._pagination import DEFAULT_PAGE_SIZE, fetch_paginated

__all__ = [
    "fetch_next_ride",
    "fetch_ride_by_id",
    "fetch_ride_participants",
    "fetch_rides",
]

_RIDE_FIELDS = (
    "id title description startTime rideType location hasStops distance altitude "
    "averageSpeed duration isPublic maxGroupSize shareUrl gpxUrl imageUrl"
)

_RIDE_MEMBER_FIELDS = "memberId firstName lastName status waiverAccepted"

RIDES_QUERY = f"""
query Rides($page: Int, $pageSize: Int, $isUpcoming: Boolean, $search: String) {{
  rides(page: $page, pageSize: $pageSize, isUpcoming: $isUpcoming, search: $search) {{
    items {{ {_RIDE_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""

RIDE_BY_ID_QUERY = f"""
query RideById($rideId: UUID!) {{
  rideById(rideId: $rideId) {{ {_RIDE_FIELDS} }}
}}
"""

RIDE_PARTICIPANTS_QUERY = f"""
query RideParticipants($rideId: UUID!, $page: Int, $pageSize: Int, $search: String) {{
  rideParticipants(rideId: $rideId, page: $page, pageSize: $pageSize, search: $search) {{
    items {{ {_RIDE_MEMBER_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""


def fetch_rides(
    client: CyqlClient,
    *,
    is_upcoming: bool | None = None,
    search: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[Ride]:
    """Yield rides, optionally filtered to upcoming and/or a search term."""
    return fetch_paginated(
        client,
        RIDES_QUERY,
        "rides",
        Ride,
        {"isUpcoming": is_upcoming, "search": search},
        page_size=page_size,
    )


def fetch_next_ride(client: CyqlClient) -> Ride | None:
    """Return the single next upcoming ride, or ``None`` if there are none."""
    data = client.execute(
        RIDES_QUERY, {"page": 1, "pageSize": 1, "isUpcoming": True, "search": None}
    )
    items = data["rides"]["items"]
    return Ride.model_validate(items[0]) if items else None


def fetch_ride_by_id(client: CyqlClient, ride_id: str) -> Ride | None:
    """Return a single ride by id, or ``None`` if it does not exist."""
    data = client.execute(RIDE_BY_ID_QUERY, {"rideId": ride_id})
    ride = data.get("rideById")
    return Ride.model_validate(ride) if ride else None


def fetch_ride_participants(
    client: CyqlClient,
    ride_id: str,
    *,
    search: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[RideMember]:
    """Yield the participants of a ride, optionally filtered by a search term."""
    return fetch_paginated(
        client,
        RIDE_PARTICIPANTS_QUERY,
        "rideParticipants",
        RideMember,
        {"rideId": ride_id, "search": search},
        page_size=page_size,
    )
