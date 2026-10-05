# Copyright (c) 2026 Mark Buckaway.
# SPDX-License-Identifier: LicenseRef-Proprietary
# All rights reserved.
#
# This file is proprietary and confidential. Unauthorized copying, distribution,
# or use of this file, via any medium, is strictly prohibited without the
# express written permission of Mark Buckaway.
"""End-to-end CLI tests: real stack with the HTTP boundary mocked by respx."""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from cyql.cli.main import app
from cyql.models import Member
from cyql.queries import QUERIES, QuerySpec

URL = "https://api.cyql.app/api/graphql"
runner = CliRunner()


@pytest.fixture
def cli_env(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Point CYQL_CONFIG at a missing file so the real user config cannot leak in,
    # then supply a dummy key via the environment.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CYQL_CONFIG", str(tmp_path / "cyql-config.toml"))
    monkeypatch.setenv("CYQL_API_KEY", "test-key")
    yield


def _data(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"data": payload})


def _paged(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": items,
        "totalCount": len(items),
        "page": 1,
        "pageSize": 50,
        "hasNextPage": False,
    }


_STATS = {"totalRides": 3, "memberCount": 42, "totalKilometers": 100.5, "totalAdmins": 2}


@respx.mock
def test_stats_command_renders_member_count(cli_env: None) -> None:
    respx.post(URL).mock(return_value=_data({"clubStats": _STATS}))

    result = runner.invoke(app, ["stats"])

    assert result.exit_code == 0
    assert "42" in result.output


@respx.mock
def test_stats_command_json_emits_snake_case_keys(cli_env: None) -> None:
    respx.post(URL).mock(return_value=_data({"clubStats": _STATS}))

    result = runner.invoke(app, ["stats", "--json"])

    assert result.exit_code == 0
    assert "member_count" in result.output


@respx.mock
def test_nextride_renders_title(cli_env: None) -> None:
    respx.post(URL).mock(
        return_value=_data({"rides": {"items": [{"id": "r1", "title": "Dawn Patrol"}]}})
    )

    result = runner.invoke(app, ["nextride"])

    assert result.exit_code == 0
    assert "Dawn Patrol" in result.output


@respx.mock
def test_nextride_reports_when_no_upcoming(cli_env: None) -> None:
    respx.post(URL).mock(return_value=_data({"rides": {"items": []}}))

    result = runner.invoke(app, ["nextride"])

    assert result.exit_code == 0
    assert "No upcoming rides" in result.output


@respx.mock
def test_rides_lists_titles(cli_env: None) -> None:
    respx.post(URL).mock(return_value=_data({"rides": _paged([{"id": "r1", "title": "Loop A"}])}))

    result = runner.invoke(app, ["rides", "-n", "3"])

    assert result.exit_code == 0
    assert "Loop A" in result.output


@respx.mock
def test_ride_search_renders_match(cli_env: None) -> None:
    respx.post(URL).mock(
        return_value=_data({"rides": _paged([{"id": "r1", "title": "Gravel Grind"}])})
    )

    result = runner.invoke(app, ["ride", "gravel"])

    assert result.exit_code == 0
    assert "Gravel Grind" in result.output


@respx.mock
def test_ride_search_reports_no_match(cli_env: None) -> None:
    respx.post(URL).mock(return_value=_data({"rides": _paged([])}))

    result = runner.invoke(app, ["ride", "nope"])

    assert result.exit_code == 0
    assert "No ride matching" in result.output


@respx.mock
def test_members_lists_names(cli_env: None) -> None:
    member = {"id": "m1", "firstName": "Ada", "lastName": "L", "isAdmin": True}
    respx.post(URL).mock(return_value=_data({"members": _paged([member])}))

    result = runner.invoke(app, ["members"])

    assert result.exit_code == 0
    assert "Ada" in result.output


@respx.mock
def test_events_lists_titles(cli_env: None) -> None:
    respx.post(URL).mock(
        return_value=_data({"events": _paged([{"id": "e1", "title": "EPIC Festival"}])})
    )

    result = runner.invoke(app, ["events"])

    assert result.exit_code == 0
    assert "EPIC Festival" in result.output


@respx.mock
def test_news_lists_titles(cli_env: None) -> None:
    respx.post(URL).mock(
        return_value=_data({"news": _paged([{"id": "n1", "title": "Trail Day"}])})
    )

    result = runner.invoke(app, ["news"])

    assert result.exit_code == 0
    assert "Trail Day" in result.output


@respx.mock
def test_club_renders_name(cli_env: None) -> None:
    respx.post(URL).mock(
        return_value=_data({"clubInfo": {"title": "GORBA", "city": "Guelph", "email": "e@g.ca"}})
    )

    result = runner.invoke(app, ["club"])

    assert result.exit_code == 0
    assert "GORBA" in result.output


@respx.mock
def test_nextride_localizes_time_to_configured_timezone(
    cli_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CYQL_TIMEZONE", "America/Toronto")
    ride = {"id": "r1", "title": "Dawn", "startTime": "2026-06-16T23:00:00Z"}
    respx.post(URL).mock(return_value=_data({"rides": {"items": [ride]}}))

    result = runner.invoke(app, ["nextride"])

    assert result.exit_code == 0
    assert "19:00" in result.output  # 23:00 UTC -> 19:00 EDT


@respx.mock
def test_unknown_timezone_falls_back_to_local(
    cli_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CYQL_TIMEZONE", "Not/AZone")
    ride = {"id": "r1", "title": "Dawn", "startTime": "2026-06-16T23:00:00Z"}
    respx.post(URL).mock(return_value=_data({"rides": {"items": [ride]}}))

    result = runner.invoke(app, ["nextride"])

    assert result.exit_code == 0
    assert "Dawn" in result.output


@respx.mock
def test_api_error_exits_nonzero(cli_env: None) -> None:
    respx.post(URL).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "ApiKeyInvalid"}]})
    )

    result = runner.invoke(app, ["stats"])

    assert result.exit_code == 1


def test_missing_credentials_exits_nonzero(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CYQL_CONFIG", str(tmp_path / "cyql-config.toml"))
    monkeypatch.delenv("CYQL_API_KEY", raising=False)

    result = runner.invoke(app, ["stats"])

    assert result.exit_code == 1


# --- Output formats and the extended command surface ------------------------

RIDE_ID = "11111111-1111-1111-1111-111111111111"
MEMBER_ID = "aaaaaaaa-0000-0000-0000-000000000001"
NEWS_ID = "ffffffff-0000-0000-0000-000000000001"
EVENT_ID = "eeeeeeee-0000-0000-0000-000000000001"
CHALLENGE_ID = "cccccccc-0000-0000-0000-000000000001"
GPX_ID = "gggggggg-0000-0000-0000-000000000001"


def _last_variables(route: Any) -> dict[str, Any]:
    return json.loads(route.calls.last.request.content)["variables"]


@respx.mock
def test_json_and_csv_are_mutually_exclusive(cli_env: None) -> None:
    result = runner.invoke(app, ["stats", "--json", "--csv"])

    assert result.exit_code == 2
    assert "--json and --csv are mutually exclusive" in result.output


@respx.mock
def test_rides_defaults_to_upcoming(cli_env: None) -> None:
    route = respx.post(URL).mock(
        return_value=_data({"rides": _paged([{"id": "r1", "title": "Loop"}])})
    )

    result = runner.invoke(app, ["rides"])

    assert result.exit_code == 0
    assert _last_variables(route)["isUpcoming"] is True


@respx.mock
def test_rides_all_flag_requests_past_rides(cli_env: None) -> None:
    route = respx.post(URL).mock(
        return_value=_data({"rides": _paged([{"id": "r1", "title": "Old Loop"}])})
    )

    result = runner.invoke(app, ["rides", "--all"])

    assert result.exit_code == 0
    assert _last_variables(route)["isUpcoming"] is None


@respx.mock
def test_rides_search_passes_search_term(cli_env: None) -> None:
    route = respx.post(URL).mock(return_value=_data({"rides": _paged([])}))

    result = runner.invoke(app, ["rides", "--search", "gravel"])

    assert result.exit_code == 0
    assert _last_variables(route)["search"] == "gravel"


@respx.mock
def test_rides_zero_count_renders_no_rows(cli_env: None) -> None:
    respx.post(URL).mock(return_value=_data({"rides": _paged([{"id": "r1"}])}))

    result = runner.invoke(app, ["rides", "-n", "0"])

    assert result.exit_code == 0
    assert "r1" not in result.output


@respx.mock
def test_rides_csv_output_writes_file(cli_env: None, tmp_path: Any) -> None:
    respx.post(URL).mock(
        return_value=_data({"rides": _paged([{"id": "r1", "title": "Loop A"}])})
    )
    target = tmp_path / "rides.csv"

    result = runner.invoke(app, ["rides", "--csv", "--output", str(target)])

    assert result.exit_code == 0
    assert "Loop A" in target.read_text(encoding="utf-8")
    assert result.output.strip() == ""


@respx.mock
def test_members_status_normalizes_to_enum_value(cli_env: None) -> None:
    route = respx.post(URL).mock(
        return_value=_data({"members": _paged([{"id": "m1", "firstName": "Ada"}])})
    )

    result = runner.invoke(app, ["members", "--status", "approved"])

    assert result.exit_code == 0
    assert _last_variables(route)["memberStatus"] == "APPROVED"


def test_members_unknown_status_exits_two(cli_env: None) -> None:
    result = runner.invoke(app, ["members", "--status", "bogus"])

    assert result.exit_code == 2


@respx.mock
def test_members_search_passes_search_term(cli_env: None) -> None:
    route = respx.post(URL).mock(return_value=_data({"members": _paged([])}))

    result = runner.invoke(app, ["members", "--search", "ada"])

    assert result.exit_code == 0
    assert _last_variables(route)["search"] == "ada"


@respx.mock
def test_events_fetch_type_passes_value(cli_env: None) -> None:
    route = respx.post(URL).mock(return_value=_data({"events": _paged([])}))

    result = runner.invoke(app, ["events", "--fetch-type", "upcoming"])

    assert result.exit_code == 0
    assert _last_variables(route)["fetchType"] == "upcoming"


@respx.mock
def test_news_search_passes_search_term(cli_env: None) -> None:
    route = respx.post(URL).mock(return_value=_data({"news": _paged([])}))

    result = runner.invoke(app, ["news", "--search", "trail"])

    assert result.exit_code == 0
    assert _last_variables(route)["search"] == "trail"


_LIST_CASES = [
    pytest.param(
        ["ride-participants", RIDE_ID],
        "rideParticipants",
        {"firstName": "Ada"},
        "Ride participants",
        "first_name",
        "member_id",
        id="ride-participants",
    ),
    pytest.param(
        ["challenges"],
        "challenges",
        {"title": "Summer"},
        "Challenges",
        "title",
        "id",
        id="challenges",
    ),
    pytest.param(
        ["challenge-scores", CHALLENGE_ID],
        "challengeScores",
        {"memberName": "Grace"},
        "Challenge scores",
        "member_name",
        "member_id",
        id="challenge-scores",
    ),
    pytest.param(
        ["gpx"],
        "gpxRoutes",
        {"title": "Riverside"},
        "GPX routes",
        "title",
        "id",
        id="gpx",
    ),
]


@pytest.mark.parametrize(
    ("args", "root", "item", "title", "json_key", "csv_key"), _LIST_CASES
)
@respx.mock
def test_new_list_command_renders_table(
    cli_env: None,
    args: list[str],
    root: str,
    item: dict[str, Any],
    title: str,
    json_key: str,
    csv_key: str,
) -> None:
    respx.post(URL).mock(return_value=_data({root: _paged([item])}))

    result = runner.invoke(app, list(args))

    assert result.exit_code == 0
    assert title in result.output


@pytest.mark.parametrize(
    ("args", "root", "item", "title", "json_key", "csv_key"), _LIST_CASES
)
@respx.mock
def test_new_list_command_json_uses_snake_case_keys(
    cli_env: None,
    args: list[str],
    root: str,
    item: dict[str, Any],
    title: str,
    json_key: str,
    csv_key: str,
) -> None:
    respx.post(URL).mock(return_value=_data({root: _paged([item])}))

    result = runner.invoke(app, [*args, "--json"])

    assert result.exit_code == 0
    assert f'"{json_key}"' in result.output


@pytest.mark.parametrize(
    ("args", "root", "item", "title", "json_key", "csv_key"), _LIST_CASES
)
@respx.mock
def test_new_list_command_csv_output_writes_file(
    cli_env: None,
    tmp_path: Any,
    args: list[str],
    root: str,
    item: dict[str, Any],
    title: str,
    json_key: str,
    csv_key: str,
) -> None:
    respx.post(URL).mock(return_value=_data({root: _paged([item])}))
    target = tmp_path / "out.csv"

    result = runner.invoke(app, [*args, "--csv", "--output", str(target)])

    assert result.exit_code == 0
    assert csv_key in target.read_text(encoding="utf-8")
    assert result.output.strip() == ""


_DETAIL_CASES = [
    pytest.param(
        ["member", MEMBER_ID],
        "memberById",
        {"id": MEMBER_ID, "firstName": "Ada"},
        "Ada",
        "first_name",
        id="member",
    ),
    pytest.param(
        ["news-post", NEWS_ID],
        "newsById",
        {"id": NEWS_ID, "title": "Trails open"},
        "Trails open",
        "title",
        id="news-post",
    ),
    pytest.param(
        ["event", EVENT_ID],
        "eventById",
        {"id": EVENT_ID, "title": "EPIC Festival"},
        "EPIC Festival",
        "title",
        id="event",
    ),
    pytest.param(
        ["challenge", CHALLENGE_ID],
        "challengeById",
        {"id": CHALLENGE_ID, "title": "Summer Challenge"},
        "Summer Challenge",
        "title",
        id="challenge",
    ),
    pytest.param(
        ["gpx-route", GPX_ID],
        "gpxRouteById",
        {"id": GPX_ID, "title": "Riverside Loop"},
        "Riverside Loop",
        "title",
        id="gpx-route",
    ),
]


@pytest.mark.parametrize(("args", "root", "item", "cell", "json_key"), _DETAIL_CASES)
@respx.mock
def test_new_detail_command_shows_record(
    cli_env: None,
    args: list[str],
    root: str,
    item: dict[str, Any],
    cell: str,
    json_key: str,
) -> None:
    respx.post(URL).mock(return_value=_data({root: item}))

    result = runner.invoke(app, list(args))

    assert result.exit_code == 0
    assert cell in result.output


@pytest.mark.parametrize(("args", "root", "item", "cell", "json_key"), _DETAIL_CASES)
@respx.mock
def test_new_detail_command_json_uses_snake_case_keys(
    cli_env: None,
    args: list[str],
    root: str,
    item: dict[str, Any],
    cell: str,
    json_key: str,
) -> None:
    respx.post(URL).mock(return_value=_data({root: item}))

    result = runner.invoke(app, [*args, "--json"])

    assert result.exit_code == 0
    assert f'"{json_key}"' in result.output


@pytest.mark.parametrize(("args", "root", "item", "cell", "json_key"), _DETAIL_CASES)
@respx.mock
def test_new_detail_command_csv_output_writes_file(
    cli_env: None,
    tmp_path: Any,
    args: list[str],
    root: str,
    item: dict[str, Any],
    cell: str,
    json_key: str,
) -> None:
    respx.post(URL).mock(return_value=_data({root: item}))
    target = tmp_path / "detail.csv"

    result = runner.invoke(app, [*args, "--csv", "--output", str(target)])

    assert result.exit_code == 0
    assert json_key in target.read_text(encoding="utf-8")
    assert result.output.strip() == ""


_NOT_FOUND_CASES = [
    pytest.param(["member", MEMBER_ID], "memberById", "No member with id", id="member"),
    pytest.param(
        ["news-post", NEWS_ID], "newsById", "No news article with id", id="news-post"
    ),
    pytest.param(["event", EVENT_ID], "eventById", "No event with id", id="event"),
    pytest.param(
        ["challenge", CHALLENGE_ID],
        "challengeById",
        "No challenge with id",
        id="challenge",
    ),
    pytest.param(
        ["gpx-route", GPX_ID], "gpxRouteById", "No GPX route with id", id="gpx-route"
    ),
]


@pytest.mark.parametrize(("args", "root", "message"), _NOT_FOUND_CASES)
@respx.mock
def test_detail_command_reports_when_missing(
    cli_env: None, args: list[str], root: str, message: str
) -> None:
    respx.post(URL).mock(return_value=_data({root: None}))

    result = runner.invoke(app, list(args))

    assert result.exit_code == 0
    assert message in result.output


def test_query_list_renders_available_queries(cli_env: None) -> None:
    result = runner.invoke(app, ["query", "--list"])

    assert result.exit_code == 0
    assert "active-ride-leaders" in result.output


def test_query_list_json_emits_registry_entries(cli_env: None) -> None:
    result = runner.invoke(app, ["query", "--list", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == [
        {
            "name": "active-ride-leaders",
            "description": (
                "Distinct ride leaders listed on rides in the current year"
            ),
        }
    ]


def test_query_list_csv_output_writes_file(cli_env: None, tmp_path: Any) -> None:
    target = tmp_path / "queries.csv"

    result = runner.invoke(app, ["query", "--list", "--csv", "--output", str(target)])

    assert result.exit_code == 0
    assert "active-ride-leaders" in target.read_text(encoding="utf-8")
    assert result.output.strip() == ""


def test_query_list_does_not_require_credentials(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CYQL_CONFIG", str(tmp_path / "cyql-config.toml"))
    monkeypatch.delenv("CYQL_API_KEY", raising=False)

    result = runner.invoke(app, ["query", "--list"])

    assert result.exit_code == 0
    assert "active-ride-leaders" in result.output


def test_query_without_name_or_list_exits_two(cli_env: None) -> None:
    result = runner.invoke(app, ["query"])

    assert result.exit_code == 2
    assert "provide a query name or --list" in result.output


def test_query_unknown_name_reports_error(cli_env: None) -> None:
    result = runner.invoke(app, ["query", "no-such-query"])

    assert result.exit_code == 1
    assert "unknown query: no-such-query" in result.output


def test_query_active_ride_leaders_reports_missing_club_id(cli_env: None) -> None:
    result = runner.invoke(app, ["query", "active-ride-leaders"])

    assert result.exit_code == 1
    assert "club_id is not set" in result.output


def test_query_runs_registered_query(
    cli_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = [Member(id="m1", first_name="Ada")]
    spec = QuerySpec(
        name="unit-test-run", description="demo", run=lambda client: records
    )
    monkeypatch.setitem(QUERIES, spec.name, spec)

    result = runner.invoke(app, ["query", "unit-test-run"])

    assert result.exit_code == 0
    assert "unit-test-run" in result.output
    assert "Ada" in result.output
