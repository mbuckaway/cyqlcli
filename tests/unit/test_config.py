# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Tests for :mod:`cyql.config`."""

import os
import stat
import tomllib
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cyql.config import (
    INTERNAL_ENDPOINT,
    OFFICIAL_ENDPOINT,
    Settings,
    _render_config,
    config_dir,
    default_config_path,
    load_settings,
    migrate_api_key,
)

_ENV_NAMES = (
    "CYQL_API_KEY",
    "CYQL_SESSION_TOKEN",
    "CYQL_TIMEZONE",
    "CYQL_TIMEOUT_SECONDS",
    "CYQL_OFFICIAL_ENDPOINT",
    "CYQL_INTERNAL_ENDPOINT",
    "CYQL_CONFIG",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every CYQL_* variable so ambient config cannot leak into a test."""
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_settings_defaults_match_the_public_contract() -> None:
    settings = Settings()

    assert settings.api_key is None
    assert settings.session_token is None
    assert settings.timezone is None
    assert settings.timeout_seconds == 10.0
    assert settings.official_endpoint == OFFICIAL_ENDPOINT
    assert settings.internal_endpoint == INTERNAL_ENDPOINT


def test_settings_ignores_extra_keys() -> None:
    settings = Settings(api_key="k", unknown="ignored")  # type: ignore[call-arg]

    assert settings.api_key == "k"


def test_load_settings_missing_file_returns_defaults(clean_env: None, tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "absent.toml")

    assert settings.api_key is None
    assert settings.timeout_seconds == 10.0
    assert settings.official_endpoint == OFFICIAL_ENDPOINT


def test_load_settings_reads_cyql_table(clean_env: None, tmp_path: Path) -> None:
    config = _write(
        tmp_path / "config.toml",
        '[cyql]\napi_key = "from-toml"\ntimezone = "America/Toronto"\ntimeout_seconds = 3.5\n',
    )

    settings = load_settings(config)

    assert settings.api_key == "from-toml"
    assert settings.timezone == "America/Toronto"
    assert settings.timeout_seconds == 3.5


def test_load_settings_ignores_other_tables_and_keys(clean_env: None, tmp_path: Path) -> None:
    config = _write(
        tmp_path / "config.toml",
        '[cyql]\napi_key = "from-toml"\nunknown_key = "ignored"\n\n[other]\napi_key = "nope"\n',
    )

    settings = load_settings(config)

    assert settings.api_key == "from-toml"


def test_load_settings_env_value_beats_toml(
    clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(tmp_path / "config.toml", '[cyql]\napi_key = "from-toml"\n')
    monkeypatch.setenv("CYQL_API_KEY", "from-env")

    settings = load_settings(config)

    assert settings.api_key == "from-env"


def test_load_settings_empty_env_value_does_not_beat_toml(
    clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(tmp_path / "config.toml", '[cyql]\napi_key = "from-toml"\n')
    monkeypatch.setenv("CYQL_API_KEY", "")

    settings = load_settings(config)

    assert settings.api_key == "from-toml"


def test_load_settings_coerces_env_timeout_seconds_to_float(
    clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CYQL_TIMEOUT_SECONDS", "2.5")

    settings = load_settings(tmp_path / "absent.toml")

    assert isinstance(settings.timeout_seconds, float)
    assert settings.timeout_seconds == 2.5


def test_load_settings_applies_env_session_token(
    clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CYQL_SESSION_TOKEN", "t-456")

    settings = load_settings(tmp_path / "absent.toml")

    assert settings.session_token == "t-456"


def test_load_settings_uses_cyql_config_path(
    clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write(tmp_path / "custom.toml", '[cyql]\napi_key = "from-env-path"\n')
    monkeypatch.setenv("CYQL_CONFIG", str(config))

    settings = load_settings()

    assert settings.api_key == "from-env-path"


def test_load_settings_explicit_path_beats_cyql_config(
    clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_config = _write(tmp_path / "env.toml", '[cyql]\napi_key = "from-env-path"\n')
    explicit = _write(tmp_path / "explicit.toml", '[cyql]\napi_key = "from-explicit"\n')
    monkeypatch.setenv("CYQL_CONFIG", str(env_config))

    settings = load_settings(explicit)

    assert settings.api_key == "from-explicit"


@pytest.mark.skipif(os.name == "nt", reason="POSIX home resolution")
def test_load_settings_defaults_to_default_config_path(
    clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir_path = tmp_path / ".config" / "cyql"
    config_dir_path.mkdir(parents=True)
    _write(config_dir_path / "config.toml", '[cyql]\napi_key = "from-default-path"\n')

    settings = load_settings()

    assert settings.api_key == "from-default-path"


def test_config_dir_uses_xdg_config_home_on_posix(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert config_dir() == tmp_path / "xdg" / "cyql"


@pytest.mark.skipif(os.name == "nt", reason="POSIX home resolution")
def test_config_dir_defaults_to_home_config_on_posix(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert config_dir() == tmp_path / ".config" / "cyql"


@pytest.mark.skipif(os.name == "nt", reason="POSIX home resolution")
def test_config_dir_treats_empty_xdg_config_home_as_unset(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert config_dir() == tmp_path / ".config" / "cyql"


def test_config_dir_uses_appdata_on_windows(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

    assert config_dir() == tmp_path / "Roaming" / "cyql"


def test_config_dir_windows_without_appdata_uses_home(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert config_dir() == tmp_path / "AppData" / "Roaming" / "cyql"


def test_default_config_path_appends_config_toml(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert default_config_path() == tmp_path / "cyql" / "config.toml"


def test_migrate_api_key_writes_trimmed_key(
    clean_env: None, tmp_path: Path
) -> None:
    source = _write(tmp_path / "key.txt", "  secret-key-abc \n")
    target = tmp_path / "nested" / "config.toml"

    migrate_api_key(source, target)

    parsed: dict[str, Any] = tomllib.loads(target.read_text(encoding="utf-8"))
    assert parsed["cyql"]["api_key"] == "secret-key-abc"
    assert source.read_text(encoding="utf-8") == "  secret-key-abc \n"


@pytest.mark.skipif(os.name == "nt", reason="0600 is a POSIX-only file mode")
def test_migrate_api_key_writes_0600_permissions_on_posix(
    clean_env: None, tmp_path: Path
) -> None:
    source = _write(tmp_path / "key.txt", "secret-key-abc")
    target = tmp_path / "config.toml"

    migrate_api_key(source, target)

    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_migrate_api_key_output_reloads(clean_env: None, tmp_path: Path) -> None:
    source = _write(tmp_path / "key.txt", "secret-key-abc")

    target = tmp_path / "config.toml"
    migrate_api_key(source, target)

    assert load_settings(target).api_key == "secret-key-abc"


@pytest.mark.skipif(os.name == "nt", reason="POSIX home resolution")
def test_migrate_api_key_writes_default_path_when_none(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    source = _write(tmp_path / "key.txt", "secret-key-abc")

    migrate_api_key(source)

    assert (tmp_path / ".config" / "cyql" / "config.toml").exists()


def test_render_config_includes_default_other_fields(clean_env: None) -> None:
    parsed: dict[str, Any] = tomllib.loads(_render_config("k-123"))

    assert parsed["cyql"]["session_token"] == ""
    assert parsed["cyql"]["timezone"] == ""
    assert parsed["cyql"]["timeout_seconds"] == 10.0
    assert parsed["cyql"]["official_endpoint"] == OFFICIAL_ENDPOINT
    assert parsed["cyql"]["internal_endpoint"] == INTERNAL_ENDPOINT


@pytest.mark.parametrize(
    "raw",
    ["plain", 'has"quote', "back\\slash", "line\nbreak", "bell\x07", "del\x7f"],
)
def test_render_config_escapes_special_characters(clean_env: None, raw: str) -> None:
    parsed: dict[str, Any] = tomllib.loads(_render_config(raw))

    assert parsed["cyql"]["api_key"] == raw


@given(st.text())
def test_render_config_round_trips_api_key(api_key: str) -> None:
    parsed = tomllib.loads(_render_config(api_key))

    assert parsed["cyql"]["api_key"] == api_key
