# 🤖 Connect your agent

Bring Agent Engineering HQ into the workspace you already use. Start with local
MCP, then use the same requests over hosted MCP, A2A or HTTP when a service is running.

| Your starting point | Next step |
| --- | --- |
| A coding agent or editor | [Set up local MCP](#local-mcp) |
| A running remote AgentEng service | [Connect over HTTP or use the stdio bridge](#hosted-mcp-and-a-stdio-bridge) |
| An A2A client or your own integration | [Use typed questions and requests](#useful-questions-and-requests) |

AgentEng is the Agent Engineering Conference and event guide from Agent Engineering HQ. This service covers **London and San Francisco only**, including their published historical events. `discover` highlights the next published event in each city, or the most recent event when there is no upcoming one. Event names, dates, speakers and registration links come from the public website catalogue.

The official hosted origin is live at `https://a2a.agentengineering.world`. Installing this package does not start that service. Local lookup and proposal drafting work offline and require no provider key.

## Local MCP

Install the package with its `mcp` extra using your package manager or a release wheel. Ensure `agenteng` is on the client's executable path, or substitute the absolute path to your installed executable. For a source checkout:

```sh
uv sync --frozen --extra mcp
uv run --frozen --extra mcp agenteng mcp
```

Print client-specific instructions without changing any client settings:

```sh
agenteng connect codex
agenteng connect claude-code
agenteng connect cursor
agenteng connect generic
```

For an installed executable, the coding-client commands are:

```sh
codex mcp add agenteng -- agenteng mcp
claude mcp add --transport stdio agenteng -- agenteng mcp
```

Codex uses shared MCP configuration for its CLI and IDE integration. See the [official OpenAI documentation](https://developers.openai.com/codex/mcp/). Claude Code supports local command servers; see its [MCP documentation](https://code.claude.com/docs/en/mcp).

Cursor can use this entry in `.cursor/mcp.json`. A generic `mcpServers` client can use the command and arguments in its own supported configuration location:

```json
{
  "mcpServers": {
    "agenteng": {
      "type": "stdio",
      "command": "agenteng",
      "args": [
        "mcp"
      ]
    }
  }
}
```

See [Cursor's MCP documentation](https://prod.cursor.com/docs/mcp). Configuration formats differ between clients; `agenteng connect CLIENT` prints the corresponding shape. These instructions do not install a plugin, register a marketplace listing or authenticate anyone.

## Hosted MCP and a stdio bridge

Use the official host below, or replace the origin with your own self-hosted service:

```sh
agenteng connect codex --transport http --url https://a2a.agentengineering.world
agenteng connect claude-code --transport http --url https://a2a.agentengineering.world
agenteng connect cursor --transport http --url https://a2a.agentengineering.world
```

The HTTP MCP endpoint is `/mcp/` and uses Streamable HTTP. For clients that need a local command, the same installed CLI can bridge to a hosted service:

```json
{
  "mcpServers": {
    "agenteng": {
      "command": "agenteng",
      "args": [
        "--remote",
        "https://a2a.agentengineering.world",
        "mcp"
      ]
    }
  }
}
```

This bridge requires network access and relays requests to that origin; it does not silently fall back to a local snapshot. Remote tools conservatively advertise possible writes. The hosted server still controls intake availability and authorization.

## Useful questions and requests

- “Find the next Agent Engineering Conference in London.”
- “Show Agent Engineering HQ events in San Francisco.”
- “Which London sessions cover evaluation or agent harnesses?”
- “Help me draft a workshop idea for a future AgentEng event in San Francisco.”

Start with `{"operation":"discover"}` or `{"operation":"events","upcoming":true}`. Use returned IDs for agenda, speakers, tickets and planning. London 2026 is `agenteng-london-2026`; the October San Francisco event is `sf-code-engineering-2026`, whose published title remains **Code Engineering: From Coding Agents to Software Factories**.

Event-day operations: `{"operation":"live","at":"2026-10-16T10:40:00+01:00"}` returns a now/next venue-screen snapshot (`at` is optional and also works for `now` and `next`), `{"operation":"bingo","seed":7,"size":5,"format":"svg"}` deals a reproducible talk bingo card (the card is always in `data`; `format` text, svg or html also returns a printable copy in `artifact`, and json, the default, leaves `artifact` empty), `{"operation":"about","section":"connect"}` returns the organiser, chair and connection details, and `{"operation":"hq","section":"manifesto"}` returns Agent Engineering HQ content. City filters accept website slugs such as `san-francisco`.

An LLM client can use the same typed operations through MCP, or translate them to `POST /v1/query` using `/openapi.json`. A2A clients discover `/.well-known/agent-card.json` and send A2A 1.0 JSON-RPC to `/` with `A2A-Version: 1.0`. The card advertises skills, examples and any enabled participant security requirements. Client/model usage may have its own costs; default AgentEng lookup and drafting make zero server-side model calls.

## Tool directory

Use the same single MCP tool for `disciplines`, `tools` and `tool`:

```json
{
  "request": {
    "operation": "tools",
    "discipline": "memory",
    "limit": 20,
    "offset": 0
  }
}
```

A2A data parts and HTTP bodies use the inner object. Continue with `next_offset` and unchanged filters. Plain “List memory tools” questions route to directory browsing. Names, aliases, categories and links are bundled offline; no model call or third-party installation is needed. See [full directory usage and attribution](TOOLS.md).

## Discovery surfaces

The hosted service provides crawlable HTML at `/` and `/events/EVENT_ID`, individual event JSON-LD, `/events.json`, `/llms.txt`, `/robots.txt` and `/sitemap.xml`. The tool directory adds `/tools`, `/tools/TOOL_ID` and the full `/tools.json` export. Human-readable pages link to the official registration source; JSON includes catalogue freshness and supporting evidence.

These surfaces make the service accessible to crawlers and agents. They do not guarantee indexing, search ranking, recommendations by an LLM or automatic discovery in a coding client. An `llms.txt` is a reading guide, not an instruction override or a registry submission. Event markup preserves published facts; see [Google's event structured-data guidance](https://developers.google.com/search/docs/appearance/structured-data/event).

The website already maintains its own metadata, sitemap and `llms.txt`. Release staging adds an **AgentEng agent guide** and an **event feed** for website publication. Link the guide from the website and its existing `llms.txt` after the service is deployed; preserve the site's existing event and organizer identities.

## Private participation

Local drafts use `proposal_draft`, `proposal_preview` and `proposal_export`. An agent must never submit as a side effect of discovery or brainstorming. London 2026 has an invited programme and no public CFP; no San Francisco public CFP is announced in the bundled snapshot.

An enabled private pilot requires a distinct participant credential issued by the organizer. HTTP/A2A clients send it as an authorization bearer header; local stdio clients can use `AGENTENG_PARTICIPANT_TOKEN` through their client's supported secret/environment configuration. Never commit the credential to project configuration. Optional inference credentials are separate and do not authorize submissions.

Private operations are `proposal_prepare`, `proposal_submit`, `proposal_status` and `proposal_withdraw`. Show the exact prepared draft, privacy terms and recipient to the contributor, obtain explicit confirmation, then submit the unchanged draft and preview reference. A broad tool serving an enabled intake advertises writes and withdrawal; it is not marked read-only. See [participation usage](PARTICIPATION.md).

## Website A2A chat

The conference website's native **Talk to AgentEng A2A** panel discovers the
agent card and sends A2A 1.0 JSON-RPC `SendMessage` requests. The service permits
the `A2A-Version` header in browser CORS preflights. Public requests continue
to use catalogue lookup with no model calls; adding a chat UI does not enable
inference or private intake.

The default allowed browser origin is `https://agentengineering.world`.
For a local website running at `http://localhost:8080`, configure the local
service explicitly:

```sh
AGENTENG_PUBLIC_URL=http://127.0.0.1:8000 AGENTENG_ALLOWED_ORIGINS=http://localhost:8080 agenteng serve
```

Set `VITE_AGENTENG_A2A_URL=http://127.0.0.1:8000` in the website's `.env.local`.
Use the actual browser origin if your development port differs. Deploy the
service update before publishing the website chat. The browser retains only a
page-local transcript; the current A2A adapter answers each question independently.
Future model integration belongs in the service, with provider credentials
kept out of browser configuration.
