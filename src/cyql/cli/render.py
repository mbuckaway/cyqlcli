# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Rendering helpers for the CLI: rich tables, JSON, or CSV.

Each ``render_*`` function forwards a JSON-ready payload and a table builder to
:func:`emit`. ``emit`` owns the output-format branch and the optional file write,
so no caller repeats that logic.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Sequence
from datetime import datetime, tzinfo
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from rich.console import Console, RenderableType
from rich.table import Table

from cyql.models import ClubInfo, ClubStats, Event, Member, News, Ride

__all__ = [
    "OutputFormat",
    "emit",
    "render_club_info",
    "render_detail",
    "render_events",
    "render_members",
    "render_news",
    "render_records",
    "render_ride_detail",
    "render_rides",
    "render_stats",
]


class OutputFormat(StrEnum):
    """How a command renders its result."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


def emit(
    console: Console,
    fmt: OutputFormat,
    payload: Any,
    build_table: Callable[[], RenderableType],
    *,
    output: str | None = None,
) -> None:
    """Emit ``payload`` as a table, JSON, or CSV, on screen or to ``output``."""
    renderable: RenderableType = (
        build_table() if fmt is OutputFormat.TABLE else _serialize(fmt, payload)
    )
    if output is None:
        console.print(renderable)
        return
    text = renderable if isinstance(renderable, str) else _capture(console, renderable)
    Path(output).write_text(text, encoding="utf-8")


def _serialize(fmt: OutputFormat, payload: Any) -> str:
    if fmt is OutputFormat.JSON:
        return json.dumps(payload, indent=2)
    return _to_csv(payload)


def _to_csv(payload: Any) -> str:
    rows = payload if isinstance(payload, list) else [payload]
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _capture(console: Console, renderable: RenderableType) -> str:
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


def _as_dict(record: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(record, BaseModel):
        return record.model_dump(mode="json")
    return record


def _text(value: object) -> str:
    return "-" if value is None else str(value)


def _dt(value: datetime | None, tz: tzinfo | None) -> str:
    return "-" if value is None else value.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def _km(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} km"


def _dump(items: Sequence[object]) -> list[Any]:
    return [item.model_dump(mode="json") for item in items]  # type: ignore[attr-defined]


def render_records(
    console: Console,
    records: Sequence[BaseModel | dict[str, Any]],
    *,
    fmt: OutputFormat = OutputFormat.TABLE,
    output: str | None = None,
    title: str = "",
) -> None:
    """Render a list of models or dicts; table columns follow the first keys."""
    payload = [_as_dict(record) for record in records]
    emit(console, fmt, payload, lambda: _records_table(payload, title), output=output)


def _records_table(rows: Sequence[dict[str, Any]], title: str) -> Table:
    table = Table(title=title or None)
    if not rows:
        return table
    for key in rows[0]:
        table.add_column(key)
    for row in rows:
        table.add_row(*(_text(row.get(key)) for key in rows[0]))
    return table


def render_detail(
    console: Console,
    record: BaseModel | dict[str, Any],
    *,
    fmt: OutputFormat = OutputFormat.TABLE,
    output: str | None = None,
    title: str = "",
) -> None:
    """Render one model or dict as a key/value table, JSON, or CSV."""
    payload = _as_dict(record)
    emit(console, fmt, payload, lambda: _detail_table(payload, title), output=output)


def _detail_table(row: dict[str, Any], title: str) -> Table:
    table = Table(title=title or None, show_header=False)
    for key, value in row.items():
        table.add_row(key, _text(value))
    return table


def _ride_detail_table(ride: Ride, tz: tzinfo | None) -> Table:
    table = Table(title=ride.title or "Ride", show_header=False)
    table.add_row("When", _dt(ride.start_time, tz))
    table.add_row("Location", _text(ride.location))
    table.add_row("Distance", _km(ride.distance))
    table.add_row("Type", _text(ride.ride_type))
    table.add_row("Link", _text(ride.share_url))
    return table


def render_ride_detail(
    console: Console,
    ride: Ride,
    fmt: OutputFormat = OutputFormat.TABLE,
    *,
    output: str | None = None,
    tz: tzinfo | None = None,
) -> None:
    """Render a single ride's details."""
    emit(
        console,
        fmt,
        ride.model_dump(mode="json"),
        lambda: _ride_detail_table(ride, tz),
        output=output,
    )


def _rides_table(rides: Sequence[Ride], tz: tzinfo | None) -> Table:
    table = Table(title="Upcoming rides")
    for column in ("Title", "When", "Distance", "Type"):
        table.add_column(column)
    for ride in rides:
        table.add_row(
            _text(ride.title),
            _dt(ride.start_time, tz),
            _km(ride.distance),
            _text(ride.ride_type),
        )
    return table


def render_rides(
    console: Console,
    rides: Sequence[Ride],
    fmt: OutputFormat = OutputFormat.TABLE,
    *,
    output: str | None = None,
    tz: tzinfo | None = None,
) -> None:
    """Render a list of rides as a table."""
    emit(console, fmt, _dump(rides), lambda: _rides_table(rides, tz), output=output)


def _stats_table(stats: ClubStats) -> Table:
    table = Table(title="Club statistics", show_header=False)
    table.add_row("Members", str(stats.member_count))
    table.add_row("Admins", str(stats.total_admins))
    table.add_row("Rides", str(stats.total_rides))
    table.add_row("Kilometres", f"{stats.total_kilometers:.1f}")
    return table


def render_stats(
    console: Console,
    stats: ClubStats,
    fmt: OutputFormat = OutputFormat.TABLE,
    *,
    output: str | None = None,
    tz: tzinfo | None = None,
) -> None:
    """Render club statistics."""
    emit(
        console,
        fmt,
        stats.model_dump(mode="json"),
        lambda: _stats_table(stats),
        output=output,
    )


def _club_table(info: ClubInfo) -> Table:
    table = Table(title=info.title or "Club", show_header=False)
    table.add_row("City", _text(info.city))
    table.add_row("Contact", _text(info.contact))
    table.add_row("Email", _text(info.email))
    return table


def render_club_info(
    console: Console,
    info: ClubInfo,
    fmt: OutputFormat = OutputFormat.TABLE,
    *,
    output: str | None = None,
    tz: tzinfo | None = None,
) -> None:
    """Render club profile information."""
    emit(
        console,
        fmt,
        info.model_dump(mode="json"),
        lambda: _club_table(info),
        output=output,
    )


def _members_table(members: Sequence[Member]) -> Table:
    table = Table(title="Members")
    for column in ("Name", "Email", "Status", "Admin"):
        table.add_column(column)
    for member in members:
        name = " ".join(part for part in (member.first_name, member.last_name) if part) or "-"
        admin = "yes" if member.is_admin else "no"
        table.add_row(name, _text(member.email), _text(member.status), admin)
    return table


def render_members(
    console: Console,
    members: Sequence[Member],
    fmt: OutputFormat = OutputFormat.TABLE,
    *,
    output: str | None = None,
    tz: tzinfo | None = None,
) -> None:
    """Render a list of members (admin/local use)."""
    emit(console, fmt, _dump(members), lambda: _members_table(members), output=output)


def _events_table(events: Sequence[Event], tz: tzinfo | None) -> Table:
    table = Table(title="Events")
    for column in ("Title", "When", "Location"):
        table.add_column(column)
    for event in events:
        table.add_row(_text(event.title), _dt(event.start_date_time, tz), _text(event.location))
    return table


def render_events(
    console: Console,
    events: Sequence[Event],
    fmt: OutputFormat = OutputFormat.TABLE,
    *,
    output: str | None = None,
    tz: tzinfo | None = None,
) -> None:
    """Render a list of events as a table."""
    emit(console, fmt, _dump(events), lambda: _events_table(events, tz), output=output)


def _news_table(news: Sequence[News], tz: tzinfo | None) -> Table:
    table = Table(title="News")
    for column in ("Title", "Date"):
        table.add_column(column)
    for article in news:
        table.add_row(_text(article.title), _dt(article.publication_date, tz))
    return table


def render_news(
    console: Console,
    news: Sequence[News],
    fmt: OutputFormat = OutputFormat.TABLE,
    *,
    output: str | None = None,
    tz: tzinfo | None = None,
) -> None:
    """Render a list of news articles as a table."""
    emit(console, fmt, _dump(news), lambda: _news_table(news, tz), output=output)
