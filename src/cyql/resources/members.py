# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Member read accessors (official ``members`` / ``memberById``).

NOTE: per-member detail is for CLI/admin use only. The Discord bot must never
import this module; it reports member *counts* via ``clubStats`` instead.
"""

from __future__ import annotations

from collections.abc import Iterator

from cyql.client import CyqlClient
from cyql.models import ClubMemberStatus, Member
from cyql.resources._pagination import DEFAULT_PAGE_SIZE, fetch_paginated

__all__ = ["fetch_member_by_id", "fetch_members"]

_MEMBER_FIELDS = "id firstName lastName email status memberSinceUtc isAdmin isRoadCaptain"

MEMBERS_QUERY = f"""
query Members($page: Int, $pageSize: Int, $search: String, $memberStatus: ClubMemberStatus) {{
  members(page: $page, pageSize: $pageSize, search: $search, memberStatus: $memberStatus) {{
    items {{ {_MEMBER_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""

MEMBER_BY_ID_QUERY = f"""
query MemberById($memberId: UUID!) {{
  memberById(memberId: $memberId) {{ {_MEMBER_FIELDS} }}
}}
"""


def fetch_members(
    client: CyqlClient,
    *,
    search: str | None = None,
    status: ClubMemberStatus | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[Member]:
    """Yield club members, optionally filtered by a search term and/or status."""
    return fetch_paginated(
        client,
        MEMBERS_QUERY,
        "members",
        Member,
        {"search": search, "memberStatus": status},
        page_size=page_size,
    )


def fetch_member_by_id(client: CyqlClient, member_id: str) -> Member | None:
    """Return a single member by id, or ``None`` if it does not exist."""
    data = client.execute(MEMBER_BY_ID_QUERY, {"memberId": member_id})
    member = data.get("memberById")
    return Member.model_validate(member) if member else None
