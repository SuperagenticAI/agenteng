<p align="center">
  <img src="https://raw.githubusercontent.com/SuperagenticAI/agenteng/main/docs/assets/logo.png" alt="Agent Engineering HQ" width="128" height="128">
</p>

<h1 align="center">AgentEng</h1>

<p align="center">
  <strong>Conference CLI and agent tool for Agent Engineering</strong><br>
  London and San Francisco conferences, meetups and events
</p>

<p align="center">
  <a href="https://pypi.org/project/agenteng/"><img src="https://img.shields.io/pypi/v/agenteng.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/agenteng/"><img src="https://img.shields.io/pypi/pyversions/agenteng.svg" alt="Python versions"></a>
  <a href="https://github.com/SuperagenticAI/agenteng/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SuperagenticAI/agenteng/ci.yml?branch=main&label=CI" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/agenteng.svg" alt="License"></a>
  <a href="https://docs.agentengineering.world"><img src="https://img.shields.io/badge/docs-docs.agentengineering.world-0A7EA4" alt="Docs"></a>
</p>

<p align="center">
  <a href="https://agentengineering.world">Website</a>
  ·
  <a href="https://docs.agentengineering.world">Docs</a>
  ·
  <a href="https://a2a.agentengineering.world">A2A host</a>
  ·
  <a href="https://a2a.agentengineering.world/mcp/">MCP</a>
  ·
  <a href="https://pypi.org/project/agenteng/">PyPI</a>
  ·
  <a href="https://github.com/SuperagenticAI/agenteng">Source</a>
</p>

## What it is

**AgentEng** is the offline-capable Python CLI, MCP server and A2A agent for the [Agent Engineering](https://agentengineering.world) conference, meetups and events in **London** and **San Francisco**.

Use it from a terminal or from a coding agent to browse events, speakers, agendas, tickets, FAQ and the tool directory. Default requests use the bundled catalogue with **no server-side model calls**.

| Surface | Where |
| --- | --- |
| Website | [agentengineering.world](https://agentengineering.world) |
| Docs | [docs.agentengineering.world](https://docs.agentengineering.world) |
| A2A agent | [a2a.agentengineering.world](https://a2a.agentengineering.world) |
| MCP (remote) | [a2a.agentengineering.world/mcp/](https://a2a.agentengineering.world/mcp/) |
| PyPI | [pypi.org/project/agenteng](https://pypi.org/project/agenteng/) |

The catalogue is a snapshot. It does not verify live ticket availability. See [data and attribution](docs/DATA.md).

## Install

```sh
# One-liner (CLI + MCP + A2A extras)
curl -fsSL https://agentengineering.world/install.sh | sh

# Or with uv / pip
uv tool install --upgrade 'agenteng[server]'
pip install -U 'agenteng[server]'
```

Pin a version with `AGENTENG_VERSION=0.0.7`. The installer bootstraps [uv](https://docs.astral.sh/uv/) when needed and never uses sudo.

`ae` is a short alias for `agenteng` (handy for developers). Commands on the website and in docs always use `agenteng`.

## Quickstart

```sh
agenteng                         # interactive menu (TTY)
agenteng discover                # London / SF overview
agenteng events --upcoming
agenteng talks
agenteng speakers --city London
agenteng agenda agenteng-london-2026
agenteng tickets agenteng-london-2026
agenteng --json events           # shared Result JSON for agents and pipes
```

On a terminal, commands print cards and tables. Agents should use `--json` (before the command), set `AGENTENG_OUTPUT=json`, or pipe stdout. Non-TTY stdout always returns the shared Result JSON.

Put global flags before the command: `agenteng --json events --city London`.

## For agents

### MCP (local)

```json
{
  "mcpServers": {
    "agenteng": {
      "command": "agenteng",
      "args": ["mcp"]
    }
  }
}
```

`agenteng connect cursor` (also `claude-code`, `codex`) prints setup for that client. See [integrations](https://docs.agentengineering.world/INTEGRATIONS/).

### A2A

- Agent card: `https://a2a.agentengineering.world/.well-known/agent-card.json`
- JSON-RPC: `https://a2a.agentengineering.world/` with header `A2A-Version: 1.0`
- MCP Streamable HTTP: `https://a2a.agentengineering.world/mcp/`

### JSON output

```sh
agenteng --json discover
agenteng --json talks
AGENTENG_OUTPUT=json agenteng events --upcoming
```

The same typed request works from CLI, MCP, A2A and HTTP (`/v1/query`). Full operation list: [architecture](docs/ARCHITECTURE.md).

## Event day

```sh
agenteng live                    # full-screen now/next board (Ctrl-C exits)
agenteng live --at 10:40         # preview the board at a given time
agenteng bingo --seed 7          # talk bingo; same seed, same card
agenteng bingo --format html --output bingo.html
agenteng about                   # what Agent Engineering is
agenteng hq                      # manifesto, mindset, reading
agenteng agenda agenteng-london-2026
agenteng talks
agenteng speakers --city London
```

Piped or with `--json`, `agenteng live` prints one Result JSON snapshot (`agenteng --json live --once`). Website command wording is tracked in [docs/SITE-SYNC.md](docs/SITE-SYNC.md).

## Experimental: drive a coding agent (`agenteng code`)

`agenteng code` launches an [ACP](https://agentclientprotocol.com) coding agent you already use, attaches the AgentEng MCP server and streams its work. Every permission is asked in your terminal. Options and output may change between releases.

```sh
uv tool install 'agenteng[acp]'
agenteng code --list
agenteng code --agent claude "summarise talk agenteng-london-2026-14"
```

Details: [ACP design note](docs/ACP.md) and [docs](https://docs.agentengineering.world/ACP/).

## Privacy

- **No personal data** about users, and none is collected.
- **No telemetry.** The CLI stays offline unless you pass `--remote URL`.
- **Local files stay local.** Bookmarks and `agenteng code` logs live under your config directory and are never uploaded.
- The public host keeps no conversations or request bodies.

Full policy: [Privacy in DATA.md](docs/DATA.md#privacy).

## Docs

| Topic | Link |
| --- | --- |
| Start here | [docs.agentengineering.world](https://docs.agentengineering.world) |
| Coding-agent integrations | [INTEGRATIONS](https://docs.agentengineering.world/INTEGRATIONS/) |
| Tool directory | [TOOLS](https://docs.agentengineering.world/TOOLS/) |
| ACP client | [ACP](https://docs.agentengineering.world/ACP/) |
| Participation drafts | [PARTICIPATION](https://docs.agentengineering.world/PARTICIPATION/) |
| Data and privacy | [DATA](https://docs.agentengineering.world/DATA/) |
| Architecture | [ARCHITECTURE](docs/ARCHITECTURE.md) |
| Releases | [RELEASING](docs/RELEASING.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## Contributing

Code, docs and source-backed data improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md) and [SECURITY.md](SECURITY.md).

```sh
git clone https://github.com/SuperagenticAI/agenteng.git
cd agenteng
uv sync --frozen --all-extras
uv run --frozen pytest -q
uv run --frozen ruff check src tests scripts
```

## License

Source code and original documentation are licensed under [Apache-2.0](LICENSE). Third-party event and speaker material retains its own rights; see [NOTICE](NOTICE) and [DATA.md](docs/DATA.md).
