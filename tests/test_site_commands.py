"""Stage 1: website command wording, about/hq, the live board and talk bingo."""

from __future__ import annotations

import json
import re
import shlex
from datetime import UTC, datetime
from pathlib import Path

import click
import httpx
import pytest
from click.testing import CliRunner

from agenteng import __version__
from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Catalogue, Request, canonical_city
from agenteng.output import make_console
from agenteng.render import live_board, play_bingo, render_result
from agenteng.screens import BINGO_TERMS, FREE, bingo_pool, winning_lines
from agenteng.service import Service

ROOT = Path(__file__).resolve().parents[1]
TSV = ROOT / "tests/fixtures/site_commands.tsv"
LONDON = "agenteng-london-2026"


def site_rows():
    rows = []
    for line in TSV.read_text().splitlines():
        if line and not line.startswith("#"):
            status, command, site_file, runs_as, note = (line.split("\t") + [""] * 5)[:5]
            rows.append((status, command, site_file, runs_as, note))
    return rows


def run(*args, env=None):
    runner = CliRunner()
    return runner.invoke(main, list(args), env={"AGENTENG_OUTPUT": "json", **(env or {})})


def run_line(command: str):
    argv = shlex.split(command)
    assert argv[0] == "agenteng"
    return run(*argv[1:])


def data(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["data"]


@pytest.fixture
def service():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 4, 12, tzinfo=UTC))


# --- every command shown on the website ---------------------------------------


@pytest.mark.parametrize("row", site_rows(), ids=lambda r: r[1])
def test_site_command_status_is_true(row):
    status, command, _, runs_as, _ = row
    outcome = run_line(command)
    if status in {"works", "alias"}:
        assert outcome.exit_code == 0, outcome.output
        assert runs_as == command
    else:
        assert outcome.exit_code != 0, f"{command} now works; mark it alias or works"
    if status == "change":
        assert run_line(runs_as).exit_code == 0, runs_as
    if status == "missing":
        assert not runs_as


def test_site_sync_doc_lists_every_site_command():
    doc = (ROOT / "docs/SITE-SYNC.md").read_text()
    rows = site_rows()
    assert len(rows) == 45
    for status, command, site_file, runs_as, _ in rows:
        assert f"`{command}`" in doc, command
        if status == "change":
            assert f"`{runs_as}`" in doc, runs_as
    assert "\N{EM DASH}" not in doc


# --- aliases keep the existing JSON -----------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("san-francisco", "San Francisco"),
        ("San_Francisco", "San Francisco"),
        ("SF", "San Francisco"),
        ("london", "London"),
        ("San Francisco", "San Francisco"),
        ("Paris", "Paris"),
        (None, None),
    ],
)
def test_canonical_city(value, expected):
    assert canonical_city(value) == expected
    assert Request(operation="events", city=value).city == expected


@pytest.mark.parametrize(
    "alias, canonical",
    [
        (["events", "--city", "san-francisco"], ["events", "--city", "San Francisco"]),
        (
            ["events", "--next", "san-francisco"],
            ["events", "--city", "San Francisco", "--upcoming"],
        ),
        (["events", "--london", "--next"], ["events", "--city", "London", "--upcoming"]),
        (["events", "--london", "--history"], ["events", "--city", "London", "--past"]),
        (["events", "--previous"], ["events", "--past"]),
        (["events", "london"], ["events", "--city", "London"]),
        (["agenda", "--london"], ["agenda", LONDON]),
        (["agenda", "london"], ["agenda", LONDON]),
        (["tickets", "--london"], ["tickets", LONDON]),
        (["venue", "--london"], ["venue", LONDON]),
        (["event", "--london"], ["event", LONDON]),
        (["plan", "--london", "--interest", "memory"], ["plan", LONDON, "--interest", "memory"]),
        (["sponsors", "--sf"], ["sponsors", "--city", "San Francisco"]),
        (["speakers", "--sf"], ["speakers", "--city", "San Francisco"]),
        (["discover", "--city", "san-francisco"], ["discover", "--city", "San Francisco"]),
        (["inspect", "--speaker", "samuel-colvin"], ["speaker", "samuel-colvin"]),
        (["--list-disciplines"], ["disciplines"]),
        (["--themes"], ["themes"]),
        (["--list-cities"], ["discover"]),
        (["--info"], ["about"]),
        (["whoami", "--chair"], ["about", "--chair"]),
        (["now", "--at", "10:40"], ["now", "--at", "2026-10-16T10:40"]),
    ],
)
def test_alias_matches_canonical_json(alias, canonical):
    assert data(run(*alias)) == data(run(*canonical))


def test_sf_city_events_resolve_to_next_sf_event():
    assert data(run("event", "--sf"))[0]["id"] == "sf-code-engineering-2026"


def test_aliases_stay_out_of_help():
    top = run("--help").output
    for hidden in ["--list-disciplines", "--list-cities", "--info", "inspect", "whoami"]:
        assert hidden not in top
    events_help = run("events", "--help").output
    assert "--upcoming, --next" in events_help
    assert "--past, --history, --previous" in events_help
    assert "--london" not in events_help


def test_discover_rejects_unknown_city():
    assert run("discover", "--city", "paris").exit_code == 2


# --- about and hq: published data only ---------------------------------------------


def test_about_uses_published_site_data(service):
    result = service.lookup(Request(operation="about"))
    assert result.status == "ok"
    about = result.data
    catalogue = service.catalogue
    assert about["chair"] == catalogue.about.chair.model_dump(mode="json")
    assert about["organiser"]["name"] == "Superagentic AI"
    assert about["definition"].startswith("Agent Engineering is the discipline")
    assert about["cities"] == ["London", "San Francisco"]
    evidence = " ".join(s.text for s in result.sources)
    for text in [about["definition"], about["chair"]["name"], about["chair"]["bio"]]:
        assert text in evidence
    connect = about["connect"]
    assert connect["mcp_url"] == "https://a2a.agentengineering.world/mcp/"
    assert connect["agent_card_url"].endswith("/.well-known/agent-card.json")
    assert "install.sh | sh" in connect["install"]


@pytest.mark.parametrize("section", ["chair", "organiser", "connect"])
def test_about_sections(service, section):
    result = service.lookup(Request(operation="about", section=section))
    assert set(result.data) == {"section", section}


def test_about_without_published_card_omits_it(service):
    service.catalogue = service.catalogue.model_copy(update={"about": None})
    full = service.lookup(Request(operation="about"))
    assert full.status == "ok" and full.data["chair"] is None
    assert service.lookup(Request(operation="about", section="chair")).status == "not_found"


def test_hq_content_and_sections(service):
    hq = service.lookup(Request(operation="hq"))
    assert hq.status == "ok"
    assert len(hq.data["manifesto"]) == 5
    assert hq.data["manifesto"][0].startswith("Agents are not features.")
    assert {p["title"] for p in hq.data["mindset"]} >= {"Non-Determinism", "Agent Networking"}
    assert all(r["url"].startswith("https://") for r in hq.data["further_reading"])
    assert {s.id for s in hq.sources} == {"hq-manifesto", "hq-mindset", "hq-further-reading"}
    reading = service.lookup(Request(operation="hq", section="reading"))
    assert set(reading.data) == {"section", "url", "further_reading", "further_reading_intro"}
    assert [s.id for s in reading.sources] == ["hq-further-reading"]


def test_hq_section_must_match_operation():
    with pytest.raises(ValueError):
        Request(operation="hq", section="chair")
    with pytest.raises(ValueError):
        Request(operation="events", section="manifesto")


def test_catalogue_requires_evidence_for_hq_and_about(service):
    raw = service.catalogue.model_dump(mode="json")
    raw["hq"]["source_ids"] = ["missing-source"]
    with pytest.raises(ValueError, match="Missing evidence"):
        Catalogue.model_validate(raw)


def test_hq_and_about_render(service):
    for operation in ["about", "hq"]:
        console = make_console(record=True, width=100)
        render_result(service.lookup(Request(operation=operation)), operation, console)
        text = console.export_text()
        assert "\N{EM DASH}" not in text
    assert "Shashi Jagtap" in render_text(service, "about")
    assert "The Agent Engineering Manifesto" in render_text(service, "hq")


def render_text(service, operation, **kwargs):
    console = make_console(record=True, width=100)
    render_result(service.lookup(Request(operation=operation, **kwargs)), operation, console)
    return console.export_text()


# --- live board ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "at, phase, current, upcoming",
    [
        ("2026-10-16T07:30:00", "before", None, "Doors, registration, tea and pastries"),
        ("2026-10-16T10:40:00", "during", "samuel-colvin", "Networking break"),
        ("2026-10-16T10:40:00+01:00", "during", "samuel-colvin", "Networking break"),
        ("2026-10-16T09:40:00Z", "during", "samuel-colvin", "Networking break"),
        ("2026-10-16T20:00:00", "after", None, None),
    ],
)
def test_live_snapshot(service, at, phase, current, upcoming):
    result = service.lookup(Request(operation="live", at=at))
    assert result.status == "ok"
    snap = result.data
    assert snap["event_id"] == LONDON and snap["phase"] == phase
    assert snap["event"]["track"] == "single"
    assert (snap["current"] or {}).get("speaker_id") == current
    assert (snap["next"] or {}).get("title") == upcoming
    if current:
        assert 0 < snap["current"]["progress"] < 1
        assert snap["current"]["remaining_seconds"] == 15 * 60
        assert snap["next"]["starts_in_seconds"] == 20 * 60


def test_live_uses_service_clock_without_at(service):
    snap = service.lookup(Request(operation="live")).data
    assert snap["phase"] == "before" and snap["as_of"].startswith("2026-10-04T13:00")


def test_live_without_timed_agenda(service):
    result = service.lookup(Request(operation="live", event_id="sf-code-engineering-2026"))
    assert result.status == "not_found"


def test_at_only_for_clock_operations():
    with pytest.raises(ValueError):
        Request(operation="events", at="2026-10-16T10:00:00")


def test_live_cli_snapshot_and_now_screen_alias():
    snapshot = data(run("live", "--at", "10:40"))
    assert snapshot["current"]["speaker_id"] == "samuel-colvin"
    assert data(run("now", "--screen", "--at", "10:40")) == snapshot
    assert data(run("live", "--event", "london", "--at", "10:40")) == snapshot
    assert run("live", "--at", "soon").exit_code != 0


def test_live_board_renders_frame(service):
    result = service.lookup(Request(operation="live", at="2026-10-16T10:40:00"))
    console = make_console(record=True, width=110)
    console.print(live_board(result), height=34)
    text = console.export_text()
    for expected in [
        "AGENTENG LONDON 2026",
        "NOW",
        "NEXT UP",
        "LATER",
        "Samuel Colvin",
        "15 min left",
    ]:
        assert expected in text
    assert "Single track" in text and "Ctrl-C" in text


def test_run_live_screen_once_and_clock_advance(monkeypatch):
    from agenteng import render

    seen = []
    real = render.live_board
    monkeypatch.setattr(render, "live_board", lambda r: seen.append(r) or real(r))
    ctx = click.Context(
        click.Command("ae"), obj={"remote": None, "catalogue": None, "as_json": False}
    )
    console = make_console(record=True, width=110)
    render.run_live_screen(
        ctx,
        {"operation": "live", "at": "2026-10-16T10:40:00"},
        refresh=1,
        once=True,
        console=console,
    )
    assert seen and seen[0].data["current"]["speaker_id"] == "samuel-colvin"
    assert "Samuel Colvin" in console.export_text()


def test_run_live_screen_exits_on_ctrl_c(monkeypatch):
    from agenteng import render

    calls = []

    def boom(seconds):
        calls.append(seconds)
        raise KeyboardInterrupt

    monkeypatch.setattr("time.sleep", boom)
    ctx = click.Context(
        click.Command("ae"), obj={"remote": None, "catalogue": None, "as_json": False}
    )
    console = make_console(record=True, width=110)
    render.run_live_screen(
        ctx, {"operation": "live", "at": "2026-10-16T10:40:00"}, refresh=7, console=console
    )
    assert calls == [7]


# --- bingo --------------------------------------------------------------------------


def card(service, **kwargs):
    result = service.lookup(Request(operation="bingo", **kwargs))
    assert result.status == "ok", result.answer
    return result


def test_bingo_is_reproducible(service):
    first = card(service, seed=42).data
    assert card(service, seed=42).data["grid"] == first["grid"]
    assert card(service, seed=43).data["grid"] != first["grid"]
    assert first["command"] == f"ae bingo --event {LONDON} --size 5 --seed 42"


def test_bingo_without_seed_reports_its_seed(service):
    random_card = card(service).data
    assert card(service, seed=random_card["seed"]).data["grid"] == random_card["grid"]


@pytest.mark.parametrize("size", [4, 5])
def test_bingo_shape_and_evidence(service, size):
    result = card(service, seed=7, size=size)
    grid = result.data["grid"]
    assert len(grid) == size and all(len(row) == size for row in grid)
    labels = [label for row in grid for label in row]
    assert len(set(labels)) == len(labels)
    assert (grid[2][2] == FREE) == (size == 5)
    assert labels.count(FREE) == (1 if size == 5 else 0)
    sessions = service.session_map()
    for square in result.data["squares"]:
        if square.get("free"):
            continue
        assert square["session_ids"], square
        assert all(sessions[s].event_id == LONDON for s in square["session_ids"])


def test_bingo_terms_are_evidenced_in_published_text(service):
    speakers, sessions = service.speaker_map(), service.session_map()
    patterns = dict(BINGO_TERMS)

    def published(session_id):
        session = sessions[session_id]
        speaker = speakers.get(session.speaker_id) if session.speaker_id else None
        return " ".join(filter(None, [session.title, speaker and speaker.abstract]))

    for term in bingo_pool(service, LONDON):
        if term["label"] in patterns:
            assert any(
                re.search(patterns[term["label"]], published(s), re.IGNORECASE)
                for s in term["session_ids"]
            ), term
        else:  # discipline titles come from the speakers' published disciplines
            assert term["label"].endswith("Engineering") and term["session_ids"], term


def test_bingo_artifacts(service):
    text = card(service, seed=7, format="text").artifact
    assert "AGENTENG TALK BINGO" in text and "--seed 7" in text and FREE in text
    svg = card(service, seed=7, format="svg").artifact
    assert svg.startswith("<svg") and svg.count("<rect") >= 26
    page = card(service, seed=7, format="html").artifact
    assert page.startswith("<!doctype html>") and "@media print" in page and "<svg" in page
    for artifact in [text, svg, page]:
        assert "\N{EM DASH}" not in artifact


def test_bingo_thin_event_is_unavailable(service):
    result = service.lookup(
        Request(operation="bingo", event_id="sf-harness-engineering-2026", size=4)
    )
    assert result.status == "unavailable" and result.data["needed"] == 16


def test_bingo_fields_only_for_bingo():
    for bad in [dict(seed=1), dict(size=4), dict(format="svg")]:
        with pytest.raises(ValueError):
            Request(operation="events", **bad)


def test_bingo_cli_formats_and_output(tmp_path):
    assert data(run("bingo", "--seed", "9"))["seed"] == 9
    runner = CliRunner()
    printed = runner.invoke(
        main, ["bingo", "--seed", "9", "--format", "text"], env={"AGENTENG_OUTPUT": ""}
    )
    assert printed.exit_code == 0 and "AGENTENG TALK BINGO" in printed.output
    target = tmp_path / "card.svg"
    wrote = runner.invoke(
        main, ["bingo", "--seed", "9", "--output", str(target)], env={"AGENTENG_OUTPUT": ""}
    )
    assert wrote.exit_code == 0 and target.read_text().startswith("<svg")
    assert run("bingo", "--play").exit_code != 0  # not a terminal


def test_winning_lines():
    assert winning_lines({(0, c) for c in range(5)}, 5) == ["row 1"]
    assert winning_lines({(r, 1) for r in range(4)}, 4) == ["column B"]
    assert winning_lines({(i, i) for i in range(5)}, 5) == ["diagonal"]
    assert winning_lines({(i, 3 - i) for i in range(4)}, 4) == ["anti-diagonal"]
    assert winning_lines({(0, 0)}, 5) == []


def test_play_bingo_marks_and_calls_bingo(service):
    result = card(service, seed=7)
    answers = iter(["A3", "B3", "zz", "D3", "E3", "q"])
    console = make_console(record=True, width=110)
    won = play_bingo(result, console, ask=lambda: next(answers))
    assert won == {"row 3"}
    text = console.export_text()
    assert "BINGO! row 3" in text and "Use a column letter" in text


def test_bingo_renders_in_terminal(service):
    console = make_console(record=True, width=100)
    render_result(card(service, seed=7), "bingo", console)
    text = console.export_text()
    assert "AGENTENG TALK BINGO" in text and "FREE" in text and "--seed 7" in text


# --- protocols ----------------------------------------------------------------------


def test_mcp_reports_agenteng_version():
    from starlette.testclient import TestClient

    from agenteng.server import create_app

    with TestClient(create_app(), base_url="https://a2a.agentengineering.world") as client:
        response = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["version"] == __version__


def test_http_query_serves_new_operations():
    from starlette.testclient import TestClient

    from agenteng.server import create_app

    with TestClient(create_app(), base_url="https://a2a.agentengineering.world") as client:
        for payload in [
            {"operation": "about", "section": "connect"},
            {"operation": "hq", "section": "manifesto"},
            {"operation": "live", "at": "2026-10-16T10:40:00+01:00"},
            {"operation": "bingo", "seed": 3, "size": 4, "format": "svg"},
        ]:
            response = client.post("/v1/query", json=payload)
            assert response.status_code == 200, payload
            assert response.json()["status"] == "ok", payload


def test_a2a_card_lists_event_day_skill():
    from starlette.testclient import TestClient

    from agenteng.server import create_app

    with TestClient(create_app(), base_url="https://a2a.agentengineering.world") as client:
        card_json = client.get("/.well-known/agent-card.json").json()
    skill = next(s for s in card_json["skills"] if s["id"] == "agenteng-event-day")
    for example in skill["examples"]:
        Request.model_validate_json(example)


def test_remote_requests_omit_defaults_for_older_servers():
    from agenteng.remote import RemoteService
    import asyncio

    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        service = Service()
        result = service.lookup(Request.model_validate(sent[-1]))
        return httpx.Response(200, json=result.model_dump(mode="json"))

    remote = RemoteService(
        "https://a2a.agentengineering.world", transport=httpx.MockTransport(handler)
    )
    asyncio.run(remote.execute(Request(operation="events", city="london")))
    assert sent == [{"operation": "events", "city": "London"}]


# --- interactive menu ---------------------------------------------------------------


def _menu_ctx():
    return click.Context(
        click.Command("ae"), obj={"remote": None, "catalogue": None, "as_json": False}
    )


def test_menu_lists_live_bingo_about_hq(monkeypatch):
    from agenteng import interactive

    seen = []

    def fake_select(message, choices, **kwargs):
        seen.append([getattr(c, "title", c) for c in choices])
        return "quit"

    monkeypatch.setattr(interactive, "_select", fake_select)
    interactive.run_menu(_menu_ctx())
    for title in [
        "Live now/next board (venue screen)",
        "Talk bingo card",
        "About Agent Engineering",
        "Agent Engineering HQ: manifesto and mindset",
    ]:
        assert title in seen[0]


def test_menu_about_and_bingo_actions(monkeypatch):
    from agenteng import interactive

    answers = iter(["about", "bingo", "show", "quit"])
    shown, invoked = [], []
    monkeypatch.setattr(interactive, "_select", lambda *a, **k: next(answers))
    monkeypatch.setattr(interactive, "_show", lambda ctx, payload: shown.append(payload))
    ctx = _menu_ctx()
    monkeypatch.setattr(ctx, "invoke", lambda cmd, **kw: invoked.append((cmd.name, kw)))
    interactive.run_menu(ctx)
    assert shown == [{"operation": "about"}]
    assert invoked == [("bingo", {"play": False})]
