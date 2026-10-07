<p align="center">
  <a href="https://agentengineering.world">
    <img src="https://raw.githubusercontent.com/SuperagenticAI/agenteng/main/docs/assets/logo.png" alt="Agent Engineering HQ logo" width="128" height="128">
  </a>
</p>

<h1 align="center">AgentEng: Agent Engineering HQ</h1>

<p align="center">
  <strong>The home of the agent engineering discipline.</strong><br>
  Discover events, people and tools from your terminal to your coding agent.<br>
  London &amp; San Francisco · CLI · MCP · A2A
</p>

<p align="center">
  <a href="https://agentengineering.world"><img src="https://img.shields.io/badge/website-agentengineering.world-0A7EA4" alt="Website: agentengineering.world"></a>
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

<p align="center">
  <a href="#quickstart">Quickstart</a>
  ·
  <a href="#explore-the-tool-directory">Tool directory</a>
  ·
  <a href="#connect-your-agent">Connect your agent</a>
  ·
  <a href="#contributing">Contribute</a>
</p>

## Why AgentEng?

**AgentEng** brings [Agent Engineering HQ](https://agentengineering.world) to your terminal and coding agent. It is an offline-capable Python CLI, MCP server and A2A agent for conferences, meetups and events in **London** and **San Francisco**, with a directory of tools across **12 agent engineering disciplines**.

Explore the bundled catalogue with **no provider key or model calls**. Read cards and tables in your terminal, or use the same structured results through CLI JSON, MCP, A2A and HTTP.

| What you can do | How AgentEng helps |
| --- | --- |
| **Find your next event** | Browse events, speakers, talks, agendas and official ticket links. |
| **Explore the discipline** | Search tools, models and infrastructure across 12 disciplines, with source attribution. |
| **Bring your coding agent** | Connect Codex, Claude Code or Cursor through MCP; use A2A or HTTP for other clients. |
| **Make the most of event day** | Browse the public agenda, follow the live now/next board and play talk bingo. |

The catalogue is a snapshot. Follow official event and registration links for current details and ticket availability. See [data and attribution](docs/DATA.md).

## Quickstart

### 1. Install

AgentEng requires **Python 3.12+**. The installer includes the CLI, MCP and A2A extras, bootstraps [uv](https://docs.astral.sh/uv/) when needed and never uses sudo.

```sh
curl -fsSL https://agentengineering.world/install.sh | sh
```

Prefer a package manager? Choose either:

```sh
# uv
uv tool install --upgrade 'agenteng[server]'

# pip
pip install -U 'agenteng[server]'
```

To pin the installer to a release, pass the version to `sh`:

```sh
curl -fsSL https://agentengineering.world/install.sh | AGENTENG_VERSION=0.0.7 sh
```

### 2. Discover an event

```sh
agenteng                            # interactive menu (TTY)
agenteng discover                   # London / San Francisco overview
agenteng events --upcoming
agenteng event agenteng-london-2026
agenteng speakers --city London
agenteng agenda agenteng-london-2026
agenteng tickets agenteng-london-2026
```

Use the IDs returned by `agenteng events` to explore other published events. Run `agenteng --help` or `agenteng COMMAND --help` for options. The short alias `ae` also works: `ae talks` is equivalent to `agenteng talks`.

### 3. Get structured results

```sh
agenteng --json discover
agenteng --json talks
AGENTENG_OUTPUT=json agenteng events --upcoming
```

Place `--json` **before** the subcommand. Non-TTY stdout also returns the shared Result JSON automatically, so commands work naturally in pipes and agent workflows.

Full commands, flags and exit codes: [CLI reference](docs/COMMANDS.md).

## Explore the tool directory

Browse tools, models and infrastructure by discipline, kind or search term. Listings include source links and work offline.

```sh
agenteng disciplines
agenteng tools --discipline memory
agenteng tools --discipline inference --kind runtime
agenteng tools --search 'Gemini CLI'
agenteng tool langgraph
agenteng --json tools --discipline code --limit 25
```

**The 12 disciplines:** Prompt · Context · Harness · Eval · Memory · Inference · Loop · Agentic · Code · Protocol · Graph · Search.

See the [tool directory guide](docs/TOOLS.md) for filters, pagination and attribution.

## Connect your agent

Give your coding agent access to events and tools. Try asking: **“Find the next London conference”** or **“List memory tools.”**

### MCP (local)

After installing `agenteng[server]`, add this to your client's MCP configuration:

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

For client-specific setup:

```sh
agenteng connect codex
agenteng connect claude-code
agenteng connect cursor
```

See the [integration guide](docs/INTEGRATIONS.md) for local and hosted connections.

### Hosted MCP, A2A and HTTP

Base URL: **[a2a.agentengineering.world](https://a2a.agentengineering.world)**. Use the hosted service to connect without a local MCP process.

| Interface | Route |
| --- | --- |
| MCP Streamable HTTP | `/mcp/` |
| A2A 1.0 discovery | `/.well-known/agent-card.json` |
| A2A JSON-RPC | `/` with `A2A-Version: 1.0` |
| Typed HTTP query | `/v1/query` |

The same typed request works as an A2A JSON data part or an HTTP body. Request shapes and architecture: [ARCHITECTURE.md](docs/ARCHITECTURE.md).

<details>
<summary><strong>Additional HTTP endpoints</strong></summary>

| Interface | Route |
| --- | --- |
| Catalogue / health | `/catalogue.json`, `/health` |
| OpenAPI / Swagger / ReDoc | `/openapi.json`, `/docs`, `/redoc` |
| Crawlable discovery | `/`, `/events/EVENT_ID`, `/events.json`, `/tools`, `/tools/TOOL_ID` |
| Full tool directory feed | `/tools.json` |
| Crawler / agent guides | `/llms.txt`, `/robots.txt`, `/sitemap.xml` |

</details>

<details>
<summary><strong>Public operations across CLI, MCP, A2A and HTTP</strong></summary>

Public operations (CLI, MCP, A2A, HTTP) include: `disciplines`, `tools`, `tool`, `discover`, `events`, `event`, `agenda`, `speakers`, `speaker`, `talks`, `talk`, `faq`, `venue`, `sponsors`, `conduct`, `themes`, `now`, `next`, `live`, `bingo`, `about`, `hq`, `tickets`, `recordings`, `search`, `ask` and `participate`.

Begin with `discover` for featured London/San Francisco events, or `events` for published IDs. Full command and flag reference: [docs/COMMANDS.md](docs/COMMANDS.md).

</details>

## Event day

```sh
agenteng live                    # full-screen now/next board (Ctrl-C exits)
agenteng live --at 10:40          # preview the board at a given time
agenteng bingo --seed 7           # talk bingo; same seed, same card
agenteng bingo --format html --output bingo.html
agenteng about                   # what Agent Engineering is
agenteng hq                      # manifesto, mindset, reading
agenteng unsave SESSION_ID
agenteng recordings
```

Piped or with `--json` before the subcommand, `agenteng live` prints one Result JSON snapshot (`agenteng --json live --once`). Website command wording is tracked in [docs/SITE-SYNC.md](docs/SITE-SYNC.md).

## Experimental: drive a coding agent (`agenteng code`)

`agenteng code` launches an [ACP](https://agentclientprotocol.com) coding agent you already use, attaches the AgentEng MCP server and streams its work. Every permission is asked in your terminal. Options and output may change between releases.

```sh
uv tool install 'agenteng[acp]'
agenteng code --list
agenteng code --agent claude "summarise talk agenteng-london-2026-14"
```

Details: [ACP design note](docs/ACP.md) and [docs](https://docs.agentengineering.world/ACP/).

## Privacy

- **No telemetry.** Catalogue lookups run offline by default; `--remote URL` sends requests to your chosen host.
- **Local storage.** Optional `agenteng code` logs stay in your config directory. Public operations create no attendee records or personal agendas.
- **Your chosen coding agent.** `agenteng code` sends prompts to the coding agent you launch and its provider.
- **No stored conversations.** The public AgentEng application keeps no conversations or request bodies; the hosting platform maintains standard request logs.

Full policy: [Privacy in DATA.md](docs/DATA.md#privacy).

## Documentation

| Topic | Link |
| --- | --- |
| Start here | [docs.agentengineering.world](https://docs.agentengineering.world) |
| CLI command reference | [COMMANDS.md](docs/COMMANDS.md) |
| Coding-agent integrations | [INTEGRATIONS](https://docs.agentengineering.world/INTEGRATIONS/) |
| Tool directory | [TOOLS](https://docs.agentengineering.world/TOOLS/) |
| ACP client | [ACP](https://docs.agentengineering.world/ACP/) |
| Public participation policy | [PARTICIPATION](https://docs.agentengineering.world/PARTICIPATION/) |
| Community | [COMMUNITY.md](docs/COMMUNITY.md) |
| Data and privacy | [DATA](https://docs.agentengineering.world/DATA/) |
| Architecture | [ARCHITECTURE](docs/ARCHITECTURE.md) |
| Releases | [RELEASING](docs/RELEASING.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## Contributing

Help improve the code, documentation or source-backed event and tool data. Start with [CONTRIBUTING.md](CONTRIBUTING.md) or [open an issue](https://github.com/SuperagenticAI/agenteng/issues).

```sh
git clone https://github.com/SuperagenticAI/agenteng.git
cd agenteng
uv sync --frozen --all-extras
uv run --frozen pytest -q
uv run --frozen ruff check src tests scripts
uv run --frozen ruff format --check src tests scripts
```

Follow the [Code of Conduct](CODE_OF_CONDUCT.md). To report a vulnerability, use [SECURITY.md](SECURITY.md).

## License

Source code and original documentation are licensed under [Apache-2.0](LICENSE). Third-party event and speaker material retains its own rights; see [NOTICE](NOTICE) and [DATA.md](docs/DATA.md).
