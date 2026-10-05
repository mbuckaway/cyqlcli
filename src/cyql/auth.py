# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Authentication strategies for the two Cyql GraphQL endpoints.

``ApiKeyAuth`` targets the official, read-only ``/api/graphql`` endpoint and is
the read strategy. ``SessionTokenAuth`` targets the internal ``/graphql`` endpoint
(Bearer JWT); it is optional and used only when an internal session token is
configured, because writes are deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cyql.config import Settings
from cyql.errors import MissingCredentialError

__all__ = [
    "ApiKeyAuth",
    "Auth",
    "SessionTokenAuth",
    "build_internal_auth",
    "build_read_auth",
]


@runtime_checkable
class Auth(Protocol):
    """An authentication strategy: a target endpoint plus request headers."""

    @property
    def endpoint(self) -> str: ...

    def headers(self) -> dict[str, str]: ...


@dataclass(frozen=True)
class ApiKeyAuth:
    """Authenticate to the official endpoint with an ``X-Api-Key`` header."""

    api_key: str
    endpoint: str

    def headers(self) -> dict[str, str]:
        """Return the headers carrying the API key."""
        return {"X-Api-Key": self.api_key}


@dataclass(frozen=True)
class SessionTokenAuth:
    """Authenticate to the internal endpoint with a Bearer session token."""

    token: str
    endpoint: str

    def headers(self) -> dict[str, str]:
        """Return the headers carrying the bearer token."""
        return {"Authorization": f"Bearer {self.token}"}


def build_read_auth(settings: Settings) -> ApiKeyAuth:
    """Build the official read-only API-key auth strategy.

    Raises:
        MissingCredentialError: if ``settings.api_key`` is empty.
    """
    if not settings.api_key:
        raise MissingCredentialError("CYQL_API_KEY is required for read auth")
    return ApiKeyAuth(api_key=settings.api_key, endpoint=settings.official_endpoint)


def build_internal_auth(settings: Settings) -> SessionTokenAuth | None:
    """Build the internal session-token strategy, or ``None`` without a token."""
    if not settings.session_token:
        return None
    return SessionTokenAuth(
        token=settings.session_token, endpoint=settings.internal_endpoint
    )
