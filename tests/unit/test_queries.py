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
from typing import Any

import httpx
import pytest
import respx

import cyql.queries.active_ride_leaders as active_ride_leaders
from cyql.auth import ApiKeyAuth, SessionTokenAuth
from cyql.client import CyqlClient
from cyql.config import Settings
from cyql.errors import CyqlError, MissingCredentialError
from cyql.queries import QUERIES, QuerySpec, get_query, list_queries, register

ACTIVE_RIDE_LEADERS_DESCRIPTION = (
    "Distinct ride leaders listed on rides in the current year"
)
INTERNAL_URL = "https://api.cyql.app/graphql"
READ_URL = "https://api.cyql.app/api/graphql"


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    """Restore the global registry after each test so registrations do not leak."""
    snapshot = dict(QUERIES)
    yield
    QUERIES.clear()
    QUERIES.update(snapshot)


def _spec(name: str) -> QuerySpec:
    return QuerySpec(name=name, description="demo", run=lambda client: [])


def _client() -> CyqlClient:
    return CyqlClient(
        ApiKeyAuth(api_key="k", endpoint=READ_URL),
        internal_auth=SessionTokenAuth(token="t-456", endpoint=INTERNAL_URL),
        sleep=lambda _seconds: None,
    )


def _page(items: list[dict[str, Any]], *, has_next: bool) -> dict[str, Any]:
    return {
        "totalCount": len(items),
        "pageInfo": {"hasNextPage": has_next, "hasPreviousPage": False},
        "items": items,
    }


def _rides_response(items: list[dict[str, Any]], *, has_next: bool) -> httpx.Response:
    return httpx.Response(
        200, json={"data": {"fetchRides": _page(items, has_next=has_next)}}
    )


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


def test_active_ride_leaders_raises_when_club_id_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(active_ride_leaders, "load_settings", lambda: Settings())
    spec = get_query("active-ride-leaders")

    with _client() as client, pytest.raises(CyqlError, match=re.escape("club_id is not set")):
        spec.run(client)


@respx.mock
def test_active_ride_leaders_counts_and_dedupes_across_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        active_ride_leaders, "load_settings", lambda: Settings(club_id="club-1")
    )
    ada = {"id": "m1", "firstName": "Ada", "lastName": "Zed", "email": "ada@example.com"}
    respx.post(INTERNAL_URL).mock(
        side_effect=[
            _rides_response(
                [
                    {"id": "r1", "roadCaptains": [ada, {"id": "m2"}]},
                    {"id": "r2", "roadCaptains": [ada]},
                ],
                has_next=True,
            ),
            _rides_response(
                [
                    {
                        "id": "r3",
                        "roadCaptains": [
                            ada,
                            {"id": "m3", "firstName": "Cy"},
                            {"id": "m4", "lastName": "Adams"},
                        ],
                    },
                    {"id": "r4", "roadCaptains": [{"id": "m4", "lastName": "Adams"}]},
                ],
                has_next=False,
            ),
        ]
    )
    spec = get_query("active-ride-leaders")

    with _client() as client:
        leaders = spec.run(client)

    assert [leader.member_id for leader in leaders] == ["m2", "m3", "m4", "m1"]
    assert [leader.rides_led for leader in leaders] == [1, 1, 2, 3]
    assert leaders[-1].email == "ada@example.com"


@respx.mock
def test_active_ride_leaders_returns_empty_list_when_no_ride_has_captains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        active_ride_leaders, "load_settings", lambda: Settings(club_id="club-1")
    )
    respx.post(INTERNAL_URL).mock(
        return_value=_rides_response([{"id": "r1"}], has_next=False)
    )
    spec = get_query("active-ride-leaders")

    with _client() as client:
        leaders = spec.run(client)

    assert leaders == []


@respx.mock
def test_active_ride_leaders_propagates_missing_internal_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        active_ride_leaders, "load_settings", lambda: Settings(club_id="club-1")
    )
    read_only = CyqlClient(
        ApiKeyAuth(api_key="k", endpoint=READ_URL), sleep=lambda _seconds: None
    )
    spec = get_query("active-ride-leaders")

    with read_only, pytest.raises(MissingCredentialError, match="internal auth is required"):
        spec.run(read_only)

