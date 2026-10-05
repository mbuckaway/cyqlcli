# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Typed models mirroring the official Cyql API DTOs (introspected).

Field aliases map the API's camelCase names onto snake_case attributes. Models
ignore unknown fields so the client keeps working if the API adds attributes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Challenge",
    "ChallengeScore",
    "ClubInfo",
    "ClubMemberStatus",
    "ClubStats",
    "Event",
    "GpxRoute",
    "InternalMember",
    "InternalRide",
    "Member",
    "News",
    "ParticipateStatus",
    "RankingModel",
    "RankingScoreType",
    "Ride",
    "RideLeader",
    "RideMember",
    "RideType",
]


class _ApiModel(BaseModel):
    """Base for API models: populate by field name or alias, ignore extras."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class RideType(StrEnum):
    """Official ``RideType`` enum."""

    RACE = "RACE"
    ATB = "ATB"
    CROSS = "CROSS"
    TOUR = "TOUR"
    VIRTUAL = "VIRTUAL"
    OTHER = "OTHER"


class ClubMemberStatus(StrEnum):
    """Official ``ClubMemberStatus`` enum."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    REMOVED = "REMOVED"
    EXPIRED = "EXPIRED"
    ALL = "ALL"


class ParticipateStatus(StrEnum):
    """Official ``ParticipateStatus`` enum."""

    UNKNOWN = "UNKNOWN"
    YES = "YES"
    NO = "NO"
    INTERESTED = "INTERESTED"
    WAITING = "WAITING"
    REFUNDED = "REFUNDED"
    REFUND_REQUESTED = "REFUND_REQUESTED"


class RankingScoreType(StrEnum):
    """Official ``RankingScoreType`` enum."""

    NONE = "NONE"
    DISTANCE = "DISTANCE"
    SCORE = "SCORE"
    NUMBER_OF_RIDES = "NUMBER_OF_RIDES"


class RankingModel(StrEnum):
    """Official ``RankingModel`` enum."""

    CLUB = "CLUB"
    PUBLIC = "PUBLIC"


class ClubStats(_ApiModel):
    """Aggregate club statistics (``clubStats``)."""

    total_rides: int = Field(alias="totalRides")
    member_count: int = Field(alias="memberCount")
    total_kilometers: float = Field(alias="totalKilometers")
    total_admins: int = Field(alias="totalAdmins")


class ClubInfo(_ApiModel):
    """Club profile (``clubInfo``)."""

    title: str | None = None
    city: str | None = None
    description: str | None = None
    address: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    contact: str | None = None
    email: str | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")


class Ride(_ApiModel):
    """A planned or past ride (``RideDto``)."""

    id: str | None = None
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = Field(default=None, alias="startTime")
    ride_type: RideType | None = Field(default=None, alias="rideType")
    location: str | None = None
    distance: float | None = None
    altitude: float | None = None
    average_speed: float | None = Field(default=None, alias="averageSpeed")
    duration: int | None = None
    is_public: bool | None = Field(default=None, alias="isPublic")
    max_group_size: int | None = Field(default=None, alias="maxGroupSize")
    has_stops: bool | None = Field(default=None, alias="hasStops")
    share_url: str | None = Field(default=None, alias="shareUrl")
    gpx_url: str | None = Field(default=None, alias="gpxUrl")
    image_url: str | None = Field(default=None, alias="imageUrl")


class Member(_ApiModel):
    """A club member (``MemberDto``). Only the CLI surfaces per-member detail."""

    id: str
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: str | None = None
    status: ClubMemberStatus | None = None
    member_since: datetime | None = Field(default=None, alias="memberSinceUtc")
    is_admin: bool = Field(default=False, alias="isAdmin")
    is_road_captain: bool = Field(default=False, alias="isRoadCaptain")


class RideMember(_ApiModel):
    """A ride participant (``RideMemberDto``)."""

    member_id: str | None = Field(default=None, alias="memberId")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    status: ParticipateStatus | None = None
    waiver_accepted: bool | None = Field(default=None, alias="waiverAccepted")


class Event(_ApiModel):
    """A calendar event (``EventDto``)."""

    id: str | None = None
    title: str | None = None
    description: str | None = None
    start_date_time: datetime | None = Field(default=None, alias="startDateTime")
    end_time: datetime | None = Field(default=None, alias="endTime")
    location: str | None = None
    image_url: str | None = Field(default=None, alias="imageUrl")
    pdf_title: str | None = Field(default=None, alias="pdfTitle")
    pdf_url: str | None = Field(default=None, alias="pdfUrl")


class News(_ApiModel):
    """A club news article (``NewsDto``)."""

    id: str | None = None
    title: str | None = None
    description: str | None = None
    publication_date: datetime | None = Field(default=None, alias="publicationDate")
    edit_date: datetime | None = Field(default=None, alias="editDate")
    image_url: str | None = Field(default=None, alias="imageUrl")
    pdf_title: str | None = Field(default=None, alias="pdfTitle")
    pdf_url: str | None = Field(default=None, alias="pdfUrl")


class Challenge(_ApiModel):
    """A club challenge (``ChallengeDto``)."""

    id: str | None = None
    title: str | None = None
    description: str | None = None
    rules: str | None = None
    scoring_criteria: str | None = Field(default=None, alias="scoringCriteria")
    prizes: str | None = None
    score_type: RankingScoreType | None = Field(default=None, alias="scoreType")
    start_date: datetime | None = Field(default=None, alias="startDate")
    end_date: datetime | None = Field(default=None, alias="endDate")
    only_strava_verified_rides: bool | None = Field(
        default=None, alias="onlyStravaVerifiedRides"
    )
    model: RankingModel | None = None
    participant_count: int | None = Field(default=None, alias="participantCount")
    icon_url: str | None = Field(default=None, alias="iconUrl")
    image_url: str | None = Field(default=None, alias="imageUrl")


class ChallengeScore(_ApiModel):
    """One member's standing in a challenge (``ChallengeScoreDto``)."""

    member_id: str | None = Field(default=None, alias="memberId")
    member_name: str | None = Field(default=None, alias="memberName")
    score: float | None = None
    rank: int | None = None
    ride_count: int | None = Field(default=None, alias="rideCount")


class GpxRoute(_ApiModel):
    """A downloadable GPX route (``GpxRouteDto``)."""

    id: str | None = None
    title: str | None = None
    description: str | None = None
    distance: int | None = None
    altitude: int | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    is_public: bool = Field(default=False, alias="isPublic")


class InternalMember(_ApiModel):
    """A member reference on the internal API (``fetchRides.roadCaptains``)."""

    id: str
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: str | None = None


class InternalRide(_ApiModel):
    """An internal API ride with its listed road captains."""

    id: str
    title: str | None = None
    start_time: datetime | None = Field(default=None, alias="startTimeUtc")
    road_captains: list[InternalMember] = Field(
        default_factory=list, alias="roadCaptains"
    )


class RideLeader(_ApiModel):
    """One distinct ride leader and the number of rides they led this year."""

    member_id: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    rides_led: int = 0
