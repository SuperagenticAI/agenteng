![Agent Engineering HQ](assets/logo.png){ .agenteng-logo }

# AgentEng

Find Agent Engineering HQ conferences and events in **London and San Francisco**
from your terminal or coding agent. AgentEng provides a CLI, one MCP tool and an
A2A agent using the same public catalogue. Event lookup, tool browsing and local
proposal drafts work offline, with no model calls or API key.

## Install from source

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/SuperagenticAI/agenteng.git
cd agenteng
uv tool install '.[mcp]'
agenteng --help
```

The Python package and executable are both named `agenteng`. This is a **0.1.0
alpha**; registry/website installation and official hosted endpoints will be
announced after verified publication.

## Explore

```sh
agenteng discover
agenteng events --city London --upcoming
agenteng events --city 'San Francisco'
agenteng ask 'When is the next London conference?'
agenteng disciplines
agenteng tools --discipline memory
agenteng tool langgraph
agenteng --json events
```

Event results include source links and snapshot freshness. Follow the official
registration page for current details. The [tool directory](TOOLS.md) lists
attributed tools across twelve disciplines without popularity rankings.

## Connect your agent

For clients supporting local MCP, add the installed executable to their MCP
configuration:

```json
{"mcpServers":{"agenteng":{"command":"agenteng","args":["mcp"]}}}
```

Run `agenteng connect codex`, `agenteng connect claude-code` or
`agenteng connect cursor` for client-specific instructions. See
[MCP, A2A and HTTP connections](INTEGRATIONS.md) for remote configuration and
typed request examples. Installing the CLI does not start or publish a server.

## Share an idea

```sh
agenteng engage --city London --output draft.json
agenteng proposal preview draft.json
agenteng proposal export draft.json --format markdown --output draft.md
agenteng participate
```

These commands prepare a local idea and show organizer contact details; they do
not send it. See [participation](PARTICIPATION.md) for the optional private intake
pilot. Receipt of an idea does not guarantee a response, acceptance or an event.
London 2026 has an invited programme and no public CFP.

Optional model synthesis and RLM are disabled by default. RLM permits maximum
depth one and one child or leaf delegation. See [architecture](ARCHITECTURE.md).

Visit the [event website](https://agentengineering.world), report a
[software issue](https://github.com/SuperagenticAI/agenteng/issues), or read the
[contribution guide](https://github.com/SuperagenticAI/agenteng/blob/main/CONTRIBUTING.md).
