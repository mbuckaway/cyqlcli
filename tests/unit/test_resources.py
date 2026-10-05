# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Tests for the read-only resource accessors (respx-mocked official API)."""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from cyql.auth import ApiKeyAuth, SessionTokenAuth
from cyql.client import CyqlClient
from cyql.errors import MissingCredentialError
from cyql.models import ClubMemberStatus, RankingModel, RankingScoreType
from cyql.resources.challenges import (
    fetch_challenge_by_id,
    fetch_challenge_scores,
    fetch_challenges,
)
from cyql.resources.club import fetch_club_info, fetch_club_stats
from cyql.resources.events import fetch_event_by_id, fetch_events
from cyql.resources.gpx import fetch_gpx_route_by_id, fetch_gpx_routes
from cyql.resources.internal_rides import fetch_internal_rides
from cyql.resources.members import fetch_member_by_id, fetch_members
from cyql.resources.news import fetch_news, fetch_news_by_id
from cyql.resources.rides import (
    fetch_next_ride,
    fetch_ride_by_id,
    fetch_ride_participants,
    fetch_rides,
)

URL = "https://api.cyql.app/api/graphql"
INTERNAL_URL = "https://api.cyql.app/graphql"


def _client() -> CyqlClient:
    return CyqlClient(ApiKeyAuth(api_key="k", endpoint=URL), sleep=lambda _seconds: None)


def _internal_client() -> CyqlClient:
    return CyqlClient(
        ApiKeyAuth(api_key="k", endpoint=URL),
        internal_auth=SessionTokenAuth(token="t-456", endpoint=INTERNAL_URL),
        sleep=lambda _seconds: None,
    )


def _page(items: list[dict[str, Any]], *, has_next: bool) -> dict[str, Any]:
    return {
        "items": items,
        "totalCount": 99,
        "page": 1,
        "pageSize": 50,
        "hasNextPage": has_next,
    }


def _variables(route: respx.Route) -> dict[str, Any]:
    return json.loads(route.calls.last.request.content)["variables"]


def _variables_at(route: respx.Route, index: int) -> dict[str, Any]:
    return json.loads(route.calls[index].request.content)["variables"]


def _rides_page(items: list[dict[str, Any]], *, has_next: bool) -> dict[str, Any]:
    return {
        "totalCount": len(items),
        "pageInfo": {"hasNextPage": has_next, "hasPreviousPage": False},
        "items": items,
    }


@respx.mock
def test_fetch_club_stats_parses_payload() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "clubStats": {
                        "totalRides": 3,
                        "memberCount": 42,
                        "totalKilometers": 100.5,
                        "totalAdmins": 2,
                    }
                }
            },
        )
    )

    with _client() as client:
        stats = fetch_club_stats(client)

    assert stats.member_count == 42
    assert stats.total_kilometers == 100.5


@respx.mock
def test_fetch_club_info_parses_payload() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"clubInfo": {"title": "GORBA", "city": "Guelph"}}}
        )
    )

    with _client() as client:
        info = fetch_club_info(client)

    assert info.title == "GORBA"
    assert info.city == "Guelph"


@respx.mock
def test_fetch_rides_paginates_across_pages() -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": {"rides": _page([{"id": "r1"}], has_next=True)}}),
            httpx.Response(200, json={"data": {"rides": _page([{"id": "r2"}], has_next=False)}}),
        ]
    )

    with _client() as client:
        rides = list(fetch_rides(client))

    assert [ride.id for ride in rides] == ["r1", "r2"]
    assert route.call_count == 2
    assert _variables(route)["page"] == 2


@pytest.mark.parametrize(
    ("page_size", "expected"),
    [(1, 1), (50, 50), (100, 100), (101, 100), (500, 100)],
    ids=["min", "default", "max", "max+1", "far-over"],
)
@respx.mock
def test_fetch_rides_clamps_page_size_to_api_limit(page_size: int, expected: int) -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"rides": _page([], has_next=False)}})
    )

    with _client() as client:
        list(fetch_rides(client, page_size=page_size))

    assert _variables(route)["pageSize"] == expected


@respx.mock
def test_fetch_next_ride_returns_first_item() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"rides": {"items": [{"id": "r1", "title": "Next"}]}}}
        )
    )

    with _client() as client:
        ride = fetch_next_ride(client)

    assert ride is not None
    assert ride.id == "r1"


@respx.mock
def test_fetch_next_ride_returns_none_when_empty() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"rides": {"items": []}}})
    )

    with _client() as client:
        ride = fetch_next_ride(client)

    assert ride is None


@respx.mock
def test_fetch_ride_by_id_returns_ride() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"rideById": {"id": "r9", "title": "X"}}})
    )

    with _client() as client:
        ride = fetch_ride_by_id(client, "r9")

    assert ride is not None
    assert ride.id == "r9"


@respx.mock
def test_fetch_ride_by_id_returns_none_when_missing() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"data": {"rideById": None}}))

    with _client() as client:
        ride = fetch_ride_by_id(client, "missing")

    assert ride is None


@respx.mock
def test_fetch_ride_participants_yields_participants() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "rideParticipants": _page(
                        [
                            {
                                "memberId": "m1",
                                "firstName": "Ada",
                                "lastName": "Byron",
                                "status": "YES",
                                "waiverAccepted": True,
                            }
                        ],
                        has_next=False,
                    )
                }
            },
        )
    )

    with _client() as client:
        participants = list(fetch_ride_participants(client, "r1"))

    assert participants[0].member_id == "m1"
    assert participants[0].first_name == "Ada"
    assert participants[0].waiver_accepted is True


@respx.mock
def test_fetch_ride_participants_sends_ride_id_and_search_variables() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"rideParticipants": _page([], has_next=False)}}
        )
    )

    with _client() as client:
        list(fetch_ride_participants(client, "r1", search="ada"))

    assert _variables(route)["rideId"] == "r1"
    assert _variables(route)["search"] == "ada"


@respx.mock
def test_fetch_members_yields_members() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "members": _page(
                        [{"id": "m1", "firstName": "Ada", "isAdmin": True}], has_next=False
                    )
                }
            },
        )
    )

    with _client() as client:
        members = list(fetch_members(client))

    assert members[0].id == "m1"
    assert members[0].is_admin is True


@respx.mock
def test_fetch_members_sends_member_status_variable() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"members": _page([], has_next=False)}})
    )

    with _client() as client:
        list(fetch_members(client, status=ClubMemberStatus.APPROVED))

    assert _variables(route)["memberStatus"] == "APPROVED"


@respx.mock
def test_fetch_members_defaults_member_status_to_none() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"members": _page([], has_next=False)}})
    )

    with _client() as client:
        list(fetch_members(client))

    assert _variables(route)["memberStatus"] is None


@respx.mock
def test_fetch_member_by_id_returns_member() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"memberById": {"id": "m9", "firstName": "Ada", "status": "APPROVED"}}},
        )
    )

    with _client() as client:
        member = fetch_member_by_id(client, "m9")

    assert member is not None
    assert member.first_name == "Ada"
    assert member.status is ClubMemberStatus.APPROVED


@respx.mock
def test_fetch_member_by_id_returns_none_when_missing() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"data": {"memberById": None}}))

    with _client() as client:
        member = fetch_member_by_id(client, "missing")

    assert member is None


@respx.mock
def test_fetch_events_yields_events() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {"events": _page([{"id": "e1", "title": "Festival"}], has_next=False)}
            },
        )
    )

    with _client() as client:
        events = list(fetch_events(client))

    assert events[0].title == "Festival"


@respx.mock
def test_fetch_events_sends_fetch_type_variable() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"events": _page([], has_next=False)}})
    )

    with _client() as client:
        list(fetch_events(client, fetch_type="upcoming"))

    assert _variables(route)["fetchType"] == "upcoming"


@respx.mock
def test_fetch_event_by_id_returns_event() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"eventById": {"id": "e9", "title": "Festival", "pdfUrl": "u"}}},
        )
    )

    with _client() as client:
        event = fetch_event_by_id(client, "e9")

    assert event is not None
    assert event.title == "Festival"
    assert event.pdf_url == "u"


@respx.mock
def test_fetch_event_by_id_returns_none_when_missing() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"data": {"eventById": None}}))

    with _client() as client:
        event = fetch_event_by_id(client, "missing")

    assert event is None


@respx.mock
def test_fetch_news_yields_news() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"news": _page([{"id": "n1", "title": "Trail open"}], has_next=False)}},
        )
    )

    with _client() as client:
        news = list(fetch_news(client))

    assert news[0].title == "Trail open"


@respx.mock
def test_fetch_news_by_id_returns_article() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"newsById": {"id": "n9", "title": "Trail open", "imageUrl": "i"}}},
        )
    )

    with _client() as client:
        article = fetch_news_by_id(client, "n9")

    assert article is not None
    assert article.title == "Trail open"
    assert article.image_url == "i"


@respx.mock
def test_fetch_news_by_id_returns_none_when_missing() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"data": {"newsById": None}}))

    with _client() as client:
        article = fetch_news_by_id(client, "missing")

    assert article is None


@respx.mock
def test_fetch_challenges_yields_challenges() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "challenges": _page(
                        [
                            {
                                "id": "c1",
                                "title": "Summer Distance",
                                "scoreType": "DISTANCE",
                                "model": "PUBLIC",
                            }
                        ],
                        has_next=False,
                    )
                }
            },
        )
    )

    with _client() as client:
        challenges = list(fetch_challenges(client))

    assert challenges[0].title == "Summer Distance"
    assert challenges[0].score_type is RankingScoreType.DISTANCE
    assert challenges[0].model is RankingModel.PUBLIC


@respx.mock
def test_fetch_challenge_by_id_returns_challenge() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"challengeById": {"id": "c9", "title": "Summer", "model": "CLUB"}}},
        )
    )

    with _client() as client:
        challenge = fetch_challenge_by_id(client, "c9")

    assert challenge is not None
    assert challenge.title == "Summer"
    assert challenge.model is RankingModel.CLUB


@respx.mock
def test_fetch_challenge_by_id_returns_none_when_missing() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"challengeById": None}})
    )

    with _client() as client:
        challenge = fetch_challenge_by_id(client, "missing")

    assert challenge is None


@respx.mock
def test_fetch_challenge_scores_yields_scores() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "challengeScores": _page(
                        [
                            {
                                "memberId": "m1",
                                "memberName": "Ada",
                                "score": 42.5,
                                "rank": 1,
                                "rideCount": 9,
                            }
                        ],
                        has_next=False,
                    )
                }
            },
        )
    )

    with _client() as client:
        scores = list(fetch_challenge_scores(client, "c1"))

    assert scores[0].member_name == "Ada"
    assert scores[0].score == 42.5
    assert scores[0].rank == 1


@respx.mock
def test_fetch_challenge_scores_sends_challenge_id_variable() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"challengeScores": _page([], has_next=False)}}
        )
    )

    with _client() as client:
        list(fetch_challenge_scores(client, "c1"))

    assert _variables(route)["challengeId"] == "c1"


@respx.mock
def test_fetch_gpx_routes_yields_routes() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "gpxRoutes": _page(
                        [
                            {
                                "id": "g1",
                                "title": "Riverside Loop",
                                "distance": 25,
                                "isPublic": True,
                            }
                        ],
                        has_next=False,
                    )
                }
            },
        )
    )

    with _client() as client:
        routes = list(fetch_gpx_routes(client))

    assert routes[0].title == "Riverside Loop"
    assert routes[0].distance == 25


@respx.mock
def test_fetch_gpx_route_by_id_returns_route() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "gpxRouteById": {
                        "id": "g9",
                        "title": "Riverside Loop",
                        "downloadUrl": "u",
                    }
                }
            },
        )
    )

    with _client() as client:
        route = fetch_gpx_route_by_id(client, "g9")

    assert route is not None
    assert route.title == "Riverside Loop"
    assert route.download_url == "u"


@respx.mock
def test_fetch_gpx_route_by_id_returns_none_when_missing() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"gpxRouteById": None}})
    )

    with _client() as client:
        route = fetch_gpx_route_by_id(client, "missing")

    assert route is None


@respx.mock
def test_fetch_internal_rides_single_page_yields_rides() -> None:
    respx.post(INTERNAL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "fetchRides": _rides_page(
                        [
                            {
                                "id": "r1",
                                "title": "Dawn Patrol",
                                "startTimeUtc": "2026-06-20T08:00:00Z",
                                "roadCaptains": [{"id": "m1", "firstName": "Ada"}],
                            }
                        ],
                        has_next=False,
                    )
                }
            },
        )
    )

    with _internal_client() as client:
        rides = list(fetch_internal_rides(client, "club-1", year=2026))

    assert [ride.id for ride in rides] == ["r1"]
    assert rides[0].title == "Dawn Patrol"
    assert rides[0].start_time == datetime(2026, 6, 20, 8, 0, tzinfo=UTC)
    assert rides[0].road_captains[0].first_name == "Ada"


@respx.mock
def test_fetch_internal_rides_paginates_with_skip_and_take() -> None:
    route = respx.post(INTERNAL_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={"data": {"fetchRides": _rides_page([{"id": "r1"}], has_next=True)}},
            ),
            httpx.Response(
                200,
                json={"data": {"fetchRides": _rides_page([{"id": "r2"}], has_next=False)}},
            ),
        ]
    )

    with _internal_client() as client:
        rides = list(fetch_internal_rides(client, "club-1", year=2026, page_size=25))

    assert [ride.id for ride in rides] == ["r1", "r2"]
    assert route.call_count == 2
    assert _variables_at(route, 0)["skip"] == 0
    assert _variables_at(route, 1)["skip"] == 25
    assert _variables_at(route, 1)["take"] == 25


@respx.mock
def test_fetch_internal_rides_sends_club_year_filter_variables() -> None:
    route = respx.post(INTERNAL_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"fetchRides": _rides_page([], has_next=False)}}
        )
    )

    with _internal_client() as client:
        list(fetch_internal_rides(client, "club-1", year=2026))

    variables = _variables(route)
    assert variables["clubId"] == "club-1"
    assert variables["sort"] == {"startTimeUtc": "DESC"}
    assert variables["showInactiveItems"] is True
    assert variables["filter"] == {
        "rideTypes": [],
        "labelIds": [],
        "minDate": "Thu, 01 Jan 2026 00:00:00 GMT",
        "maxDate": "Thu, 31 Dec 2026 23:59:59 GMT",
    }


@respx.mock
def test_fetch_internal_rides_defaults_year_to_current_utc_year() -> None:
    route = respx.post(INTERNAL_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"fetchRides": _rides_page([], has_next=False)}}
        )
    )

    with _internal_client() as client:
        list(fetch_internal_rides(client, "club-1"))

    year = datetime.now(UTC).year
    expected = datetime(year, 1, 1, tzinfo=UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert _variables(route)["filter"]["minDate"] == expected


@respx.mock
def test_fetch_internal_rides_uses_internal_endpoint_and_bearer_header() -> None:
    route = respx.post(INTERNAL_URL).mock(
        return_value=httpx.Response(
            200, json={"data": {"fetchRides": _rides_page([], has_next=False)}}
        )
    )

    with _internal_client() as client:
        list(fetch_internal_rides(client, "club-1", year=2026))

    request = route.calls.last.request
    assert str(request.url) == INTERNAL_URL
    assert request.headers["Authorization"] == "Bearer t-456"


def test_fetch_internal_rides_without_internal_auth_raises() -> None:
    client = _client()

    with client, pytest.raises(MissingCredentialError, match="internal auth is required"):
        list(fetch_internal_rides(client, "club-1", year=2026))

