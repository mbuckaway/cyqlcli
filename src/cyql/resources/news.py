# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""News read accessors (official ``news`` / ``newsById``)."""

from __future__ import annotations

from collections.abc import Iterator

from cyql.client import CyqlClient
from cyql.models import News
from cyql.resources._pagination import DEFAULT_PAGE_SIZE, fetch_paginated

__all__ = ["fetch_news", "fetch_news_by_id"]

_NEWS_FIELDS = "id title description publicationDate editDate imageUrl pdfTitle pdfUrl"

NEWS_QUERY = f"""
query News($page: Int, $pageSize: Int, $search: String) {{
  news(page: $page, pageSize: $pageSize, search: $search) {{
    items {{ {_NEWS_FIELDS} }}
    totalCount
    page
    pageSize
    hasNextPage
  }}
}}
"""

NEWS_BY_ID_QUERY = f"""
query NewsById($newsId: UUID!) {{
  newsById(newsId: $newsId) {{ {_NEWS_FIELDS} }}
}}
"""


def fetch_news(
    client: CyqlClient,
    *,
    search: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[News]:
    """Yield club news articles, optionally filtered by a search term."""
    return fetch_paginated(
        client, NEWS_QUERY, "news", News, {"search": search}, page_size=page_size
    )


def fetch_news_by_id(client: CyqlClient, news_id: str) -> News | None:
    """Return a single news article by id, or ``None`` if it does not exist."""
    data = client.execute(NEWS_BY_ID_QUERY, {"newsId": news_id})
    article = data.get("newsById")
    return News.model_validate(article) if article else None
