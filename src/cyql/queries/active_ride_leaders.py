# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""The ``active-ride-leaders`` query — distinct ride leaders for the year.

It reads the internal ``fetchRides`` ``roadCaptains`` field with the Bearer
session token, then counts how many rides in the current UTC year each person
led.
"""

from __future__ import annotations

from pydantic import BaseModel

from cyql.client import CyqlClient
from cyql.config import load_settings
from cyql.errors import CyqlError
from cyql.models import InternalMember, RideLeader
from cyql.queries.registry import QuerySpec, register
from cyql.resources.internal_rides import fetch_internal_rides

__all__ = ["ACTIVE_RIDE_LEADERS"]

_CLUB_ID_MISSING = (
    "club_id is not set; run scripts/get-session-token.py or add club_id to the config"
)


def _run(client: CyqlClient) -> list[BaseModel]:
    """Return the distinct ride leaders of rides in the current UTC year.

    Raises:
        CyqlError: if no ``club_id`` is configured.
        MissingCredentialError: if the client has no internal auth.
    """
    club_id = load_settings().club_id
    if not club_id:
        raise CyqlError(_CLUB_ID_MISSING)

    counts: dict[str, int] = {}
    profiles: dict[str, InternalMember] = {}
    for ride in fetch_internal_rides(client, club_id):
        for captain in ride.road_captains:
            profiles.setdefault(captain.id, captain)
            counts[captain.id] = counts.get(captain.id, 0) + 1

    ordered_ids = sorted(
        counts,
        key=lambda member_id: (
            (profiles[member_id].last_name or "").lower(),
            (profiles[member_id].first_name or "").lower(),
            member_id,
        ),
    )
    leaders: list[BaseModel] = [
        RideLeader(
            member_id=member_id,
            first_name=profiles[member_id].first_name,
            last_name=profiles[member_id].last_name,
            email=profiles[member_id].email,
            rides_led=counts[member_id],
        )
        for member_id in ordered_ids
    ]
    return leaders


ACTIVE_RIDE_LEADERS = register(
    QuerySpec(
        name="active-ride-leaders",
        description="Distinct ride leaders listed on rides in the current year",
        run=_run,
    )
)
