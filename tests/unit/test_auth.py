# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Tests for :mod:`cyql.auth`."""

import re

import pytest

from cyql.auth import (
    ApiKeyAuth,
    SessionTokenAuth,
    build_internal_auth,
    build_read_auth,
)
from cyql.config import INTERNAL_ENDPOINT, OFFICIAL_ENDPOINT, Settings
from cyql.errors import MissingCredentialError


def test_build_read_auth_uses_official_endpoint_and_api_key_header() -> None:
    auth = build_read_auth(Settings(api_key="k-123"))

    assert auth == ApiKeyAuth(api_key="k-123", endpoint=OFFICIAL_ENDPOINT)
    assert auth.headers() == {"X-Api-Key": "k-123"}


def test_build_read_auth_uses_configured_official_endpoint() -> None:
    settings = Settings(api_key="k-123", official_endpoint="http://localhost/api/graphql")

    auth = build_read_auth(settings)

    assert auth.endpoint == "http://localhost/api/graphql"


@pytest.mark.parametrize("api_key", [None, ""])
def test_build_read_auth_missing_key_raises_missing_credential(api_key: str | None) -> None:
    with pytest.raises(
        MissingCredentialError,
        match=re.escape("CYQL_API_KEY is required for read auth"),
    ):
        build_read_auth(Settings(api_key=api_key))


def test_build_internal_auth_returns_session_token_auth_when_token_set() -> None:
    auth = build_internal_auth(Settings(session_token="t-456"))

    assert auth == SessionTokenAuth(token="t-456", endpoint=INTERNAL_ENDPOINT)
    assert auth.headers() == {"Authorization": "Bearer t-456"}


def test_build_internal_auth_uses_configured_internal_endpoint() -> None:
    settings = Settings(session_token="t-456", internal_endpoint="http://localhost/graphql")

    auth = build_internal_auth(settings)

    assert auth == SessionTokenAuth(token="t-456", endpoint="http://localhost/graphql")


@pytest.mark.parametrize("token", [None, ""])
def test_build_internal_auth_returns_none_when_no_token(token: str | None) -> None:
    assert build_internal_auth(Settings(session_token=token)) is None
