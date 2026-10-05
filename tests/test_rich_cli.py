"""Output mode selection, rich renderers and interactive menu."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.output import display_text, make_console, use_json
from agenteng.render import render_result
from agenteng.service import Service


OPERATIONS = [
    ("events", {"upcoming": True}),
    ("event", {"event_id": "agenteng-london-2026"}),
    ("speakers", {"event_id": "agenteng-london-2026"}),
    ("speaker", {"speaker_id": "samuel-colvin"}),
    ("talks", {"event_id": "agenteng-london-2026"}),
    ("talk", {"speaker_id": "samuel-colvin"}),
    ("faq", {"query": "tickets"}),
    ("venue", {"event_id": "agenteng-london-2026"}),
    ("sponsors", {}),
    ("conduct", {}),
    ("themes", {}),
    ("agenda", {"event_id": "agenteng-london-2026"}),
    ("tickets", {"event_id": "agenteng-london-2026"}),
    ("recordings", {}),
    ("search", {"query": "memory"}),
    ("disciplines", {}),
    ("tools", {"discipline": "memory", "limit": 5}),
    ("tool", {"tool_id": "langgraph"}),
    ("discover", {}),
    ("plan", {"event_id": "agenteng-london-2026", "interests": ["memory"]}),
    ("participate", {}),
]


def test_display_text_strips_em_dash():
    assert "\N{EM DASH}" not in display_text("AgentEng \N{EM DASH} Conference")
    assert " - " in display_text("AgentEng \N{EM DASH} Conference")


def test_friendly_date_and_event_label():
    from agenteng.render import event_label, friendly_date

    event = {
        "id": "agenteng-london-2026",
        "title": "AgentEng London 2026",
        "city": "London",
        "date": "2026-10-16",
        "date_precision": "day",
    }
    assert friendly_date(event) == "Fri 16 Oct 2026"
    assert event_label(event) == "AgentEng London 2026 · London · Fri 16 Oct 2026"
    month = {**event, "date": "2026-07", "date_precision": "month", "title": "Meetup"}
    assert friendly_date(month) == "Jul 2026"


def test_discover_description_wraps_fully():
    import asyncio

    console = make_console(record=True, width=88)
    service = Service(Settings.from_env())
    result = asyncio.run(service.execute(Request(operation="discover")))
    render_result(result, "discover", console)
    text = console.export_text()
    # Rich may wrap mid-phrase depending on panel chrome width; compare collapsed.
    collapsed = " ".join(text.split())
    assert "technical events" in collapsed
    assert "and te " not in collapsed
    assert "operating AI agents" in collapsed


def test_use_json_flag_and_env(monkeypatch):
    class Obj:
        def __init__(self, as_json=False):
            self.obj = {"as_json": as_json}

    assert use_json(Obj(True)) is True
    monkeypatch.setenv("AGENTENG_OUTPUT", "json")
    assert use_json(Obj(False)) is True
    monkeypatch.delenv("AGENTENG_OUTPUT")
    with patch("agenteng.output.stdout_is_tty", return_value=False):
        assert use_json(Obj(False)) is True
    with patch("agenteng.output.stdout_is_tty", return_value=True):
        assert use_json(Obj(False)) is False


def test_json_flag_unchanged_shape():
    runner = CliRunner()
    result = runner.invoke(main, ["--json", "events", "--upcoming"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["engine"] == "lookup"
    assert isinstance(payload["data"], list)
    assert {"id", "title", "city", "offers", "state"} <= set(payload["data"][0])


def test_pipe_defaults_to_result_json():
    runner = CliRunner()
    result = runner.invoke(main, ["events", "--upcoming"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert isinstance(payload["data"], list)


def test_env_forces_json_even_if_tty(monkeypatch):
    runner = CliRunner(env={"AGENTENG_OUTPUT": "json"})
    with (
        patch("agenteng.cli.stdout_is_tty", return_value=True),
        patch("agenteng.output.stdout_is_tty", return_value=True),
    ):
        result = runner.invoke(main, ["events", "--upcoming"], env={"AGENTENG_OUTPUT": "json"})
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["engine"] == "lookup"


def test_tty_uses_rich_not_raw_json():
    runner = CliRunner()
    with (
        patch("agenteng.cli.stdout_is_tty", return_value=True),
        patch("agenteng.output.stdout_is_tty", return_value=True),
    ):
        result = runner.invoke(main, ["events", "--upcoming"])
    assert result.exit_code == 0, result.output
    assert "AgentEng London" in result.output
    assert "upcoming" in result.output
    # Should not be a bare Result JSON document.
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)


def test_missing_event_id_errors_without_tty():
    runner = CliRunner()
    result = runner.invoke(main, ["tickets"])
    assert result.exit_code != 0
    assert "event_id is required" in result.output


def test_no_args_without_tty_prints_help():
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output


@pytest.mark.asyncio
async def test_renderers_do_not_crash_on_catalogue():
    service = Service(Settings.from_env())
    console = make_console(record=True, width=88)
    for operation, kwargs in OPERATIONS:
        result = await service.execute(Request(operation=operation, **kwargs))
        assert result.status in {"ok", "not_found", "unavailable"}, operation
        render_result(result, operation, console)
    text = console.export_text()
    assert "AgentEng" in text or "Events" in text
    assert "\u2014" not in text  # no em dashes in rendered UI


def test_interactive_menu_quit(monkeypatch):
    runner = CliRunner()
    answers = iter(["quit"])

    def fake_select(message, choices, **kwargs):
        return next(answers)

    with (
        patch("agenteng.cli.stdout_is_tty", return_value=True),
        patch("agenteng.cli.stdin_is_tty", return_value=True),
        patch("agenteng.interactive.stdout_is_tty", return_value=True),
        patch("agenteng.interactive.stdin_is_tty", return_value=True),
        patch("agenteng.interactive._select", side_effect=fake_select),
    ):
        result = runner.invoke(main, [], input="\n")
    assert result.exit_code == 0, result.output
    assert "Bye" in result.output


def test_interactive_browse_event_overview(monkeypatch):
    runner = CliRunner()
    london = {
        "id": "agenteng-london-2026",
        "title": "AgentEng London 2026",
        "city": "London",
        "date": "2026-10-16",
        "date_precision": "day",
        "state": "upcoming",
    }
    # Main menu -> events -> pick london dict -> overview -> back -> quit
    picks = iter(
        [
            "events",
            london,
            "overview",
            "back",
            "quit",
        ]
    )

    def fake_select(message, choices, **kwargs):
        return next(picks)

    with (
        patch("agenteng.cli.stdout_is_tty", return_value=True),
        patch("agenteng.cli.stdin_is_tty", return_value=True),
        patch("agenteng.interactive.stdout_is_tty", return_value=True),
        patch("agenteng.interactive.stdin_is_tty", return_value=True),
        patch("agenteng.output.stdout_is_tty", return_value=True),
        patch("agenteng.interactive._select", side_effect=fake_select),
    ):
        result = runner.invoke(main, [])
    assert result.exit_code == 0, result.output
    assert "AgentEng London" in result.output
    assert "Fri 16 Oct 2026" in result.output or "16 Oct 2026" in result.output
    assert "Bye" in result.output


def test_speaker_human_output_shows_abstract_once():
    import asyncio

    console = make_console(record=True, width=88)
    service = Service(Settings.from_env())
    result = asyncio.run(service.execute(Request(operation="speaker", speaker_id="samuel-colvin")))
    render_result(result, "speaker", console)
    text = console.export_text()
    abstract_line = "For most of my career, my job was writing code."
    assert text.count(abstract_line) == 1
    assert "10:25-10:55" in text
    assert "Software Development as Constrained Optimization" in text
    assert "https://github.com/samuelcolvin" in text


def test_talk_card_shows_full_title_in_body():
    import asyncio

    console = make_console(record=True, width=72)
    service = Service(Settings.from_env())
    result = asyncio.run(
        service.execute(Request(operation="talk", speaker_id="tobie-morgan-hitchcock"))
    )
    render_result(result, "talk", console)
    text = console.export_text()
    full = "Memory Is Not a Bigger Context Window: Memory Engineering for Production Agents"
    # Rich wraps long lines; compare on whitespace-collapsed text.
    collapsed = " ".join(text.split())
    assert full in collapsed
    # Short panel header "Talk"; long title wraps in the body instead of truncating.
    assert "Talk" in text.splitlines()[0]
    assert "Production Ag" not in text.splitlines()[0]


def test_footer_deduplicates_source_urls():
    import asyncio

    console = make_console(record=True, width=88)
    service = Service(Settings.from_env())
    result = asyncio.run(
        service.execute(Request(operation="talks", event_id="agenteng-london-2026"))
    )
    assert len(result.sources) > 1
    assert len({str(s.url) for s in result.sources}) == 1
    # JSON/result still carries every source row.
    assert len(result.sources) == len(result.data)
    render_result(result, "talks", console)
    text = console.export_text()
    assert text.count("Source:") == 1
    assert "https://agentengineering.world/agenda" in text
