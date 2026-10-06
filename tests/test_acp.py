"""ae code: ACP client spike, exercised against an in-repo fake ACP agent."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from importlib.util import find_spec

import pytest

from agenteng.acp_agents import AGENTS, find_agent

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests/fixtures/fake_acp_agent.py"
FAKE_COMMAND = f"{sys.executable} {FAKE}"


def run_ae(*args, env=None, stdin=subprocess.DEVNULL, timeout=60):
    merged = {**os.environ, "AGENTENG_OUTPUT": "", **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "agenteng", *args],
        capture_output=True,
        text=True,
        env=merged,
        stdin=stdin,
        timeout=timeout,
        cwd=ROOT,
    )


def events(stdout: str) -> list[dict]:
    return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def test_list_reports_registry_launch_commands():
    result = run_ae("code", "--list", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    commands = {row["name"]: row["command"] for row in data["agents"]}
    assert commands["claude"] == "claude-agent-acp"
    assert commands["codex"] == "codex-acp"
    assert commands["gemini"] == "gemini --acp"
    assert data["registry"].startswith("https://cdn.agentclientprotocol.com/")
    assert all(isinstance(row["installed"], bool) for row in data["agents"])


def test_list_renders_table_for_humans():
    from agenteng.output import make_console
    from agenteng.render import render_acp_agents

    console = make_console(record=True, width=120)
    render_acp_agents([spec.as_dict() for spec in AGENTS], "https://example.test", console)
    text = console.export_text()
    assert "ACP coding agents" in text
    assert "claude-agent-acp" in text and "gemini --acp" in text


def test_find_agent_aliases_and_unknown():
    assert find_agent("Claude-Code").name == "claude"
    assert find_agent("gemini-cli").name == "gemini"
    with pytest.raises(LookupError, match="Known agents"):
        find_agent("nope")


def test_missing_agent_explains_install(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(LookupError, match="npm install -g @agentclientprotocol/codex-acp"):
        find_agent("codex").argv()


needs_acp = pytest.mark.skipif(find_spec("acp") is None, reason="install agenteng[acp]")


@needs_acp
def test_session_attaches_mcp_and_rejects_without_terminal(tmp_path):
    pytest.importorskip("mcp")
    record = tmp_path / "record.json"
    result = run_ae(
        "code",
        "--json",
        "--agent-command",
        FAKE_COMMAND,
        "scaffold a demo of talk agenteng-london-2026-14",
        env={"FAKE_ACP_RECORD": str(record), "FAKE_ACP_USE_MCP": "1"},
    )
    assert result.returncode == 0, result.stderr + result.stdout
    stream = events(result.stdout)
    names = [e["event"] for e in stream]
    assert names[0] == "agent" and names[-1] == "stop"
    assert {"plan", "agent_message_chunk", "tool_call", "tool_call_update", "permission"} <= set(
        names
    )
    session = next(e for e in stream if e["event"] == "session")
    assert session["mcp_servers"] == ["agenteng"]
    assert session["context"] == ["talk:agenteng-london-2026-14"]
    permission = next(e for e in stream if e["event"] == "permission")
    assert permission["decision"] == "rejected (non-interactive)"
    text = "".join(e["text"] for e in stream if e["event"] == "agent_message_chunk")
    assert "Memory Is Not a Bigger Context Window" in text
    assert "Skipped the write." in text

    sent = json.loads(record.read_text())
    assert sent["protocol_version"] == 1
    assert sent["client_info"]["name"] == "agenteng"
    assert sent["client_capabilities"]["fs"]["writeTextFile"] is False
    assert sent["client_capabilities"]["terminal"] is False
    (server,) = sent["mcp_servers"]
    assert server["name"] == "agenteng"
    assert Path(server["command"]).is_absolute()
    assert server["args"] == ["-m", "agenteng", "mcp"]
    assert sent["mcp_tools"] == ["agenteng"] and sent["mcp_status"] == "ok"
    assert sent["permission_option"] == "reject"
    assert "agenteng-london-2026-14" in sent["prompt"][1]
    assert sent["prompt"][-1] == "scaffold a demo of talk agenteng-london-2026-14"


@needs_acp
def test_no_mcp_flag_sends_no_servers(tmp_path):
    record = tmp_path / "record.json"
    result = run_ae(
        "code",
        "--json",
        "--no-mcp",
        "--agent-command",
        FAKE_COMMAND,
        "hello",
        env={"FAKE_ACP_RECORD": str(record)},
    )
    assert result.returncode == 0, result.stderr
    sent = json.loads(record.read_text())
    assert sent["mcp_servers"] == []
    assert "MCP server named `agenteng`" not in sent["prompt"][0]


def fake_session(prompter, *, allow_always=False, env=None):
    from agenteng import acp_client
    from agenteng.output import make_console

    console = make_console(record=True, width=100)
    sink = acp_client.RichSink(console=console)
    old = dict(os.environ)
    os.environ.update(env or {})
    try:
        outcome = asyncio.run(
            acp_client.run_session(
                [sys.executable, str(FAKE)],
                acp_client.build_prompt("hi", [], mcp_attached=False),
                cwd=str(ROOT),
                sink=sink,
                prompter=prompter,
                allow_always=allow_always,
            )
        )
    finally:
        os.environ.clear()
        os.environ.update(old)
    return outcome, console


@needs_acp
def test_user_can_allow_once_and_allow_always_is_hidden(tmp_path):
    seen = []

    def prompter(tool_call, options):
        seen.append([o.kind for o in options])
        return next(o for o in options if o.kind == "allow_once")

    record = tmp_path / "record.json"
    outcome, console = fake_session(prompter, env={"FAKE_ACP_RECORD": str(record)})
    assert outcome.stop_reason == "end_turn"
    assert seen == [["allow_once", "reject_once"]]
    assert json.loads(record.read_text())["permission_option"] == "allow"
    text = console.export_text()
    assert "Fake ACP agent" in text
    assert "permission allow_once" in text
    assert "Wrote the demo." in text and "end_turn" in text


@needs_acp
def test_allow_always_shown_only_when_requested():
    seen = []

    def prompter(tool_call, options):
        seen.append([o.kind for o in options])
        return None

    outcome, _ = fake_session(prompter, allow_always=True)
    assert seen == [["allow_once", "allow_always", "reject_once"]]
    assert outcome.permissions[0]["decision"] == "rejected"


@needs_acp
def test_sign_in_required_is_reported():
    from agenteng.acp_client import AgentError

    with pytest.raises(AgentError, match="sign in"):
        fake_session(None, env={"FAKE_ACP_MODE": "auth"})


@needs_acp
def test_reject_without_reject_option_is_cancelled():
    from acp import schema

    from agenteng.acp_client import reject_response

    allow = schema.PermissionOption(option_id="a", name="Allow", kind="allow_once")
    assert reject_response([allow]).outcome.outcome == "cancelled"


@needs_acp
def test_missing_agent_binary_fails_cleanly(tmp_path):
    result = run_ae("code", "--agent", "kimi", "hi", env={"PATH": str(tmp_path)})
    assert result.returncode == 1
    assert "not on PATH" in result.stderr


@pytest.mark.parametrize("ident", ["agenteng-london-2026-14", "agenteng-london-2026-2"])
def test_talk_exact_session_id_wins_over_search(ident):
    result = run_ae("--json", "talk", ident)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["data"]["id"] == ident
