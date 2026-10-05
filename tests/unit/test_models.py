# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Tests for :mod:`cyql.models` parsing, alias mapping, and enum coercion."""

from datetime import UTC, datetime

from cyql.models import (
    Challenge,
    ChallengeScore,
    ClubMemberStatus,
    ClubStats,
    Event,
    GpxRoute,
    Member,
    News,
    ParticipateStatus,
    RankingModel,
    RankingScoreType,
    Ride,
    RideMember,
    RideType,
)


def test_club_stats_parses_api_payload() -> None:
    stats = ClubStats.model_validate(
        {"totalRides": 10, "memberCount": 5, "totalKilometers": 123.5, "totalAdmins": 2}
    )

    assert stats.total_rides == 10
    assert stats.member_count == 5
    assert stats.total_kilometers == 123.5
    assert stats.total_admins == 2


def test_ride_type_enum_lists_official_members() -> None:
    assert [item.value for item in RideType] == [
        "RACE",
        "ATB",
        "CROSS",
        "TOUR",
        "VIRTUAL",
        "OTHER",
    ]


def test_club_member_status_enum_lists_official_members() -> None:
    assert [item.value for item in ClubMemberStatus] == [
        "PENDING",
        "APPROVED",
        "BLOCKED",
        "REMOVED",
        "EXPIRED",
        "ALL",
    ]


def test_participate_status_enum_lists_official_members() -> None:
    assert [item.value for item in ParticipateStatus] == [
        "UNKNOWN",
        "YES",
        "NO",
        "INTERESTED",
        "WAITING",
        "REFUNDED",
        "REFUND_REQUESTED",
    ]


def test_ranking_score_type_enum_lists_official_members() -> None:
    assert [item.value for item in RankingScoreType] == [
        "NONE",
        "DISTANCE",
        "SCORE",
        "NUMBER_OF_RIDES",
    ]


def test_ranking_model_enum_lists_official_members() -> None:
    assert [item.value for item in RankingModel] == ["CLUB", "PUBLIC"]


def test_ride_maps_camel_aliases_and_coerces_enum() -> None:
    ride = Ride.model_validate(
        {
            "id": "r1",
            "title": "Morning loop",
            "startTime": "2026-06-20T08:00:00Z",
            "rideType": "RACE",
            "averageSpeed": 25.0,
            "hasStops": True,
            "imageUrl": "https://img.example/r1.png",
        }
    )

    assert ride.start_time == datetime(2026, 6, 20, 8, 0, tzinfo=UTC)
    assert ride.ride_type is RideType.RACE
    assert ride.average_speed == 25.0
    assert ride.has_stops is True
    assert ride.image_url == "https://img.example/r1.png"


def test_ride_ignores_unknown_and_removed_fields() -> None:
    ride = Ride.model_validate({"id": "r1", "participantsCount": 7, "bogus": "x"})

    assert ride.id == "r1"
    assert "participants_count" not in Ride.model_fields


def test_ride_dump_serializes_enum_with_snake_case_keys() -> None:
    ride = Ride.model_validate({"id": "r1", "rideType": "TOUR", "hasStops": False})

    dumped = ride.model_dump(mode="json")

    assert dumped["ride_type"] == "TOUR"
    assert dumped["has_stops"] is False
    assert "rideType" not in dumped


def test_member_parses_admin_flags() -> None:
    member = Member.model_validate(
        {"id": "m1", "firstName": "Ada", "lastName": "Byron", "isAdmin": True}
    )

    assert member.first_name == "Ada"
    assert member.is_admin is True
    assert member.is_road_captain is False


def test_member_coerces_status_enum() -> None:
    member = Member.model_validate({"id": "m1", "status": "APPROVED"})

    assert member.status is ClubMemberStatus.APPROVED


def test_member_status_defaults_to_none_when_missing() -> None:
    member = Member.model_validate({"id": "m1"})

    assert member.status is None


def test_ride_member_maps_fields_and_coerces_status() -> None:
    participant = RideMember.model_validate(
        {
            "memberId": "m1",
            "firstName": "Ada",
            "lastName": "Byron",
            "status": "YES",
            "waiverAccepted": True,
        }
    )

    assert participant.member_id == "m1"
    assert participant.first_name == "Ada"
    assert participant.last_name == "Byron"
    assert participant.status is ParticipateStatus.YES
    assert participant.waiver_accepted is True


def test_challenge_maps_fields_and_coerces_enums() -> None:
    challenge = Challenge.model_validate(
        {
            "id": "c1",
            "title": "Summer Distance",
            "description": "Ride far",
            "rules": "Ride outside",
            "scoringCriteria": "Total kilometres",
            "prizes": "Bragging rights",
            "scoreType": "DISTANCE",
            "startDate": "2026-06-01T00:00:00Z",
            "endDate": "2026-08-31T00:00:00Z",
            "onlyStravaVerifiedRides": True,
            "model": "PUBLIC",
            "participantCount": 12,
            "iconUrl": "https://img.example/icon.png",
            "imageUrl": "https://img.example/banner.png",
        }
    )

    assert challenge.title == "Summer Distance"
    assert challenge.scoring_criteria == "Total kilometres"
    assert challenge.score_type is RankingScoreType.DISTANCE
    assert challenge.start_date == datetime(2026, 6, 1, tzinfo=UTC)
    assert challenge.end_date == datetime(2026, 8, 31, tzinfo=UTC)
    assert challenge.only_strava_verified_rides is True
    assert challenge.model is RankingModel.PUBLIC
    assert challenge.participant_count == 12
    assert challenge.icon_url == "https://img.example/icon.png"
    assert challenge.image_url == "https://img.example/banner.png"


def test_challenge_score_maps_fields() -> None:
    score = ChallengeScore.model_validate(
        {"memberId": "m1", "memberName": "Ada", "score": 42.5, "rank": 1, "rideCount": 9}
    )

    assert score.member_id == "m1"
    assert score.member_name == "Ada"
    assert score.score == 42.5
    assert score.rank == 1
    assert score.ride_count == 9


def test_gpx_route_maps_fields_and_parses_datetimes() -> None:
    route = GpxRoute.model_validate(
        {
            "id": "g1",
            "title": "Riverside Loop",
            "description": "Easy loop",
            "distance": 25,
            "altitude": 300,
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-02-01T00:00:00Z",
            "downloadUrl": "https://files.example/g1.gpx",
            "isPublic": True,
        }
    )

    assert route.distance == 25
    assert route.altitude == 300
    assert route.created_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert route.updated_at == datetime(2026, 2, 1, tzinfo=UTC)
    assert route.download_url == "https://files.example/g1.gpx"
    assert route.is_public is True


def test_gpx_route_is_public_defaults_false_when_missing() -> None:
    route = GpxRoute.model_validate({"id": "g1"})

    assert route.is_public is False


def test_event_maps_media_fields() -> None:
    event = Event.model_validate(
        {"id": "e1", "imageUrl": "i", "pdfTitle": "Guide", "pdfUrl": "u"}
    )

    assert event.image_url == "i"
    assert event.pdf_title == "Guide"
    assert event.pdf_url == "u"


def test_news_maps_media_and_edit_fields() -> None:
    article = News.model_validate(
        {
            "id": "n1",
            "publicationDate": "2026-04-01T00:00:00Z",
            "editDate": "2026-04-02T00:00:00Z",
            "imageUrl": "i",
            "pdfTitle": "Report",
            "pdfUrl": "u",
        }
    )

    assert article.publication_date == datetime(2026, 4, 1, tzinfo=UTC)
    assert article.edit_date == datetime(2026, 4, 2, tzinfo=UTC)
    assert article.image_url == "i"
    assert article.pdf_title == "Report"
    assert article.pdf_url == "u"
