# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""Unit tests for the CLI render helpers (table, JSON, CSV, file output)."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from rich.console import Console
from rich.table import Table

from cyql.cli.render import (
    OutputFormat,
    _serialize,
    _to_csv,
    emit,
    render_detail,
    render_records,
    render_stats,
)
from cyql.models import ClubStats, Member

RECORDS = [
    Member(id="m1", first_name="Ada", last_name="Lovelace"),
    Member(id="m2", first_name="Grace", last_name="Hopper"),
]

STATS = ClubStats(
    total_rides=3, member_count=42, total_kilometers=100.5, total_admins=2
)

_TEXT = st.text(
    alphabet=st.characters(blacklist_characters="\r\n", blacklist_categories=("Cs",))
)


def _console() -> tuple[Console, StringIO]:
    buffer = StringIO()
    return Console(file=buffer, width=200, no_color=True), buffer


@given(values=st.lists(_TEXT, min_size=1, max_size=5))
def test_to_csv_round_trips_values_through_dict_reader(values: list[str]) -> None:
    rows = [{"name": value} for value in values]

    parsed = list(csv.DictReader(StringIO(_to_csv(rows))))

    assert [row["name"] for row in parsed] == values


@given(
    payload=st.dictionaries(
        keys=st.text(min_size=1),
        values=st.one_of(st.none(), st.booleans(), st.integers()),
        max_size=5,
    )
)
def test_serialize_json_round_trips_payload(payload: dict[str, object]) -> None:
    assert json.loads(_serialize(OutputFormat.JSON, payload)) == payload


def _sample_table() -> Table:
    table = Table("Name")
    table.add_row("Ada")
    return table


def test_output_format_values_are_lowercase_names() -> None:
    assert [fmt.value for fmt in OutputFormat] == ["table", "json", "csv"]


def test_emit_table_prints_table_build_output() -> None:
    console, buffer = _console()

    emit(console, OutputFormat.TABLE, {"name": "Ada"}, _sample_table)

    assert "Ada" in buffer.getvalue()


def test_emit_json_prints_indented_json() -> None:
    console, buffer = _console()

    emit(console, OutputFormat.JSON, {"name": "Ada"}, _sample_table)

    assert json.loads(buffer.getvalue()) == {"name": "Ada"}
    assert '\n  "name"' in buffer.getvalue()


def test_emit_csv_list_of_dicts_writes_header_and_rows() -> None:
    console, buffer = _console()

    emit(console, OutputFormat.CSV, [{"name": "Ada"}, {"name": "Grace"}], _sample_table)

    assert buffer.getvalue().rstrip("\r\n").splitlines() == ["name", "Ada", "Grace"]


def test_emit_csv_single_dict_writes_one_row() -> None:
    console, buffer = _console()

    emit(console, OutputFormat.CSV, {"name": "Ada"}, _sample_table)

    assert buffer.getvalue().rstrip("\r\n").splitlines() == ["name", "Ada"]


def test_emit_csv_empty_list_writes_no_records() -> None:
    console, buffer = _console()

    emit(console, OutputFormat.CSV, [], _sample_table)

    assert buffer.getvalue().strip() == ""


def test_emit_output_writes_json_file(tmp_path: Path) -> None:
    console, _ = _console()
    target = tmp_path / "out.json"

    emit(console, OutputFormat.JSON, {"name": "Ada"}, _sample_table, output=str(target))

    assert json.loads(target.read_text(encoding="utf-8")) == {"name": "Ada"}


def test_emit_output_writes_csv_file(tmp_path: Path) -> None:
    console, _ = _console()
    target = tmp_path / "out.csv"

    emit(
        console,
        OutputFormat.CSV,
        [{"name": "Ada"}, {"name": "Grace"}],
        _sample_table,
        output=str(target),
    )

    assert target.read_text(encoding="utf-8").splitlines() == [
        "name",
        "Ada",
        "Grace",
    ]


def test_emit_output_writes_empty_csv_file(tmp_path: Path) -> None:
    console, _ = _console()
    target = tmp_path / "out.csv"

    emit(console, OutputFormat.CSV, [], _sample_table, output=str(target))

    assert target.read_text(encoding="utf-8") == ""


def test_emit_output_writes_rendered_table_file(tmp_path: Path) -> None:
    console, _ = _console()
    target = tmp_path / "out.txt"

    emit(console, OutputFormat.TABLE, {"name": "Ada"}, _sample_table, output=str(target))

    assert "Ada" in target.read_text(encoding="utf-8")


def test_emit_output_does_not_print_to_console(tmp_path: Path) -> None:
    console, buffer = _console()

    emit(
        console,
        OutputFormat.JSON,
        {"name": "Ada"},
        _sample_table,
        output=str(tmp_path / "out.json"),
    )

    assert buffer.getvalue() == ""


def test_render_records_table_lists_columns_in_insertion_order() -> None:
    console, buffer = _console()

    render_records(console, RECORDS, fmt=OutputFormat.TABLE, title="Members")

    output = buffer.getvalue()
    assert "Members" in output
    assert output.index("id") < output.index("first_name") < output.index("last_name")


def test_render_records_json_dumps_each_record() -> None:
    console, buffer = _console()

    render_records(console, RECORDS, fmt=OutputFormat.JSON)

    assert json.loads(buffer.getvalue()) == [
        record.model_dump(mode="json") for record in RECORDS
    ]


def test_render_records_csv_writes_header_and_rows() -> None:
    console, buffer = _console()

    render_records(console, RECORDS, fmt=OutputFormat.CSV)

    lines = buffer.getvalue().rstrip("\r\n").splitlines()
    assert lines[0].startswith("id,first_name")
    assert len(lines) == 3


def test_render_records_empty_list_csv_writes_no_records() -> None:
    console, buffer = _console()

    render_records(console, [], fmt=OutputFormat.CSV)

    assert buffer.getvalue().strip() == ""


def test_render_records_empty_list_table_prints_nothing() -> None:
    console, buffer = _console()

    render_records(console, [], fmt=OutputFormat.TABLE, title="Nothing here")

    assert buffer.getvalue().strip() == ""


def test_render_records_accepts_plain_dicts() -> None:
    console, buffer = _console()
    rows = [{"name": "active-ride-leaders", "description": "Ride leaders"}]

    render_records(console, rows, fmt=OutputFormat.JSON, title="Queries")

    assert json.loads(buffer.getvalue()) == rows


def test_render_records_output_writes_file(tmp_path: Path) -> None:
    console, _ = _console()
    target = tmp_path / "records.json"

    render_records(console, RECORDS, fmt=OutputFormat.JSON, output=str(target))

    assert json.loads(target.read_text(encoding="utf-8"))[0]["id"] == "m1"


def test_render_detail_table_shows_key_value_rows() -> None:
    console, buffer = _console()

    render_detail(console, RECORDS[0], title="Member")

    output = buffer.getvalue()
    assert "Member" in output
    assert "first_name" in output
    assert "Ada" in output


def test_render_detail_json_dumps_the_record() -> None:
    console, buffer = _console()

    render_detail(console, RECORDS[0], fmt=OutputFormat.JSON)

    assert json.loads(buffer.getvalue()) == RECORDS[0].model_dump(mode="json")


def test_render_detail_csv_writes_one_row() -> None:
    console, buffer = _console()

    render_detail(console, RECORDS[0], fmt=OutputFormat.CSV)

    lines = buffer.getvalue().rstrip("\r\n").splitlines()
    assert lines[0].startswith("id,first_name")
    assert len(lines) == 2


def test_render_detail_output_writes_file(tmp_path: Path) -> None:
    console, _ = _console()
    target = tmp_path / "detail.json"

    render_detail(console, RECORDS[0], fmt=OutputFormat.JSON, output=str(target))

    assert json.loads(target.read_text(encoding="utf-8"))["id"] == "m1"


def test_render_stats_csv_writes_single_row() -> None:
    console, buffer = _console()

    render_stats(console, STATS, fmt=OutputFormat.CSV)

    lines = buffer.getvalue().rstrip("\r\n").splitlines()
    assert lines[0].startswith("total_rides,member_count")
    assert lines[1].startswith("3,42,100.5,2")
