# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Internal-API ride access (undocumented ``fetchRides`` query).

The internal endpoint needs a Bearer session token and returns a
``skip``/``take`` paged result. This module owns the captured dashboard
document and its paging loop.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from cyql.client import CyqlClient
from cyql.models import InternalRide
from cyql.resources._pagination import DEFAULT_PAGE_SIZE

__all__ = ["fetch_internal_rides"]

# The operation below is the captured dashboard document. Only line breaks were
# added (GraphQL ignores insignificant whitespace); every token is unchanged.
INTERNAL_RIDES_QUERY = (
    "query getRideItems($clubId: UUID, $skip: Int = null, $take: Int = null, "
    "$sort: [BaseRideSortInput!] = null, $showInactiveItems: Boolean = true, "
    "$filter: FilterInput = null) {\n"
    "  fetchRides(skip: $skip, take: $take, clubId: $clubId, order: $sort, "
    "showInactiveItems: $showInactiveItems, filter: $filter) {\n"
    "    totalCount\n"
    "    pageInfo { hasNextPage hasPreviousPage }\n"
    "    items { id title startTimeUtc roadCaptains { id firstName lastName email } }\n"
    "  }\n"
    "}\n"
)

# The dashboard sends RFC-1123 dates in UTC, e.g. "Mon, 05 Oct 2026 04:00:00 GMT".
_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"


def fetch_internal_rides(
    client: CyqlClient,
    club_id: str,
    *,
    year: int | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[InternalRide]:
    """Yield the rides of ``club_id`` in ``year`` (UTC), newest first.

    Args:
        client: the client whose internal auth carries the session token.
        club_id: the club whose rides to read.
        year: calendar year to filter on. Defaults to the current UTC year.
        page_size: rides to request per page.
    """
    effective_year = datetime.now(UTC).year if year is None else year
    min_date = datetime(effective_year, 1, 1, tzinfo=UTC).strftime(_DATE_FORMAT)
    max_date = datetime(effective_year, 12, 31, 23, 59, 59, tzinfo=UTC).strftime(
        _DATE_FORMAT
    )

    skip = 0
    while True:
        data = client.execute(
            INTERNAL_RIDES_QUERY,
            {
                "clubId": club_id,
                "skip": skip,
                "take": page_size,
                "sort": {"startTimeUtc": "DESC"},
                "showInactiveItems": True,
                "filter": {
                    "rideTypes": [],
                    "labelIds": [],
                    "minDate": min_date,
                    "maxDate": max_date,
                },
            },
            internal=True,
        )
        result = data["fetchRides"]
        for item in result["items"]:
            yield InternalRide.model_validate(item)
        if not result["pageInfo"]["hasNextPage"]:
            return
        skip += page_size
