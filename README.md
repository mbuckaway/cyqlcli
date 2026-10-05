# cyql

A Python client and command-line tool for the [Cyql](https://cyql.app) cycling-club platform,
built for the **GORBA** club (Guelph Off-Road Bicycling Association). It talks to Cyql's official
GraphQL API and surfaces club data — rides, ride participants, members, statistics, news, events,
challenges, and GPX routes — from your terminal in a form both people and AI assistants can consume.

## Requirements

- Python **3.14+**
- A Cyql **API key** (Cyql dashboard → Settings → API)

## Install

```bash
uv tool install https://github.com/mbuckaway/cyqlcli/releases/download/v1.0.0/cyql-1.0.0-py3-none-any.whl
cyql --help
```

`uv tool install` puts a `cyql` executable on your `PATH`. A single wheel serves macOS, Linux, and
Windows.

## Configuration

Configuration lives in a TOML file in the standard config directory:

- macOS / Linux: `~/.config/cyql/config.toml`
- Windows: `%APPDATA%\cyql\config.toml`

```toml
[cyql]
api_key = "..."          # official API key, sent as the X-Api-Key header
session_token = ""       # optional: internal-API bearer token (for specialized queries)
timezone = ""            # optional IANA zone, e.g. "America/Toronto"
timeout_seconds = 10.0
# official_endpoint / internal_endpoint override the Cyql defaults when set
```

Environment variables override the file: `CYQL_API_KEY`, `CYQL_SESSION_TOKEN`, `CYQL_TIMEZONE`,
`CYQL_TIMEOUT_SECONDS`, `CYQL_OFFICIAL_ENDPOINT`, `CYQL_INTERNAL_ENDPOINT`. Set `CYQL_CONFIG` to
point at a non-default config file.

## Usage

```bash
cyql nextride                          # the next upcoming ride
cyql rides -n 5                        # upcoming rides (default 5)
cyql rides --all -n 10                 # upcoming + past rides
cyql rides --search gravel             # rides matching a search term
cyql ride "tuesday"                    # first ride matching a search term
cyql ride-participants <ride-id>       # who is signed up for a ride
cyql stats                             # club statistics
cyql club                              # club information
cyql members -n 25                     # members (name/email/status/role)
cyql members --status approved         # members filtered by status
cyql member <member-id>                # one member's details
cyql news -n 5                         # latest club news
cyql news-post <news-id>               # one news article
cyql events -n 10                      # upcoming events
cyql event <event-id>                  # one event
cyql challenges                        # club challenges
cyql challenge <challenge-id>          # one challenge
cyql challenge-scores <challenge-id>   # a challenge's leaderboard
cyql gpx                               # the GPX route library
cyql gpx-route <gpx-route-id>          # one GPX route
cyql query --list                      # list specialized queries
cyql query active-ride-leaders         # run a specialized query
cyql version                           # the installed version
```

### Output formats

Every data command has three output modes:

- **table** (default) — a rich table on screen.
- **JSON** — `--json` prints machine-readable JSON (snake_case keys), ideal for Kimi/Deepseek and
  other AI systems.
- **CSV** — `--csv` prints comma-separated values.

`--output PATH` (or `-o PATH`) writes the output to a file instead of the screen, so
`cyql rides --csv --output rides.csv` produces a CSV file.

## Development

```bash
uv sync                              # create .venv and install runtime + dev deps
uv run ruff check .                  # lint (ruff, target py314)
uv run mypy                          # type-check (strict)
uv run pytest                        # unit tests + 90% branch-coverage gate
uv run pytest tests/functional -m functional --no-cov   # functional tests (local GraphQL server)
```

Tests follow TDD. Unit tests mock only the HTTP boundary (via `respx`) and use Hypothesis for pure
helpers; functional tests run against a real local GraphQL server (`tools/mockserver`, ariadne over
`wsgiref`) with no client-side mocks.

## Releasing

Releases are driven by git tags on `main`. A tag `vX.Y.Z` triggers the `Release` workflow, which
verifies the tag matches `src/cyql/__init__.py::__version__`, runs the full test gate, builds the
wheel + sdist, and attaches them to a GitHub Release. Install with the wheel URL as shown above.

## Project layout

```
src/cyql/
  config.py            # TOML config loader (std lib tomllib) + settings
  auth.py              # X-Api-Key (read) and Bearer (internal) auth strategies
  client.py            # httpx GraphQL client (retry, error mapping)
  paginate.py          # page/pageSize pagination
  models.py            # typed API models + enums
  resources/           # rides, members, club, events, news, challenges, gpx accessors
  queries/             # named specialized queries (the `query` command)
  cli/                 # Typer app + rich/JSON/CSV rendering
tools/mockserver/      # local GraphQL server for functional tests
```

## License

Copyright (c) 2026 Mark Buckaway. All rights reserved. This project is proprietary
(`SPDX-License-Identifier: LicenseRef-Proprietary`); no license to use, copy, or distribute is
granted without the author's express written permission.
