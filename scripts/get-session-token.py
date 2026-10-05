#!/usr/bin/env python3
# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Fetch the live Cyql dashboard session token and club id from the browser.

The "undocumented" Cyql internal API authenticates with a short-lived Bearer JWT
kept in the ``token`` cookie on ``dashboard.cyql.app``. That cookie is a *session*
cookie, so it is never written to a browser's on-disk cookie store -- the reliable
way to read it is to ask the running browser. This helper drives the local Kimi
WebBridge daemon (which controls Chrome) to read ``document.cookie`` from a
dashboard tab, then writes ``session_token`` and ``club_id`` into
``~/.config/cyql/config.toml``. The token value is never printed.

Requires the WebBridge daemon running and the Kimi WebBridge extension active in
Chrome, signed in to the Cyql dashboard.

Usage:
    uv run python scripts/get-session-token.py [--url URL] [--daemon URL]
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from typing import Any

_DAEMON = "http://127.0.0.1:10086/command"
_DASHBOARD = "https://dashboard.cyql.app/"
_SESSION = "cyql-session-token"


def _post(daemon: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Send one command to the WebBridge daemon and return its parsed reply."""
    body = json.dumps({"action": action, "args": args, "session": _SESSION}).encode()
    request = urllib.request.Request(
        daemon, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def _cookie(cookie_header: str, name: str) -> str | None:
    """Return the value of ``name`` from a ``document.cookie`` string."""
    for part in cookie_header.split("; "):
        key, sep, value = part.partition("=")
        if sep and key.strip() == name:
            return value
    return None


def _jwt_claims(token: str) -> dict[str, Any]:
    """Decode the payload of a JWT without verifying it (metadata only)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return {}
    return claims


def _set_key(text: str, key: str, value: str) -> str:
    """Set ``key = "<value>"`` on its own line, replacing any existing line."""
    line = f"{key} = {json.dumps(value)}"
    if re.search(rf"(?m)^\s*{key}\s*=", text):
        return re.sub(rf"(?m)^\s*{key}\s*=.*$", lambda _match: line, text)
    return text.rstrip() + "\n" + line + "\n"


def main() -> int:
    """Read the session token from the browser and write it to the config."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daemon", default=_DAEMON, help="WebBridge command endpoint.")
    parser.add_argument(
        "--url", default=_DASHBOARD, help="Dashboard URL to read cookies from."
    )
    options = parser.parse_args()

    try:
        _post(
            options.daemon,
            "navigate",
            {"url": options.url, "newTab": True, "group_title": "Cyql session token"},
        )
        result = _post(options.daemon, "evaluate", {"code": "document.cookie"})
    except (urllib.error.URLError, OSError) as exc:
        print(f"WebBridge daemon unreachable at {options.daemon}: {exc}", file=sys.stderr)
        print("Start it with: ~/.kimi-webbridge/bin/kimi-webbridge start", file=sys.stderr)
        return 1

    cookie_header = (result.get("data") or {}).get("value") or ""
    token = _cookie(cookie_header, "token")
    club_id = _cookie(cookie_header, "clubId")
    if not token:
        print(
            "no 'token' cookie found; sign in to dashboard.cyql.app in Chrome first",
            file=sys.stderr,
        )
        return 1

    claims = _jwt_claims(token)
    exp = claims.get("exp")
    if isinstance(exp, int):
        expiry = datetime.datetime.fromtimestamp(exp, datetime.UTC)
        now = datetime.datetime.now(datetime.UTC)
        remaining = (expiry - now).total_seconds() / 60
        print(f"token exp {expiry.isoformat()} (remaining {remaining:.0f} min)")
    print(f"token length {len(token)}" + (f"; club_id {club_id}" if club_id else ""))

    config_path = pathlib.Path.home() / ".config" / "cyql" / "config.toml"
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else "[cyql]\n"
    text = _set_key(text, "session_token", token)
    if club_id:
        text = _set_key(text, "club_id", club_id)
    config_path.write_text(text, encoding="utf-8")
    config_path.chmod(0o600)
    suffix = " + club_id" if club_id else ""
    print(f"wrote session_token{suffix} to {config_path} (value not shown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
