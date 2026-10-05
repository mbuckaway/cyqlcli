# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Unit tests for the specialized-query registry."""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest

from cyql.errors import CyqlError
from cyql.queries import QUERIES, QuerySpec, get_query, list_queries, register

ACTIVE_RIDE_LEADERS_DESCRIPTION = (
    "Distinct ride leaders listed on rides in the current year"
)


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    """Restore the global registry after each test so registrations do not leak."""
    snapshot = dict(QUERIES)
    yield
    QUERIES.clear()
    QUERIES.update(snapshot)


def _spec(name: str) -> QuerySpec:
    return QuerySpec(name=name, description="demo", run=lambda client: [])


def test_register_adds_spec_and_returns_it() -> None:
    spec = _spec("unit-test-registered")

    returned = register(spec)

    assert returned is spec
    assert get_query("unit-test-registered") is spec


def test_list_queries_includes_registered_spec() -> None:
    spec = register(_spec("unit-test-listed"))

    assert spec in list_queries()


def test_get_query_returns_spec_by_name() -> None:
    register(_spec("unit-test-lookup"))

    assert get_query("unit-test-lookup").name == "unit-test-lookup"


def test_get_query_unknown_name_raises_cyql_error() -> None:
    with pytest.raises(CyqlError, match=re.escape("unknown query: nope")):
        get_query("nope")


def test_active_ride_leaders_is_registered() -> None:
    assert get_query("active-ride-leaders").name == "active-ride-leaders"


def test_active_ride_leaders_has_expected_description() -> None:
    assert (
        get_query("active-ride-leaders").description == ACTIVE_RIDE_LEADERS_DESCRIPTION
    )


def test_active_ride_leaders_run_raises_not_yet_available() -> None:
    spec = get_query("active-ride-leaders")

    with pytest.raises(
        CyqlError,
        match=re.escape(
            "query 'active-ride-leaders' is not yet available: "
            "the internal API ride-leader schema has not been captured"
        ),
    ):
        spec.run(None)  # type: ignore[arg-type]
