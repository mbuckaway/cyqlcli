# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Challenge read accessors (official ``challenges`` / ``challengeById`` /
``challengeScores``)."""

from __future__ import annotations

from collections.abc import Iterator

from cyql.client import CyqlClient
from cyql.models import Challenge, ChallengeScore
from cyql.resources._pagination import DEFAULT_PAGE_SIZE, fetch_paginated

__all__ = ["fetch_challenge_by_id", "fetch_challenge_scores", "fetch_challenges"]

_CHALLENGE_FIELDS = (
    "id title description rules scoringCriteria prizes scoreType startDate endDate "
    "onlyStravaVerifiedRides model participantCount iconUrl imageUrl"
)

_CHALLENGE_SCORE_FIELDS = "memberId memberName score rank rideCount"

CHALLENGES_QUERY = f"""
query Challenges($page: Int, $pageSize: Int, $search: String) {{
  challenges(page: $page, pageSize: $pageSize, search: $search) {{
    items {{ {_CHALLENGE_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""

CHALLENGE_BY_ID_QUERY = f"""
query ChallengeById($challengeId: UUID!) {{
  challengeById(challengeId: $challengeId) {{ {_CHALLENGE_FIELDS} }}
}}
"""

CHALLENGE_SCORES_QUERY = f"""
query ChallengeScores($challengeId: UUID!, $page: Int, $pageSize: Int, $search: String) {{
  challengeScores(
    challengeId: $challengeId, page: $page, pageSize: $pageSize, search: $search
  ) {{
    items {{ {_CHALLENGE_SCORE_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""


def fetch_challenges(
    client: CyqlClient,
    *,
    search: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[Challenge]:
    """Yield club challenges, optionally filtered by a search term."""
    return fetch_paginated(
        client, CHALLENGES_QUERY, "challenges", Challenge, {"search": search}, page_size=page_size
    )


def fetch_challenge_by_id(client: CyqlClient, challenge_id: str) -> Challenge | None:
    """Return a single challenge by id, or ``None`` if it does not exist."""
    data = client.execute(CHALLENGE_BY_ID_QUERY, {"challengeId": challenge_id})
    challenge = data.get("challengeById")
    return Challenge.model_validate(challenge) if challenge else None


def fetch_challenge_scores(
    client: CyqlClient,
    challenge_id: str,
    *,
    search: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[ChallengeScore]:
    """Yield a challenge's scores, optionally filtered by a search term."""
    return fetch_paginated(
        client,
        CHALLENGE_SCORES_QUERY,
        "challengeScores",
        ChallengeScore,
        {"challengeId": challenge_id, "search": search},
        page_size=page_size,
    )
