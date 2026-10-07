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


@pytest.fixture(autouse=True)
def isolated_agent_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTENG_CONFIG_DIR", str(tmp_path / "agenteng-config"))


def run_ae(*args, env=None, stdin=subprocess.DEVNULL, input=None, timeout=60):
    merged = {**os.environ, "AGENTENG_OUTPUT": "", **(env or {})}
    io = {"input": input} if input is not None else {"stdin": stdin}
    return subprocess.run(
        [sys.executable, "-m", "agenteng", *args],
        capture_output=True,
        text=True,
        env=merged,
        timeout=timeout,
        cwd=ROOT,
        **io,
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


# --------------------------------------------------------------------------- chat


@needs_acp
def test_chat_reads_one_turn_per_stdin_line(tmp_path):
    record = tmp_path / "record.json"
    lines = "\n".join(
        [
            "explain talk agenteng-london-2026-14",
            "/help",
            "/agent",
            "/context agenteng-london-2026-2",
            "now patch the app",
            "/bogus",
            "/exit",
            "never sent",
        ]
    )
    result = run_ae(
        "code",
        "--chat",
        "--json",
        "--no-mcp",
        "--agent-command",
        FAKE_COMMAND,
        input=lines + "\n",
        env={"FAKE_ACP_RECORD": str(record)},
    )
    assert result.returncode == 0, result.stderr + result.stdout
    stream = events(result.stdout)
    assert [e["event"] for e in stream].count("session") == 1
    assert [e["stop_reason"] for e in stream if e["event"] == "stop"] == ["end_turn", "end_turn"]
    infos = " ".join(e["message"] for e in stream if e["event"] == "info")
    assert "/context" in infos and "Fake ACP agent" in infos and "turns 1" in infos
    assert "Attached talk agenteng-london-2026-2" in infos
    warnings = " ".join(e["message"] for e in stream if e["event"] == "warning")
    assert "Unknown command /bogus" in warnings
    text = "".join(e["text"] for e in stream if e["event"] == "agent_message_chunk")
    assert "Using context: agenteng-london-2026-2" in text
    assert "Turn 2: now patch the app" in text and "never sent" not in text

    sent = json.loads(record.read_text())
    assert sent["turns"] == 2
    first, second = sent["prompts"]
    assert first[-1] == "explain talk agenteng-london-2026-14"
    assert "agenteng-london-2026-14" in first[1]
    # Later turns carry only new context plus the message, not the preamble again.
    assert second[-1] == "now patch the app"
    assert len(second) == 2 and "agenteng-london-2026-2" in second[0]


@needs_acp
def test_json_without_chat_stays_single_shot(tmp_path):
    record = tmp_path / "record.json"
    result = run_ae(
        "code",
        "--json",
        "--no-mcp",
        "--agent-command",
        FAKE_COMMAND,
        input="first line\nsecond line\n",
        env={"FAKE_ACP_RECORD": str(record)},
    )
    assert result.returncode == 0, result.stderr
    sent = json.loads(record.read_text())
    assert sent["turns"] == 1
    assert sent["prompt"][-1] == "first line\nsecond line"


def scripted_reader(lines):
    queue = list(lines)

    async def read():
        return queue.pop(0) if queue else None

    return read


def chat_session(sink, prompter=None, env=None):
    from agenteng import acp_client

    os.environ.update(env or {})
    return acp_client.AgentSession(
        [sys.executable, str(FAKE)], cwd=str(ROOT), sink=sink, prompter=prompter
    )


@needs_acp
def test_run_chat_in_process_keeps_one_session(tmp_path, monkeypatch):
    from agenteng import acp_client
    from agenteng.output import make_console

    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_ACP_RECORD", str(record))
    console = make_console(record=True, width=100)
    sink = acp_client.RichSink(console=console)

    async def go():
        async with chat_session(sink, prompter=lambda tool, options: options[0]) as session:
            last = await acp_client.run_chat(
                session,
                scripted_reader(["second turn", "patch it"]),
                mcp_attached=False,
                first_prompt="hello",
                handle_sigint=False,
            )
            return last, session.turns

    last, turns = asyncio.run(go())
    assert (last, turns) == ("end_turn", 3)
    text = console.export_text()
    assert "Wrote the demo." in text and "Turn 2: second turn" in text
    assert "Turn 3: patch it" in text
    assert json.loads(record.read_text())["turns"] == 3


@needs_acp
def test_cancel_sends_session_cancel(tmp_path, monkeypatch):
    from agenteng import acp_client

    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_ACP_RECORD", str(record))
    monkeypatch.setenv("FAKE_ACP_MODE", "slow")
    sink = acp_client.JsonSink()

    async def go():
        async with chat_session(sink) as session:
            turn = asyncio.ensure_future(session.turn([acp_client.acp.text_block("go")]))
            await asyncio.sleep(0.5)
            await session.cancel()
            return await asyncio.wait_for(turn, 10)

    assert asyncio.run(go()) == "cancelled"
    assert json.loads(record.read_text())["cancelled"] == "fake-session-1"


@needs_acp
def test_ctrl_c_at_permission_prompt_cancels_turn(tmp_path, monkeypatch):
    from agenteng import acp_client

    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_ACP_RECORD", str(record))

    async def prompter(tool_call, options):
        raise acp_client.PermissionCancelled()

    sink = acp_client.JsonSink()

    async def go():
        async with chat_session(sink, prompter=prompter) as session:
            stop = await session.turn([acp_client.acp.text_block("go")])
            return stop, session.client.permissions

    stop, permissions = asyncio.run(go())
    assert stop == "cancelled"
    assert permissions[0]["decision"] == "cancelled"
    sent = json.loads(record.read_text())
    assert sent["permission_outcome"] == "cancelled" and sent["cancelled"] == "fake-session-1"


# --------------------------------------------------------------------------- diffs


def test_diff_render_colours_and_truncates():
    from agenteng.acp_client import FileDiff, diff_renderable

    diff = FileDiff("app.py", "a\nb\n", "a\nc\n" + "".join(f"x{i}\n" for i in range(60)))
    assert diff.stats() == (61, 1)
    assert diff.summary() == {"path": "app.py", "added": 61, "removed": 1, "new_file": False}
    body, hidden = diff_renderable(diff, max_lines=10)
    plain = body.plain
    assert "app.py  +61 -1" in plain and "-b" in plain and "+c" in plain
    assert hidden > 0 and f"... {hidden} more diff lines" in plain
    styles = {str(span.style) for span in body.spans}
    assert any("green" in s for s in styles) and any("red" in s for s in styles)
    full, hidden = diff_renderable(diff, max_lines=None)
    assert hidden == 0 and "+x59" in full.plain
    new_file, _ = diff_renderable(FileDiff("new.txt", None, "hi\n"))
    assert "--- /dev/null" in new_file.plain or "+1 -0" in new_file.plain


@needs_acp
def test_permission_prompt_shows_diff_and_full_view(monkeypatch):
    from agenteng import acp_client
    from agenteng.output import make_console

    console = make_console(record=True, width=100)
    sink = acp_client.RichSink(console=console)
    answers = iter(["d", "9", "1"])
    monkeypatch.setattr("click.prompt", lambda *a, **k: next(answers))
    prompter = acp_client.terminal_prompter(console, sink=sink)
    outcome, _ = fake_session_with(
        sink, prompter, env={"FAKE_ACP_DIFF_LINES": str(acp_client.DIFF_PREVIEW_LINES + 20)}
    )
    assert outcome.stop_reason == "end_turn"
    assert outcome.permissions[0]["decision"] == "allow_once"
    assert outcome.permissions[0]["diffs"][0]["path"] == "demo/README.md"
    text = console.export_text()
    assert "Permission requested" in text and "View the full diff" in text
    assert "more diff lines" in text
    last = acp_client.DIFF_PREVIEW_LINES + 19
    assert f"+line {last}" in text  # only in the full view
    assert "Pick 1-2 or d." in text
    # Held for the prompt, so the diff is not printed twice.
    assert text.count("@@ -1,2") == 2  # preview + full view


def fake_session_with(sink, prompter, env=None):
    from agenteng import acp_client

    old = dict(os.environ)
    os.environ.update(env or {})
    try:
        return asyncio.run(
            acp_client.run_session(
                [sys.executable, str(FAKE)],
                acp_client.build_prompt("hi", [], mcp_attached=False),
                cwd=str(ROOT),
                sink=sink,
                prompter=prompter,
            )
        ), None
    finally:
        os.environ.clear()
        os.environ.update(old)


@needs_acp
def test_streamed_tool_call_diff_is_rendered(monkeypatch):
    from agenteng import acp_client
    from agenteng.output import make_console

    console = make_console(record=True, width=100)
    sink = acp_client.RichSink(console=console)

    async def go():
        async with chat_session(sink, prompter=lambda tool, options: options[-1]) as session:
            return await acp_client.run_chat(
                session,
                scripted_reader(["patch the app"]),
                mcp_attached=False,
                first_prompt="hello",
                handle_sigint=False,
            )

    assert asyncio.run(go()) == "end_turn"
    text = console.export_text()
    assert "demo/app.py  +3 -1" in text
    assert '-print("hello")' in text and "+from memory import recall" in text
    assert text.count("demo/app.py  +3 -1") == 1


@needs_acp
def test_json_stream_includes_diff_content_and_summary():
    result = run_ae("code", "--json", "--no-mcp", "--agent-command", FAKE_COMMAND, "hi")
    assert result.returncode == 0, result.stderr
    stream = events(result.stdout)
    start = next(
        e for e in stream if e["event"] == "tool_call" and e["tool_call"]["kind"] == "edit"
    )
    (content,) = start["tool_call"]["content"]
    assert content["type"] == "diff" and content["path"] == "demo/README.md"
    assert content["oldText"].startswith("# Demo")
    permission = next(e for e in stream if e["event"] == "permission")
    assert permission["diffs"] == [
        {"path": "demo/README.md", "added": 6, "removed": 1, "new_file": False}
    ]


# --------------------------------------------------------------------------- menu


def test_menu_entry_picks_agent_and_talk(monkeypatch):
    from agenteng import cli, interactive

    spec = find_agent("claude")
    monkeypatch.setattr("agenteng.acp_agents.installed_agents", lambda: [spec])
    monkeypatch.setattr(spec.__class__, "argv", lambda self, npx=False: ["/bin/fake-acp"])
    answers = iter([spec, "talk"])
    asked = []

    def fake_select(message, choices, **kwargs):
        asked.append((message, [getattr(c, "title", c) for c in choices]))
        return next(answers)

    monkeypatch.setattr(interactive, "_select", fake_select)
    monkeypatch.setattr(interactive, "pick_talk_id", lambda ctx: "agenteng-london-2026-14")
    calls = []
    monkeypatch.setattr(cli, "run_code", lambda *a, **k: calls.append((a, k)))
    interactive._code_with_agent(object())
    assert asked[0][0] == "Code with which agent?"
    assert "Claude Code (ACP adapter) (claude-agent-acp)" in asked[0][1]
    ((args, kwargs),) = calls
    assert args[1:] == (["/bin/fake-acp"], "")
    assert kwargs == {"chat": True, "context_ids": ["agenteng-london-2026-14"]}


def test_menu_entry_without_agents_shows_install_hints(monkeypatch, capsys):
    from agenteng import cli, interactive

    monkeypatch.setattr("agenteng.acp_agents.installed_agents", lambda: [])
    monkeypatch.setattr(cli, "run_code", lambda *a, **k: pytest.fail("should not run"))
    monkeypatch.setattr("agenteng.render.make_console", _wide_console)
    interactive._code_with_agent(object())
    out = capsys.readouterr()
    assert "npm install -g @agentclientprotocol/claude-agent-acp" in out.out
    assert "No ACP coding agent is on PATH yet" in out.err


def _wide_console(*args, **kwargs):
    from rich.console import Console

    from agenteng.output import THEME

    return Console(theme=THEME, width=200, force_terminal=False)


def test_menu_lists_code_with_an_agent(monkeypatch):
    from agenteng import interactive

    seen = []

    def fake_select(message, choices, **kwargs):
        seen.append([getattr(c, "title", c) for c in choices])
        return "quit"

    monkeypatch.setattr(interactive, "_select", fake_select)
    monkeypatch.setattr(interactive, "stdin_is_tty", lambda: True, raising=False)
    interactive.run_menu(_menu_ctx())
    assert "Code with an agent (ACP, experimental)" in seen[0]


def _menu_ctx():
    import click

    return click.Context(
        click.Command("ae"), obj={"remote": None, "catalogue": None, "as_json": False}
    )


def test_menu_talk_picker_skips_events_without_talks(monkeypatch):
    from agenteng import interactive

    events_picked = iter(["london-building-reliable-ai-agents-from-context-to-evals", None])
    monkeypatch.setattr(interactive, "pick_event_id", lambda ctx, prompt="": next(events_picked))
    assert interactive.pick_talk_id(_menu_ctx()) is None

    events_picked = iter(["agenteng-london-2026"])
    monkeypatch.setattr(interactive, "pick_event_id", lambda ctx, prompt="": next(events_picked))
    titles = []

    def fake_select(message, choices, **kwargs):
        titles.extend(c.title for c in choices)
        return choices[0].value

    monkeypatch.setattr(interactive, "_select", fake_select)
    assert interactive.pick_talk_id(_menu_ctx()).startswith("agenteng-london-2026-")
    assert titles[-1] == "Back"


@needs_acp
def test_rejected_edit_does_not_print_its_held_diff():
    outcome, console = fake_session(lambda tool_call, options: None)
    assert outcome.permissions[0]["decision"] == "rejected"
    text = console.export_text()
    assert "Write demo/README.md failed" in text
    assert "@@" not in text
