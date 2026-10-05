# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Runtime configuration loaded from a TOML file and the environment.

Settings live in ``config.toml`` under the ``[cyql]`` table, in the standard
per-user config directory. Environment variables override the file so a shell
can point the client elsewhere without editing config. Secrets are never
hard-coded.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

__all__ = [
    "INTERNAL_ENDPOINT",
    "OFFICIAL_ENDPOINT",
    "Settings",
    "config_dir",
    "default_config_path",
    "load_settings",
    "migrate_api_key",
]

OFFICIAL_ENDPOINT = "https://api.cyql.app/api/graphql"
INTERNAL_ENDPOINT = "https://api.cyql.app/graphql"

_ENV_FIELDS = {
    "api_key": "CYQL_API_KEY",
    "session_token": "CYQL_SESSION_TOKEN",  # nosec B105 - env-var name, not a secret
    "timezone": "CYQL_TIMEZONE",
    "timeout_seconds": "CYQL_TIMEOUT_SECONDS",
    "official_endpoint": "CYQL_OFFICIAL_ENDPOINT",
    "internal_endpoint": "CYQL_INTERNAL_ENDPOINT",
}

_TOML_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}

# ``Path`` re-dispatches to ``WindowsPath``/``PosixPath`` on ``os.name`` at call time.
# Capture the running platform's class so path construction never crosses flavours.
_PathClass: type[Path] = type(Path())


class Settings(BaseModel):
    """Configuration for the Cyql client."""

    model_config = ConfigDict(extra="ignore")

    api_key: str | None = None
    session_token: str | None = None
    timezone: str | None = None
    timeout_seconds: float = 10.0
    official_endpoint: str = OFFICIAL_ENDPOINT
    internal_endpoint: str = INTERNAL_ENDPOINT


def config_dir() -> Path:
    """Return the per-user Cyql configuration directory for this platform."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return _PathClass(appdata) / "cyql"
        return _PathClass("~").expanduser() / "AppData" / "Roaming" / "cyql"
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return _PathClass(xdg_config_home) / "cyql"
    return _PathClass("~").expanduser() / ".config" / "cyql"


def default_config_path() -> Path:
    """Return the default TOML config file path."""
    return config_dir() / "config.toml"


def load_settings(path: str | os.PathLike[str] | None = None) -> Settings:
    """Load settings from TOML and apply environment overrides.

    Args:
        path: config file to read. When omitted, use ``CYQL_CONFIG`` if set,
            otherwise ``default_config_path()``.

    Returns:
        Settings merged from field defaults, the TOML ``[cyql]`` table, and the
        ``CYQL_*`` environment variables. A missing file uses the defaults.
    """
    if path is not None:
        resolved = Path(path)
    elif os.environ.get("CYQL_CONFIG"):
        resolved = Path(os.environ["CYQL_CONFIG"])
    else:
        resolved = default_config_path()

    values: dict[str, Any] = {}
    if resolved.exists():
        with resolved.open("rb") as handle:
            document = tomllib.load(handle)
        values.update(document.get("cyql", {}))

    for field, env_name in _ENV_FIELDS.items():
        raw = os.environ.get(env_name)
        if not raw:
            continue
        values[field] = float(raw) if field == "timeout_seconds" else raw

    return Settings.model_validate(values)


def migrate_api_key(
    source: str | os.PathLike[str],
    config_path: str | os.PathLike[str] | None = None,
) -> None:
    """Write the API key from ``source`` into a new TOML config file.

    The source file is left untouched.

    Args:
        source: file that holds the raw API key.
        config_path: destination file. Defaults to ``default_config_path()``.
    """
    api_key = Path(source).read_text(encoding="utf-8").strip()
    target = Path(config_path) if config_path is not None else default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(_render_config(api_key))
    target.chmod(0o600)


def _render_config(api_key: str) -> str:
    """Render a ``[cyql]`` TOML document that carries ``api_key``."""
    lines = [
        "[cyql]",
        f"api_key = {_toml_string(api_key)}",
        'session_token = ""',
        'timezone = ""',
        "timeout_seconds = 10.0",
        f"official_endpoint = {_toml_string(OFFICIAL_ENDPOINT)}",
        f"internal_endpoint = {_toml_string(INTERNAL_ENDPOINT)}",
        "",
    ]
    return "\n".join(lines)


def _toml_string(value: str) -> str:
    """Return ``value`` as a TOML basic string literal."""
    parts: list[str] = []
    for char in value:
        if char in _TOML_ESCAPES:
            parts.append(_TOML_ESCAPES[char])
        elif char < "\x20" or char == "\x7f":
            parts.append(f"\\u{ord(char):04X}")
        else:
            parts.append(char)
    return '"' + "".join(parts) + '"'
