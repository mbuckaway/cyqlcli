# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Event read accessors (official ``events`` / ``eventById``)."""

from __future__ import annotations

from collections.abc import Iterator

from cyql.client import CyqlClient
from cyql.models import Event
from cyql.resources._pagination import DEFAULT_PAGE_SIZE, fetch_paginated

__all__ = ["fetch_event_by_id", "fetch_events"]

_EVENT_FIELDS = "id title description startDateTime endTime location imageUrl pdfTitle pdfUrl"

EVENTS_QUERY = f"""
query Events($page: Int, $pageSize: Int, $fetchType: String, $search: String) {{
  events(page: $page, pageSize: $pageSize, fetchType: $fetchType, search: $search) {{
    items {{ {_EVENT_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""

EVENT_BY_ID_QUERY = f"""
query EventById($eventId: UUID!) {{
  eventById(eventId: $eventId) {{ {_EVENT_FIELDS} }}
}}
"""


def fetch_events(
    client: CyqlClient,
    *,
    search: str | None = None,
    fetch_type: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[Event]:
    """Yield club events, optionally filtered by a search term and/or fetch type."""
    return fetch_paginated(
        client,
        EVENTS_QUERY,
        "events",
        Event,
        {"search": search, "fetchType": fetch_type},
        page_size=page_size,
    )


def fetch_event_by_id(client: CyqlClient, event_id: str) -> Event | None:
    """Return a single event by id, or ``None`` if it does not exist."""
    data = client.execute(EVENT_BY_ID_QUERY, {"eventId": event_id})
    event = data.get("eventById")
    return Event.model_validate(event) if event else None
