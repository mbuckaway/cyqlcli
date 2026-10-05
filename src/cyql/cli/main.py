# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Typer application for the ``cyql`` command — read-only Cyql access."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import tzinfo
from itertools import islice
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer
from rich.console import Console

from cyql import __version__
from cyql.auth import build_internal_auth, build_read_auth
from cyql.cli import render
from cyql.cli.render import OutputFormat
from cyql.client import CyqlClient
from cyql.config import Settings, load_settings
from cyql.errors import CyqlError, MissingCredentialError
from cyql.models import ClubMemberStatus
from cyql.queries import get_query
from cyql.queries import list_queries as list_registered_queries
from cyql.resources.challenges import (
    fetch_challenge_by_id,
    fetch_challenge_scores,
    fetch_challenges,
)
from cyql.resources.club import fetch_club_info, fetch_club_stats
from cyql.resources.events import fetch_event_by_id, fetch_events
from cyql.resources.gpx import fetch_gpx_route_by_id, fetch_gpx_routes
from cyql.resources.members import fetch_member_by_id, fetch_members
from cyql.resources.news import fetch_news, fetch_news_by_id
from cyql.resources.rides import (
    fetch_next_ride,
    fetch_ride_participants,
    fetch_rides,
)

app = typer.Typer(
    name="cyql",
    help="Read-only client for the Cyql cycling-club API.",
    no_args_is_help=True,
)

_console = Console()

JsonOption = Annotated[bool, typer.Option("--json", help="Output raw JSON instead of a table.")]
CsvOption = Annotated[bool, typer.Option("--csv", help="Output CSV instead of a table.")]
OutputOption = Annotated[
    str | None, typer.Option("--output", "-o", help="Write output to this file.")
]
CountOption = Annotated[int, typer.Option("--count", "-n", help="Maximum items to show.")]
SearchOption = Annotated[
    str | None, typer.Option("--search", help="Filter by a search term.")
]
StatusOption = Annotated[
    str | None, typer.Option("--status", help="Filter by member status.")
]
FetchTypeOption = Annotated[
    str | None, typer.Option("--fetch-type", help="Event fetch type.")
]


def _build_client(settings: Settings) -> CyqlClient:
    try:
        read_auth = build_read_auth(settings)
        internal_auth = build_internal_auth(settings)
    except MissingCredentialError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    return CyqlClient(
        read_auth, internal_auth=internal_auth, timeout=settings.timeout_seconds
    )


def _resolve_tz(settings: Settings) -> tzinfo | None:
    """Resolve the display timezone; ``None`` means the system local zone."""
    if not settings.timezone:
        return None
    try:
        return ZoneInfo(settings.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        typer.secho(
            f"Warning: unknown timezone {settings.timezone!r}; using local time.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return None


@contextmanager
def _client_session() -> Iterator[tuple[CyqlClient, tzinfo | None]]:
    """Yield a client and display timezone, turning Cyql errors into a clean message."""
    settings = load_settings()
    client = _build_client(settings)
    tz = _resolve_tz(settings)
    try:
        yield client, tz
    except CyqlError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    finally:
        client.close()


def _resolve_format(json_output: bool, csv_output: bool) -> OutputFormat:
    """Pick the output format; reject asking for JSON and CSV at once."""
    if json_output and csv_output:
        typer.secho("Error: --json and --csv are mutually exclusive", err=True)
        raise typer.Exit(code=2)
    if json_output:
        return OutputFormat.JSON
    if csv_output:
        return OutputFormat.CSV
    return OutputFormat.TABLE


def _parse_status(value: str | None) -> ClubMemberStatus | None:
    """Convert a ``--status`` string to the member status enum.

    Raises:
        typer.Exit: if ``value`` does not name a known status.
    """
    if value is None:
        return None
    try:
        return ClubMemberStatus(value.upper())
    except ValueError as exc:
        typer.secho(f"Error: unknown member status {value!r}", err=True)
        raise typer.Exit(code=2) from exc


@app.callback()
def main() -> None:
    """Read-only client for the Cyql cycling-club API."""


@app.command()
def version() -> None:
    """Print the installed cyql version."""
    typer.echo(__version__)


@app.command()
def nextride(
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show the next upcoming ride."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, tz):
        ride = fetch_next_ride(client)
    if ride is None:
        typer.echo("No upcoming rides.")
        return
    render.render_ride_detail(_console, ride, fmt, output=output, tz=tz)


@app.command()
def rides(
    count: CountOption = 5,
    all_rides: Annotated[bool, typer.Option("--all", help="Include past rides.")] = False,
    search: SearchOption = None,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """List upcoming rides (or every ride with --all)."""
    fmt = _resolve_format(json_output, csv_output)
    is_upcoming = None if all_rides else True
    with _client_session() as (client, tz):
        items = list(
            islice(fetch_rides(client, is_upcoming=is_upcoming, search=search), count)
        )
    render.render_rides(_console, items, fmt, output=output, tz=tz)


@app.command()
def ride(
    search: Annotated[str, typer.Argument(help="Text to match against rides.")],
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show details of the first ride matching SEARCH."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, tz):
        items = list(islice(fetch_rides(client, search=search), 1))
    if not items:
        typer.echo(f"No ride matching {search!r}.")
        return
    render.render_ride_detail(_console, items[0], fmt, output=output, tz=tz)


@app.command()
def ride_participants(
    ride_id: Annotated[str, typer.Argument(help="Ride id (UUID).")],
    count: CountOption = 25,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """List the participants of a ride."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        items = list(islice(fetch_ride_participants(client, ride_id), count))
    render.render_records(
        _console, items, fmt=fmt, output=output, title="Ride participants"
    )


@app.command()
def stats(
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show club statistics."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        club_stats = fetch_club_stats(client)
    render.render_stats(_console, club_stats, fmt, output=output)


@app.command()
def members(
    count: CountOption = 25,
    status: StatusOption = None,
    search: SearchOption = None,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """List club members (admin/local use)."""
    fmt = _resolve_format(json_output, csv_output)
    member_status = _parse_status(status)
    with _client_session() as (client, _tz):
        items = list(
            islice(fetch_members(client, search=search, status=member_status), count)
        )
    render.render_members(_console, items, fmt, output=output)


@app.command()
def member(
    member_id: Annotated[str, typer.Argument(help="Member id (UUID).")],
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show one member's details."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        record = fetch_member_by_id(client, member_id)
    if record is None:
        typer.echo(f"No member with id {member_id}.")
        return
    render.render_detail(_console, record, fmt=fmt, output=output, title="Member")


@app.command()
def events(
    count: CountOption = 10,
    fetch_type: FetchTypeOption = None,
    search: SearchOption = None,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """List club events."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, tz):
        items = list(
            islice(fetch_events(client, search=search, fetch_type=fetch_type), count)
        )
    render.render_events(_console, items, fmt, output=output, tz=tz)


@app.command()
def event(
    event_id: Annotated[str, typer.Argument(help="Event id (UUID).")],
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show one event."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        record = fetch_event_by_id(client, event_id)
    if record is None:
        typer.echo(f"No event with id {event_id}.")
        return
    render.render_detail(_console, record, fmt=fmt, output=output, title="Event")


@app.command()
def news(
    count: CountOption = 5,
    search: SearchOption = None,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """List club news."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, tz):
        items = list(islice(fetch_news(client, search=search), count))
    render.render_news(_console, items, fmt, output=output, tz=tz)


@app.command()
def news_post(
    news_id: Annotated[str, typer.Argument(help="News article id (UUID).")],
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show one news article."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        record = fetch_news_by_id(client, news_id)
    if record is None:
        typer.echo(f"No news article with id {news_id}.")
        return
    render.render_detail(_console, record, fmt=fmt, output=output, title="News")


@app.command()
def challenges(
    count: CountOption = 10,
    search: SearchOption = None,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """List club challenges."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        items = list(islice(fetch_challenges(client, search=search), count))
    render.render_records(_console, items, fmt=fmt, output=output, title="Challenges")


@app.command()
def challenge(
    challenge_id: Annotated[str, typer.Argument(help="Challenge id (UUID).")],
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show one challenge."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        record = fetch_challenge_by_id(client, challenge_id)
    if record is None:
        typer.echo(f"No challenge with id {challenge_id}.")
        return
    render.render_detail(_console, record, fmt=fmt, output=output, title="Challenge")


@app.command()
def challenge_scores(
    challenge_id: Annotated[str, typer.Argument(help="Challenge id (UUID).")],
    count: CountOption = 10,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show a challenge's leaderboard."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        items = list(islice(fetch_challenge_scores(client, challenge_id), count))
    render.render_records(
        _console, items, fmt=fmt, output=output, title="Challenge scores"
    )


@app.command()
def gpx(
    count: CountOption = 25,
    search: SearchOption = None,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """List the GPX route library."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        items = list(islice(fetch_gpx_routes(client, search=search), count))
    render.render_records(_console, items, fmt=fmt, output=output, title="GPX routes")


@app.command()
def gpx_route(
    gpx_route_id: Annotated[str, typer.Argument(help="GPX route id (UUID).")],
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show one GPX route."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        record = fetch_gpx_route_by_id(client, gpx_route_id)
    if record is None:
        typer.echo(f"No GPX route with id {gpx_route_id}.")
        return
    render.render_detail(_console, record, fmt=fmt, output=output, title="GPX route")


@app.command()
def club(
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Show club information."""
    fmt = _resolve_format(json_output, csv_output)
    with _client_session() as (client, _tz):
        info = fetch_club_info(client)
    render.render_club_info(_console, info, fmt, output=output)


@app.command()
def query(
    name: Annotated[str | None, typer.Argument()] = None,
    list_queries: Annotated[
        bool, typer.Option("--list", help="List available queries.")
    ] = False,
    json_output: JsonOption = False,
    csv_output: CsvOption = False,
    output: OutputOption = None,
) -> None:
    """Run a specialized query, or list them with --list."""
    fmt = _resolve_format(json_output, csv_output)
    if list_queries:
        rows = [
            {"name": spec.name, "description": spec.description}
            for spec in list_registered_queries()
        ]
        render.render_records(_console, rows, fmt=fmt, output=output, title="Queries")
        return
    if not name:
        typer.secho("Error: provide a query name or --list", err=True)
        raise typer.Exit(code=2)
    with _client_session() as (client, _tz):
        spec = get_query(name)
        records = spec.run(client)
    render.render_records(_console, records, fmt=fmt, output=output, title=spec.name)


if __name__ == "__main__":  # pragma: no cover
    app()
