# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""A real (local) GraphQL service mirroring the official Cyql read API.

Schema-first via ariadne, served on stdlib ``wsgiref``. It returns fixture data,
implements page/pageSize pagination like ``PagedResultOf*Dto``, and rejects
requests whose ``X-Api-Key`` header does not match the expected key — so
functional tests exercise the full client stack over real HTTP, no mocks.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from typing import Any

from ariadne import QueryType, ScalarType, make_executable_schema
from ariadne.wsgi import GraphQL

SDL = """
scalar UUID
scalar DateTime

enum RideType { RACE ATB CROSS TOUR VIRTUAL OTHER }
enum ClubMemberStatus { PENDING APPROVED BLOCKED REMOVED EXPIRED ALL }
enum ParticipateStatus { UNKNOWN YES NO INTERESTED WAITING REFUNDED REFUND_REQUESTED }
enum RankingScoreType { NONE DISTANCE SCORE NUMBER_OF_RIDES }
enum RankingModel { CLUB PUBLIC }

type ClubStatsDto { totalRides: Int! memberCount: Int! totalKilometers: Float! totalAdmins: Int! }
type ClubInfoDto {
  title: String city: String description: String address: String
  postalCode: String contact: String email: String createdAt: DateTime
}
type RideDto {
  id: UUID title: String description: String startTime: DateTime rideType: RideType
  location: String hasStops: Boolean distance: Float altitude: Float averageSpeed: Float
  duration: Int isPublic: Boolean maxGroupSize: Int shareUrl: String gpxUrl: String
  imageUrl: String
}
type PagedResultOfRideDto {
  items: [RideDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}
type MemberDto {
  id: UUID! firstName: String lastName: String email: String status: ClubMemberStatus!
  memberSinceUtc: DateTime isAdmin: Boolean! isRoadCaptain: Boolean!
}
type PagedResultOfMemberDto {
  items: [MemberDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}
type RideMemberDto {
  memberId: UUID firstName: String lastName: String status: ParticipateStatus
  waiverAccepted: Boolean
}
type PagedResultOfRideMemberDto {
  items: [RideMemberDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}
type EventDto {
  id: UUID title: String description: String
  startDateTime: DateTime endTime: DateTime location: String
  imageUrl: String pdfTitle: String pdfUrl: String
}
type PagedResultOfEventDto {
  items: [EventDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}
type NewsDto {
  id: UUID title: String description: String publicationDate: DateTime
  editDate: DateTime imageUrl: String pdfTitle: String pdfUrl: String
}
type PagedResultOfNewsDto {
  items: [NewsDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}
type ChallengeDto {
  id: UUID title: String description: String rules: String scoringCriteria: String
  prizes: String scoreType: RankingScoreType startDate: DateTime endDate: DateTime
  onlyStravaVerifiedRides: Boolean model: RankingModel participantCount: Int
  iconUrl: String imageUrl: String
}
type PagedResultOfChallengeDto {
  items: [ChallengeDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}
type ChallengeScoreDto {
  memberId: UUID memberName: String score: Float rank: Int rideCount: Int
}
type PagedResultOfChallengeScoreDto {
  items: [ChallengeScoreDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}
type GpxRouteDto {
  id: UUID title: String description: String distance: Int altitude: Int
  createdAt: DateTime updatedAt: DateTime downloadUrl: String isPublic: Boolean
}
type PagedResultOfGpxRouteDto {
  items: [GpxRouteDto!]! totalCount: Int! page: Int! pageSize: Int! hasNextPage: Boolean!
}

type Query {
  clubStats: ClubStatsDto!
  clubInfo: ClubInfoDto!
  rides(page: Int, pageSize: Int, isUpcoming: Boolean, search: String): PagedResultOfRideDto!
  rideById(rideId: UUID!): RideDto
  rideParticipants(
    rideId: UUID!, page: Int, pageSize: Int, search: String
  ): PagedResultOfRideMemberDto!
  members(
    page: Int, pageSize: Int, search: String, memberStatus: ClubMemberStatus
  ): PagedResultOfMemberDto!
  memberById(memberId: UUID!): MemberDto
  events(
    page: Int, pageSize: Int, fetchType: String, search: String
  ): PagedResultOfEventDto!
  eventById(eventId: UUID!): EventDto
  news(page: Int, pageSize: Int, search: String): PagedResultOfNewsDto!
  newsById(newsId: UUID!): NewsDto
  challenges(page: Int, pageSize: Int, search: String): PagedResultOfChallengeDto!
  challengeById(challengeId: UUID!): ChallengeDto
  challengeScores(
    challengeId: UUID!, page: Int, pageSize: Int, search: String
  ): PagedResultOfChallengeScoreDto!
  gpxRoutes(page: Int, pageSize: Int, search: String): PagedResultOfGpxRouteDto!
  gpxRouteById(gpxRouteId: UUID!): GpxRouteDto
}
"""

CLUB_STATS = {"totalRides": 78, "memberCount": 167, "totalKilometers": 991.0, "totalAdmins": 5}
CLUB_INFO = {
    "title": "GORBA",
    "city": "Guelph",
    "description": "Guelph Off-Road Bicycling Association",
    "address": "42 Carden St",
    "postalCode": "N1H 3A2",
    "contact": "Mark Buckaway",
    "email": "info@gorba.ca",
    "createdAt": "2010-01-01T00:00:00Z",
}
RIDES = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Tuesday Night Ride",
        "description": "Weekly social ride",
        "startTime": "2026-06-16T23:00:00Z",
        "rideType": "ATB",
        "location": "Riverside Park",
        "hasStops": True,
        "distance": 16.0,
        "altitude": 50.0,
        "averageSpeed": 22.0,
        "duration": 120,
        "isPublic": True,
        "maxGroupSize": 20,
        "shareUrl": "https://cyqlapp.app.link/ride1",
        "gpxUrl": None,
        "imageUrl": "https://images.example/ride1.png",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "title": "Gravel Grind",
        "description": "Long gravel route",
        "startTime": "2026-06-20T13:00:00Z",
        "rideType": "TOUR",
        "location": "Arkell Springs",
        "hasStops": False,
        "distance": 60.0,
        "altitude": 400.0,
        "averageSpeed": 25.0,
        "duration": 180,
        "isPublic": True,
        "maxGroupSize": 15,
        "shareUrl": "https://cyqlapp.app.link/ride2",
        "gpxUrl": None,
        "imageUrl": None,
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "title": "Sunday Spin",
        "description": "Easy recovery spin",
        "startTime": "2026-06-21T14:00:00Z",
        "rideType": "RACE",
        "location": "Hydrocut",
        "hasStops": False,
        "distance": 30.0,
        "altitude": 150.0,
        "averageSpeed": 28.0,
        "duration": 90,
        "isPublic": True,
        "maxGroupSize": 10,
        "shareUrl": "https://cyqlapp.app.link/ride3",
        "gpxUrl": None,
        "imageUrl": None,
    },
]
MEMBERS = [
    {
        "id": "aaaaaaaa-0000-0000-0000-000000000001",
        "firstName": "Ada",
        "lastName": "Byron",
        "email": "ada@example.org",
        "status": "APPROVED",
        "memberSinceUtc": "2024-03-01T00:00:00Z",
        "isAdmin": True,
        "isRoadCaptain": False,
    },
    {
        "id": "aaaaaaaa-0000-0000-0000-000000000002",
        "firstName": "Grace",
        "lastName": "Hopper",
        "email": "grace@example.org",
        "status": "APPROVED",
        "memberSinceUtc": "2025-05-01T00:00:00Z",
        "isAdmin": False,
        "isRoadCaptain": True,
    },
]
RIDE_PARTICIPANTS = {
    "11111111-1111-1111-1111-111111111111": [
        {
            "memberId": "aaaaaaaa-0000-0000-0000-000000000001",
            "firstName": "Ada",
            "lastName": "Byron",
            "status": "YES",
            "waiverAccepted": True,
        },
        {
            "memberId": "aaaaaaaa-0000-0000-0000-000000000002",
            "firstName": "Grace",
            "lastName": "Hopper",
            "status": "NO",
            "waiverAccepted": False,
        },
    ],
    "22222222-2222-2222-2222-222222222222": [
        {
            "memberId": "aaaaaaaa-0000-0000-0000-000000000002",
            "firstName": "Grace",
            "lastName": "Hopper",
            "status": "INTERESTED",
            "waiverAccepted": False,
        }
    ],
}
EVENTS = [
    {
        "id": "eeeeeeee-0000-0000-0000-000000000001",
        "title": "GORBA EPIC Festival",
        "description": "Annual festival",
        "startDateTime": "2026-09-14T08:00:00Z",
        "endTime": "2026-09-14T17:00:00Z",
        "location": "Guelph Lake",
        "imageUrl": "https://images.example/epic.png",
        "pdfTitle": "Festival guide",
        "pdfUrl": "https://files.example/epic.pdf",
    },
]
NEWS = [
    {
        "id": "ffffffff-0000-0000-0000-000000000001",
        "title": "Trails are open",
        "description": "Spring trails now open",
        "publicationDate": "2026-04-01T00:00:00Z",
        "editDate": "2026-04-02T00:00:00Z",
        "imageUrl": "https://images.example/trails.png",
        "pdfTitle": "Trail report",
        "pdfUrl": "https://files.example/trails.pdf",
    },
]
CHALLENGES = [
    {
        "id": "cccccccc-0000-0000-0000-000000000001",
        "title": "Summer Distance Challenge",
        "description": "Ride the most kilometres",
        "rules": "Log every ride",
        "scoringCriteria": "Total kilometres",
        "prizes": "Club jersey",
        "scoreType": "DISTANCE",
        "startDate": "2026-06-01T00:00:00Z",
        "endDate": "2026-08-31T00:00:00Z",
        "onlyStravaVerifiedRides": True,
        "model": "PUBLIC",
        "participantCount": 2,
        "iconUrl": "https://images.example/summer-icon.png",
        "imageUrl": "https://images.example/summer.png",
    },
    {
        "id": "cccccccc-0000-0000-0000-000000000002",
        "title": "Climb Challenge",
        "description": "Climb the most elevation",
        "rules": "Log every climb",
        "scoringCriteria": "Total elevation",
        "prizes": "Bragging rights",
        "scoreType": "SCORE",
        "startDate": "2026-07-01T00:00:00Z",
        "endDate": "2026-07-31T00:00:00Z",
        "onlyStravaVerifiedRides": False,
        "model": "CLUB",
        "participantCount": 1,
        "iconUrl": None,
        "imageUrl": None,
    },
]
CHALLENGE_SCORES = {
    "cccccccc-0000-0000-0000-000000000001": [
        {
            "memberId": "aaaaaaaa-0000-0000-0000-000000000001",
            "memberName": "Ada",
            "score": 420.5,
            "rank": 1,
            "rideCount": 12,
        },
        {
            "memberId": "aaaaaaaa-0000-0000-0000-000000000002",
            "memberName": "Grace",
            "score": 310.0,
            "rank": 2,
            "rideCount": 9,
        },
    ],
    "cccccccc-0000-0000-0000-000000000002": [
        {
            "memberId": "aaaaaaaa-0000-0000-0000-000000000002",
            "memberName": "Grace",
            "score": 1500.0,
            "rank": 1,
            "rideCount": 4,
        },
    ],
}
GPX_ROUTES = [
    {
        "id": "gggggggg-0000-0000-0000-000000000001",
        "title": "Riverside Loop",
        "description": "Easy riverside loop",
        "distance": 16,
        "altitude": 50,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-02-01T00:00:00Z",
        "downloadUrl": "https://files.example/riverside.gpx",
        "isPublic": True,
    },
    {
        "id": "gggggggg-0000-0000-0000-000000000002",
        "title": "Arkell Springs",
        "description": "Climbing route",
        "distance": 60,
        "altitude": 400,
        "createdAt": "2026-03-01T00:00:00Z",
        "updatedAt": "2026-03-05T00:00:00Z",
        "downloadUrl": "https://files.example/arkell.gpx",
        "isPublic": False,
    },
]

query = QueryType()
uuid_scalar = ScalarType("UUID", serializer=str, value_parser=str)
datetime_scalar = ScalarType("DateTime", serializer=str, value_parser=str)


def _paginate(rows: list[dict[str, Any]], kwargs: dict[str, Any]) -> dict[str, Any]:
    page = kwargs.get("page") or 1
    page_size = kwargs.get("pageSize") or 50
    search = kwargs.get("search")
    if search:
        needle = search.lower()
        rows = [row for row in rows if needle in (row.get("title") or "").lower()]
    start = (page - 1) * page_size
    chunk = rows[start : start + page_size]
    return {
        "items": chunk,
        "totalCount": len(rows),
        "page": page,
        "pageSize": page_size,
        "hasNextPage": start + page_size < len(rows),
    }


def _find_by_id(rows: list[dict[str, Any]], entity_id: str) -> dict[str, Any] | None:
    return next((row for row in rows if row["id"] == entity_id), None)


@query.field("clubStats")
def resolve_club_stats(*_: Any) -> dict[str, Any]:
    return CLUB_STATS


@query.field("clubInfo")
def resolve_club_info(*_: Any) -> dict[str, Any]:
    return CLUB_INFO


@query.field("rides")
def resolve_rides(_: Any, __: Any, **kwargs: Any) -> dict[str, Any]:
    return _paginate(RIDES, kwargs)


@query.field("rideById")
def resolve_ride_by_id(_: Any, __: Any, rideId: str) -> dict[str, Any] | None:
    return _find_by_id(RIDES, rideId)


@query.field("rideParticipants")
def resolve_ride_participants(_: Any, __: Any, rideId: str, **kwargs: Any) -> dict[str, Any]:
    return _paginate(RIDE_PARTICIPANTS.get(rideId, []), kwargs)


@query.field("members")
def resolve_members(_: Any, __: Any, **kwargs: Any) -> dict[str, Any]:
    return _paginate(MEMBERS, kwargs)


@query.field("memberById")
def resolve_member_by_id(_: Any, __: Any, memberId: str) -> dict[str, Any] | None:
    return _find_by_id(MEMBERS, memberId)


@query.field("events")
def resolve_events(_: Any, __: Any, **kwargs: Any) -> dict[str, Any]:
    return _paginate(EVENTS, kwargs)


@query.field("eventById")
def resolve_event_by_id(_: Any, __: Any, eventId: str) -> dict[str, Any] | None:
    return _find_by_id(EVENTS, eventId)


@query.field("news")
def resolve_news(_: Any, __: Any, **kwargs: Any) -> dict[str, Any]:
    return _paginate(NEWS, kwargs)


@query.field("newsById")
def resolve_news_by_id(_: Any, __: Any, newsId: str) -> dict[str, Any] | None:
    return _find_by_id(NEWS, newsId)


@query.field("challenges")
def resolve_challenges(_: Any, __: Any, **kwargs: Any) -> dict[str, Any]:
    return _paginate(CHALLENGES, kwargs)


@query.field("challengeById")
def resolve_challenge_by_id(_: Any, __: Any, challengeId: str) -> dict[str, Any] | None:
    return _find_by_id(CHALLENGES, challengeId)


@query.field("challengeScores")
def resolve_challenge_scores(
    _: Any, __: Any, challengeId: str, **kwargs: Any
) -> dict[str, Any]:
    return _paginate(CHALLENGE_SCORES.get(challengeId, []), kwargs)


@query.field("gpxRoutes")
def resolve_gpx_routes(_: Any, __: Any, **kwargs: Any) -> dict[str, Any]:
    return _paginate(GPX_ROUTES, kwargs)


@query.field("gpxRouteById")
def resolve_gpx_route_by_id(_: Any, __: Any, gpxRouteId: str) -> dict[str, Any] | None:
    return _find_by_id(GPX_ROUTES, gpxRouteId)


schema = make_executable_schema(SDL, query, uuid_scalar, datetime_scalar)

WsgiApp = Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]


def make_app(expected_key: str | None = None) -> WsgiApp:
    """Build the WSGI app, rejecting requests without the expected ``X-Api-Key``."""
    key = expected_key if expected_key is not None else os.environ.get(
        "MOCK_EXPECTED_API_KEY", "functional-test-key"
    )
    graphql_app = GraphQL(schema)

    def app(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        if environ.get("REQUEST_METHOD") == "POST" and environ.get("HTTP_X_API_KEY") != key:
            body = json.dumps({"data": None, "errors": [{"message": "ApiKeyInvalid"}]}).encode()
            start_response(
                "200 OK",
                [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
            )
            return [body]
        return graphql_app(environ, start_response)

    return app


def serve(host: str = "127.0.0.1", port: int = 8888) -> None:  # pragma: no cover - manual use
    """Run the mock server (for manual exploration)."""
    from wsgiref.simple_server import make_server

    with make_server(host, port, make_app()) as server:  # type: ignore[arg-type]
        server.serve_forever()


if __name__ == "__main__":  # pragma: no cover - manual use
    serve()
