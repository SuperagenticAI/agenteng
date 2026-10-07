"""Connection walkthroughs produce usable protocol instructions without side effects."""

import json
import shlex

import pytest
from click.testing import CliRunner

from agenteng.cli import main


def test_a2a_instructions_include_complete_public_discovery_and_message():
    output = CliRunner().invoke(main, ["connect", "a2a", "--url", "https://example.org"])
    assert output.exit_code == 0
    commands = [
        shlex.split(line) for line in output.output.splitlines() if line.startswith("curl ")
    ]
    assert len(commands) == 2
    assert commands[0][-1] == "https://example.org/.well-known/agent-card.json"
    message = commands[1]
    assert "https://example.org/" in message and "A2A-Version: 1.0" in message
    payload = json.loads(message[message.index("--data") + 1])
    assert payload["method"] == "SendMessage"
    assert payload["params"]["message"]["parts"] == [{"data": {"operation": "discover"}}]


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_mcp_protocol_matches_generic_configuration(transport):
    runner = CliRunner()
    protocol = runner.invoke(main, ["connect", "mcp", "--transport", transport])
    generic = runner.invoke(main, ["connect", "generic", "--transport", transport])
    assert protocol.exit_code == 0
    assert json.loads(protocol.output) == json.loads(generic.output)


def test_acp_setup_does_not_start_agents_or_write_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTENG_CONFIG_DIR", str(tmp_path / "logs"))
    output = CliRunner().invoke(main, ["connect", "acp"])
    assert output.exit_code == 0
    assert "agenteng[acp]" in output.output and "agenteng code --list" in output.output
    assert "do not launch" in output.output
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("protocol", ["a2a", "mcp", "acp"])
def test_protocol_setup_rejects_credential_bearing_origins(protocol):
    output = CliRunner().invoke(
        main, ["connect", protocol, "--url", "https://user:private@example.org"]
    )
    assert output.exit_code != 0
    assert "private" not in output.output
