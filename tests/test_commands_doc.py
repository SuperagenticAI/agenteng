"""docs/COMMANDS.md lists every visible command and option; help text is complete."""

from __future__ import annotations

import json
import re
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from agenteng.cli import main

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/COMMANDS.md"
LONDON = "agenteng-london-2026"


def visible_commands(group=main, path=()):
    for name, command in group.commands.items():
        if command.hidden:
            continue
        yield path + (name,), command
        if isinstance(command, click.Group):
            yield from visible_commands(command, path + (name,))


def visible_options(command):
    return [p for p in command.params if isinstance(p, click.Option) and not p.hidden]


def test_commands_doc_lists_every_command_and_option():
    doc = DOC.read_text()
    assert "\N{EM DASH}" not in doc
    for path, command in visible_commands():
        name = " ".join(path)
        assert re.search(rf"^#+ agenteng {re.escape(name)}$", doc, re.MULTILINE), name
        for option in visible_options(command):
            assert f"`{option.opts[0]}`" in doc, (name, option.opts[0])


def test_commands_doc_examples_use_agenteng():
    doc = DOC.read_text()
    blocks = re.findall(r"```sh\n(.*?)```", doc, re.DOTALL)
    assert blocks
    for block in blocks:
        for line in block.strip().splitlines():
            assert line.startswith("agenteng"), line


def test_every_visible_option_has_help():
    missing = [
        (" ".join(path), option.opts[0])
        for path, command in visible_commands()
        for option in visible_options(command)
        if not option.help
    ]
    assert not missing


def test_user_visible_copy_says_agenteng(tmp_path):
    runner = CliRunner(env={"AGENTENG_OUTPUT": "json", "AGENTENG_CONFIG_DIR": str(tmp_path)})
    about = json.loads(runner.invoke(main, ["about", "--connect"]).output)
    commands = json.dumps(about["data"])
    assert "agenteng connect cursor" in commands
    assert '"ae ' not in commands
    help_text = runner.invoke(main, ["now", "--help"]).output
    assert "agenteng live" in help_text and "`ae " not in help_text
    failed = runner.invoke(main, ["talk", "zzqxv"])
    assert failed.exit_code == 1


# --- exit codes: empty but valid is 0, unknown IDs stay 1 --------------------------


def run_json(tmp_path, *args):
    runner = CliRunner(env={"AGENTENG_OUTPUT": "json", "AGENTENG_CONFIG_DIR": str(tmp_path)})
    result = runner.invoke(main, list(args))
    return result.exit_code, result.output


@pytest.mark.parametrize(
    "args",
    [
        ("now", LONDON, "--at", "03:00"),
        ("search", "zzqxv"),
        ("talks", "--search", "zzqxv"),
        ("speakers", "--search", "zzqxv"),
        ("agenda", LONDON, "--topic", "zzqxv"),
    ],
)
def test_empty_but_valid_results_exit_zero(tmp_path, args):
    code, output = run_json(tmp_path, *args)
    assert code == 0, output
    body = json.loads(output)
    # The JSON contract is unchanged for agents: status stays not_found.
    assert body["status"] == "not_found"
    data = body["data"]
    assert data == [] or (isinstance(data, dict) and data.get("session") is None)


@pytest.mark.parametrize(
    "args",
    [
        ("event", "no-such-event"),
        ("speaker", "no-such-speaker"),
        ("tool", "no-such-tool"),
        ("talk", "zzqxv"),
        ("now", "no-such-event"),
        ("agenda", "no-such-event"),
        ("query", '{"operation":"talks","event_id":"no-such-event"}'),
    ],
)
def test_unknown_ids_still_exit_one(tmp_path, args):
    code, output = run_json(tmp_path, *args)
    assert code == 1, output
    assert json.loads(output)["status"] == "not_found"


def test_bad_usage_exits_two(tmp_path):
    code, _ = run_json(tmp_path, "events", "--no-such-option")
    assert code == 2
