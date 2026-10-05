<img src="https://raw.githubusercontent.com/SuperagenticAI/agenteng/main/docs/assets/logo.png" alt="Agent Engineering HQ" width="96" height="96">

# AgentEng · Agent Engineering HQ

Find the Agent Engineering Conference and Agent Engineering HQ events in **London and San Francisco**, explore the speakers, and participate from your coding agent or terminal.

AgentEng provides an offline-capable Python CLI, a single-tool MCP server and an A2A 1.0 agent over one public catalogue. Default requests use **zero server-side model calls**. Optional model synthesis and bounded RLM are included, disabled by default.

[Source](https://github.com/SuperagenticAI/agenteng) · [Issues](https://github.com/SuperagenticAI/agenteng/issues) · [Documentation](docs/index.md) · [Getting started](#getting-started) · [Coding-agent integrations](docs/INTEGRATIONS.md) · [Participation](docs/PARTICIPATION.md) · [Contribute](CONTRIBUTING.md) · [Security](SECURITY.md)

## What it does

- Discover public London and San Francisco events, speakers, agendas and recordings.
- Browse 456 tool/model/infrastructure listings across twelve disciplines, with search, filters, pagination and source links.
- Read published ticket prices and follow the official registration link.
- Search attributed public sources, select sessions by topic and export a UTC calendar.
- Use the same typed requests from the CLI, MCP, A2A or HTTP.
- See source links, snapshot freshness, date precision and timezone-aware event state.
- Prepare reusable local talk, workshop and event-idea drafts, with preview and Markdown export.
- Run an optional, credentialed private intake pilot for one organizer, disabled by default.

The catalogue is a snapshot. It does not verify live ticket availability or registration approval. Unknown historical dates and session times remain unknown. Consult the linked organizer/registration page for current details. See [data and attribution](docs/DATA.md).

## Getting started

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required. Once the repository is published, clone it:

```sh
git clone https://github.com/SuperagenticAI/agenteng.git
cd agenteng
```

From the source checkout:

```sh
uv sync --frozen
uv run --frozen agenteng events --upcoming
uv run --frozen agenteng discover
uv run --frozen agenteng disciplines
uv run --frozen agenteng tools --discipline memory
uv run --frozen agenteng tool langgraph
uv run --frozen agenteng tickets agenteng-london-2026
uv run --frozen agenteng agenda agenteng-london-2026 --topic memory
uv run --frozen agenteng ask 'When is the next London conference?'
uv run --frozen agenteng participate
uv run --frozen agenteng plan agenteng-london-2026 --interest evaluation --format ics --output agenda.ics
```

For an executable available outside the checkout, use `uv tool install .` or `uv tool install '.[mcp]'` for local MCP. With pip, use a virtual environment and `python -m pip install .` (or `'.[mcp]'`). The published installer requires Python 3.12+, curl, venv and pip on a POSIX system.

This is an initial **0.1.0 alpha**. Public package/installer distribution and hosted endpoints have not yet been published. Source installs work today; registry and website installation instructions will be announced after verified publication.

The CLI uses its bundled catalogue offline. Put global options before the command:

```sh
agenteng --json events --city London
agenteng --remote https://YOUR_HOST events --upcoming
agenteng --catalogue ./catalogue.json speakers --city 'San Francisco'
agenteng query '{"operation":"events","upcoming":true}'
```

Run `agenteng --help` or `agenteng COMMAND --help` for command options.

Draft an idea without sending it:

```sh
agenteng engage --city London --output draft.json
agenteng proposal preview draft.json
agenteng proposal export draft.json --format markdown --output draft.md
```

## Tool directory

The directory covers all 461 entries in the imported SuperRadar snapshot, normalized into 456 listings after duplicate merges and separating Graphiti from Zep. Browse alphabetically across the website's twelve disciplines; there is no fixed category quota. Listings provide attributed names and links, not popularity rankings or integrations. Source Hold/deprecated entries remain accessible with `--status all` and are omitted from default browse results.

```sh
agenteng tools --discipline inference --kind runtime
agenteng tools --search 'Gemini CLI'
agenteng --json tools --limit 100 --offset 100 --status all
agenteng tool letta-memory
```

Repeat filters with the returned `next_offset` to retrieve every matching listing. All directory operations work offline with zero model calls. See [directory usage, provenance and contribution policy](docs/TOOLS.md).

## Connect an agent

Local MCP exposes exactly one typed `agenteng` tool:

```sh
uv run --frozen --extra mcp agenteng mcp
```

`agenteng connect codex`, `agenteng connect claude-code` and `agenteng connect cursor` print local setup instructions. Add `--transport http --url https://YOUR_HOST` for a running remote service. They do not modify editor settings. See [integration examples](docs/INTEGRATIONS.md).

After a tool install, a stdio client can use:

```json
{"mcpServers":{"agenteng":{"command":"agenteng","args":["mcp"]}}}
```

Run the combined HTTP, MCP and A2A service:

```sh
uv run --frozen --extra server agenteng serve --host 127.0.0.1 --port 8000
```

| Interface | Route |
| --- | --- |
| MCP Streamable HTTP | `/mcp/` |
| A2A 1.0 discovery | `/.well-known/agent-card.json` |
| A2A JSON-RPC | `/` with `A2A-Version: 1.0` |
| Typed HTTP query | `/v1/query` |
| Catalogue / health | `/catalogue.json`, `/health` |
| Crawlable discovery | `/`, `/events/EVENT_ID`, `/events.json`, `/tools`, `/tools/TOOL_ID` |
| Full tool directory feed | `/tools.json` |
| Crawler / agent guides | `/llms.txt`, `/robots.txt`, `/sitemap.xml` |

MCP call example:

```json
{"name":"agenteng","arguments":{"request":{"operation":"tickets","event_id":"agenteng-london-2026"}}}
```

Public operations are `disciplines`, `tools`, `tool`, `discover`, `events`, `event`, `agenda`, `speakers`, `tickets`, `recordings`, `search`, `plan`, `ask` and `participate`. Draft operations are `proposal_draft`, `proposal_preview` and `proposal_export`. Begin with `discover` for featured London/San Francisco events and interfaces, or `events` for published IDs. The same request can be an A2A JSON data part or an HTTP body; plain A2A text uses question routing or public-source search. Responses include supporting sources and snapshot metadata. A2A returns immediate messages and advertises no streaming or push notifications.

The intended official host is `a2a.agentengineering.world`, once published. To self-host, set `AGENTENG_PUBLIC_URL` to your HTTPS origin and configure allowed origins. See [deployment](deploy/README.md), [architecture](docs/ARCHITECTURE.md) and the [HTTP MCP config](deploy/mcp-http.json).

For Google Cloud Run, the [console setup guide](deploy/README.md) connects this repository through Cloud Build with **Push new tag**, regex `^v.*$` and configuration file `cloudbuild.yaml`. Version tags deploy the public server and separately trigger PyPI publishing; ordinary commits do not deploy either release.

## Optional model engines

`lookup` and `auto` remain model-free. `standard` performs one provider request. `rlm` offers a persistent Monty sandbox with one model-visible `run_code` tool and scoped evidence reads. The root can make **one child OR leaf delegation total**, at **maximum depth 1**. Children cannot delegate. All calls share model-call, token-reservation and deadline limits.

Install the RLM extra and configure an operator environment only when you intend to test it:

```sh
uv sync --frozen --extra rlm
# Configure the enable flag, operator credential, provider key and model in your environment.
uv run --frozen --extra rlm agenteng ask 'Compare memory sessions' --engine rlm --event agenteng-london-2026
```

Use `.env.example` as a variable reference; it is not loaded automatically. `AGENTENG_ENABLE_STANDARD=1` and `AGENTENG_ENABLE_RLM=1` enable the respective paths. Both require `AGENTENG_OPERATOR_TOKEN`, `AGENTENG_MODEL_API_KEY` and an operator-selected `AGENTENG_MODEL`; remote callers must supply the operator bearer credential. An OpenAI-compatible provider can be selected with `AGENTENG_MODEL_BASE_URL` and must support the required tool/JSON features.

Defaults cap requests at 6 model calls, 1,200 output tokens per call, 12,000 conservatively reserved tokens and 45 seconds. One recursion can involve several model calls. These are per-request limits, not a daily spending cap. Model code cannot access host files, network or environment callbacks. Citation checks enforce source membership, not the truth of generated prose. Live-provider answer quality and billing are not yet validated; tests use scripted providers. The public container omits the RLM runtime and keeps both engines disabled.

## Participate and contribute

Have an idea for a talk, workshop or future event in London or San Francisco? See [Community participation](docs/COMMUNITY.md) and [draft/intake usage](docs/PARTICIPATION.md). Private proposals go only to Agent Engineering HQ; public event discussions are opt-in. An idea or submission does not guarantee review, acceptance, a response or an event. **London 2026 has an invited programme and no public CFP.**

`agenteng participate` (or a typed `{"operation":"participate"}` agent request) returns the public organizer contact, a proposal checklist and the current capability limits. It sends no message and creates no submission receipt.

Offline drafting is available now. Optional private intake requires persistent storage, an operator-approved privacy notice and separate participant credentials. `proposal_prepare` previews the exact draft; `proposal_submit` requires explicit confirmation and returns a receipt after storage. Authors can inspect status or withdraw. The organizer reviews through local private-store administration. The pilot does not provide public signup, notifications or automatic publication. An enabled intake advertises write behavior through MCP; the default service stays read-only. The supplied Cloud Run deployment keeps intake disabled.

Code, documentation and source-backed data improvements are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), follow the [Code of Conduct](CODE_OF_CONDUCT.md), and use private [security reporting](SECURITY.md) for vulnerabilities.

```sh
uv sync --frozen --all-extras
uv run --frozen pytest -q
uv run --frozen ruff check src tests scripts
uv run --frozen python scripts/check-public-release.py
```

The website is the event-data source. Updating its public catalogue requires a website checkout with TypeScript installed:

```sh
node scripts/export-website.mjs /path/to/agent-engineering-summit
```

Exports record their source revision/content hash and publication time. Changed event content requires a refreshed build; no background synchronization is claimed. Version tags trigger verified PyPI publishing and a GitHub release once the repository publishing secret is configured. See [release verification and publisher setup](docs/RELEASING.md) and [CHANGELOG.md](CHANGELOG.md).

## License

Source code and original documentation are licensed under [Apache-2.0](LICENSE). Third-party event/speaker material and linked recordings retain their own rights; see [NOTICE](NOTICE) and [DATA.md](docs/DATA.md).
