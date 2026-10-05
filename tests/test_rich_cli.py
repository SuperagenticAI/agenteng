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
    assert "—" not in display_text("AgentEng — Conference")
    assert " - " in display_text("AgentEng — Conference")


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
    # Main menu -> events -> pick london -> overview -> back -> quit
    picks = iter(
        [
            "events",
            "agenteng-london-2026",
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
    assert "AgentEng London 2026" in result.output
    assert "Bye" in result.output
