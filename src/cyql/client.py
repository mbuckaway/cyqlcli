# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Thin synchronous GraphQL client over httpx.

Sends a single GraphQL operation per call, retries transient failures with
exponential backoff, and maps HTTP / GraphQL errors onto package exceptions.
The official Cyql API returns HTTP 200 with an ``errors`` array on failures
(e.g. ``ApiKeyInvalid``), so both paths are handled.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from types import TracebackType
from typing import Any

import httpx

from cyql.auth import Auth
from cyql.errors import CyqlAPIError, CyqlHTTPError, MissingCredentialError

__all__ = ["CyqlClient"]

DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = 0.5
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


class CyqlClient:
    """Execute GraphQL queries against a Cyql endpoint selected by ``auth``."""

    def __init__(
        self,
        auth: Auth,
        *,
        internal_auth: Auth | None = None,
        timeout: float = 10.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._auth = auth
        self._internal_auth = internal_auth
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._http_client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    def __enter__(self) -> CyqlClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._owns_client:
            self._http_client.close()

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        internal: bool = False,
    ) -> dict[str, Any]:
        """Run a GraphQL operation and return its ``data`` object.

        Args:
            query: the GraphQL document to send.
            variables: values for the document's variables.
            internal: use the internal API auth instead of the read auth.

        Raises:
            MissingCredentialError: if ``internal`` is set but no internal auth
                was supplied to the constructor.
        """
        auth = self._resolve_auth(internal)
        payload = {"query": query, "variables": variables or {}}
        headers = {"Content-Type": "application/json", **auth.headers()}

        attempt = 0
        while True:
            is_last = attempt == self._max_retries
            try:
                response = self._http_client.post(
                    auth.endpoint, json=payload, headers=headers
                )
            except httpx.TimeoutException as exc:
                if is_last:
                    raise CyqlHTTPError("request to Cyql timed out") from exc
                self._backoff(attempt)
                attempt += 1
                continue

            if response.status_code in RETRYABLE_STATUS and not is_last:
                self._backoff(attempt)
                attempt += 1
                continue
            return self._parse(response)

    def _resolve_auth(self, internal: bool) -> Auth:
        if not internal:
            return self._auth
        if self._internal_auth is None:
            raise MissingCredentialError(
                "internal auth is required for internal API calls"
            )
        return self._internal_auth

    def _backoff(self, attempt: int) -> None:
        self._sleep(self._backoff_seconds * (2**attempt))

    def _parse(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code != 200:
            raise CyqlHTTPError(
                f"Cyql API returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        body = response.json()
        errors = body.get("errors")
        if errors:
            messages = [item.get("message", "unknown error") for item in errors]
            raise CyqlAPIError("; ".join(messages), messages=messages)
        return body.get("data") or {}
