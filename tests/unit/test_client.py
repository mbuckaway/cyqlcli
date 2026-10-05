# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Tests for :mod:`cyql.client`."""

import json
import re

import httpx
import pytest
import respx

from cyql.auth import ApiKeyAuth, SessionTokenAuth
from cyql.client import CyqlClient
from cyql.errors import CyqlAPIError, CyqlHTTPError, MissingCredentialError

URL = "https://api.cyql.app/api/graphql"
INTERNAL_URL = "https://api.cyql.app/graphql"


def _auth() -> ApiKeyAuth:
    return ApiKeyAuth(api_key="k-123", endpoint=URL)


def _internal_auth() -> SessionTokenAuth:
    return SessionTokenAuth(token="t-456", endpoint=INTERNAL_URL)


def _client() -> CyqlClient:
    # No-op sleep keeps retry tests instant.
    return CyqlClient(_auth(), sleep=lambda _seconds: None)


@respx.mock
def test_execute_posts_query_with_auth_header_and_returns_data() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"clubStats": {"members": 3}}})
    )

    with _client() as client:
        data = client.execute("query { clubStats { members } }", {"clubId": "x"})

    assert data == {"clubStats": {"members": 3}}
    request = route.calls.last.request
    assert request.headers["X-Api-Key"] == "k-123"
    assert json.loads(request.content) == {
        "query": "query { clubStats { members } }",
        "variables": {"clubId": "x"},
    }


@respx.mock
def test_execute_raises_api_error_on_graphql_errors() -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "ApiKeyInvalid"}]})
    )

    with _client() as client, pytest.raises(CyqlAPIError, match="ApiKeyInvalid") as exc:
        client.execute("{ __typename }")

    assert exc.value.messages == ["ApiKeyInvalid"]


@respx.mock
def test_execute_raises_http_error_on_non_200() -> None:
    respx.post(URL).mock(return_value=httpx.Response(500, text="boom"))

    with _client() as client, pytest.raises(CyqlHTTPError, match="500") as exc:
        client.execute("{ __typename }")

    assert exc.value.status_code == 500


@respx.mock
def test_execute_retries_transient_status_then_succeeds() -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]
    )

    with _client() as client:
        data = client.execute("{ ok }")

    assert data == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_execute_retries_timeout_then_succeeds() -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.ConnectTimeout("slow"),
            httpx.Response(200, json={"data": {"ok": True}}),
        ]
    )

    with _client() as client:
        data = client.execute("{ ok }")

    assert data == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_execute_gives_up_after_max_retries_on_transient_status() -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(503))

    with _client() as client, pytest.raises(CyqlHTTPError, match="503"):
        client.execute("{ ok }")

    assert route.call_count == 3  # initial + 2 retries (default)


@respx.mock
def test_execute_raises_http_error_after_persistent_timeout() -> None:
    respx.post(URL).mock(side_effect=httpx.ConnectTimeout("slow"))

    with _client() as client, pytest.raises(CyqlHTTPError, match="timed out"):
        client.execute("{ ok }")


@respx.mock
def test_execute_returns_empty_dict_when_data_is_null() -> None:
    respx.post(URL).mock(return_value=httpx.Response(200, json={"data": None}))

    with _client() as client:
        data = client.execute("{ ok }")

    assert data == {}


def test_close_leaves_injected_http_client_open() -> None:
    injected = httpx.Client()

    CyqlClient(_auth(), http_client=injected).close()

    assert injected.is_closed is False
    injected.close()


@respx.mock
def test_execute_internal_uses_internal_auth_endpoint_and_headers() -> None:
    route = respx.post(INTERNAL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"ride": {"id": "r1"}}})
    )

    with CyqlClient(
        _auth(), internal_auth=_internal_auth(), sleep=lambda _seconds: None
    ) as client:
        data = client.execute("{ ride { id } }", internal=True)

    assert data == {"ride": {"id": "r1"}}
    request = route.calls.last.request
    assert str(request.url) == INTERNAL_URL
    assert request.headers["Authorization"] == "Bearer t-456"
    assert "X-Api-Key" not in request.headers


@respx.mock
def test_execute_default_uses_read_auth_when_internal_auth_present() -> None:
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json={"data": {"ok": True}})
    )

    with CyqlClient(
        _auth(), internal_auth=_internal_auth(), sleep=lambda _seconds: None
    ) as client:
        data = client.execute("{ ok }")

    assert data == {"ok": True}
    request = route.calls.last.request
    assert str(request.url) == URL
    assert request.headers["X-Api-Key"] == "k-123"
    assert "Authorization" not in request.headers


def test_execute_internal_without_internal_auth_raises_missing_credential() -> None:
    client = CyqlClient(_auth(), sleep=lambda _seconds: None)

    with pytest.raises(
        MissingCredentialError, match=re.escape("internal auth is required")
    ):
        client.execute("{ ok }", internal=True)
