# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Registry of the named specialized queries behind the ``query`` command."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from cyql.client import CyqlClient
from cyql.errors import CyqlError

__all__ = ["QUERIES", "QuerySpec", "get_query", "list_queries", "register"]


@dataclass(frozen=True)
class QuerySpec:
    """A named query: its description and the callable that runs it."""

    name: str
    description: str
    run: Callable[[CyqlClient], list[BaseModel]]


QUERIES: dict[str, QuerySpec] = {}


def register(spec: QuerySpec) -> QuerySpec:
    """Add ``spec`` to the registry and return it."""
    QUERIES[spec.name] = spec
    return spec


def list_queries() -> list[QuerySpec]:
    """Return every registered query, in registration order."""
    return list(QUERIES.values())


def get_query(name: str) -> QuerySpec:
    """Return the query named ``name``.

    Raises:
        CyqlError: if no query is registered under ``name``.
    """
    try:
        return QUERIES[name]
    except KeyError as exc:
        raise CyqlError(f"unknown query: {name}") from exc
