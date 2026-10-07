# Command reference

Every visible `agenteng` command and subcommand, with its main options and one
real example. It is built from the CLI's own help text for 0.0.7, and a test checks
that every visible command and option is listed here.
Run `agenteng COMMAND --help` for the same text in your terminal.

`ae` is a short alias for developers in their own terminal: `ae talks` is the same
as `agenteng talks`. Docs and the website always write `agenteng`.

## Global options

```text
agenteng [GLOBAL OPTIONS] COMMAND [ARGS]...
```

| Option | Meaning |
| --- | --- |
| `--json` | Print the shared Result JSON. Put it **before** the command: `agenteng --json talks`. |
| `--remote URL` | Send the request to a hosted AgentEng server, for example `https://a2a.agentengineering.world`, instead of the bundled offline catalogue. |
| `--catalogue FILE` | Use a local public catalogue JSON file. |
| `--version` | Print `agenteng, version 0.0.7` as plain text. |
| `-h`, `--help` | Show help for `agenteng` or any command. |

With no command in a terminal, `agenteng` opens the interactive menu. Without a
terminal it prints the help text.

City shortcuts: commands that take a city also accept the website wording
`--london` and `--sf` (or `--san-francisco`). City values accept slugs such as
`san-francisco` and `sf`. Commands that take an `EVENT_ID` also accept a city
(`london`, `san-francisco`) and use that city's next event, else its latest one.

## Output and JSON

On a terminal, commands print cards and tables. Agents and scripts get the
**Result JSON** in any of three ways:

- `agenteng --json talks` (the global flag, before the command);
- `AGENTENG_OUTPUT=json agenteng talks`;
- piping stdout, for example `agenteng talks | jq .`.

The Result JSON is the same object MCP, A2A and `POST /v1/query` return:

| Field | Meaning |
| --- | --- |
| `status` | `ok`, `not_found`, `unavailable` or `error`. |
| `answer` | One short human sentence. |
| `data` | The records: a list, or an object for single-record commands. |
| `sources` | Published sources behind the answer: `id`, `url`, `text`, `event_id`, `kind`. |
| `catalogue_version` | Version of the bundled or hosted catalogue. |
| `evaluated_at`, `published_at` | When the answer was made and when the catalogue was published (ISO 8601). |
| `stale` | `true` when the catalogue is older than the configured maximum age. |
| `engine` | `lookup` unless a model engine was explicitly requested and enabled. |
| `usage` | Model usage, empty for lookups. |
| `artifact` | A file body for `--format ics`, bingo `text`/`svg`/`html`, else `null`. |

When a command returns an `artifact` and you do not pass `--output` or `--json`,
the artifact itself is printed (for example the `.ics` text).

These print something other than Result JSON:

| Command | Output |
| --- | --- |
| `agenteng --version` | Plain text: `agenteng, version 0.0.7`. |
| `agenteng connect CLIENT` | Plain-text setup instructions, never JSON. |
| `agenteng code --list` | A table on a terminal; with `--json` or piped, `{"registry": URL, "agents": [...]}`. |
| `agenteng code --json PROMPT` | Newline-delimited JSON events, one per line. |
| `agenteng live` | A full-screen board on a terminal; with `--json` or piped, one Result JSON snapshot. |
| `agenteng inbox list`, `agenteng inbox review` | Plain JSON records for the organizer, not a Result. |
| `agenteng mcp`, `agenteng serve` | Long-running servers. |

## Exit codes

| Code | When |
| --- | --- |
| `0` | Success, including an **empty but valid** result. |
| `1` | Unknown ID, no single match, unavailable feature, invalid input or a failed request. |
| `2` | Usage error: unknown option, missing argument or invalid choice. |
| `130` | `agenteng code` turn cancelled with Ctrl-C. |

**Empty but valid** means a list or snapshot command ran correctly and found
nothing: `agenteng now` between sessions,
`agenteng search` with zero hits, or `agenteng talks --search` with no match.
These exit `0`. Their Result JSON is unchanged, so `status` is still `not_found`
with an empty list (or a snapshot whose `session` is `null`). Check `data`, not
the exit code, to tell empty from full. The commands this applies to are
`events`, `speakers`, `talks`, `faq`, `themes`, `sponsors`, `recordings`,
`search`, `ask`, `agenda`, `now`, `next` and `live`.

An unknown ID still exits `1` with `status` `not_found`: `agenteng event nope`,
`agenteng speaker nope`, `agenteng tool nope`, `agenteng talk nope` or
`agenteng now nope`.

## Events and programme

### agenteng events

List events with published date precision and current state.

CITY is optional: London or San Francisco (slugs such as san-francisco work).

```text
agenteng events [OPTIONS] [CITY]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--city` TEXT | London or San Francisco (slugs such as san-francisco work). |  |
| `--upcoming`, `--next` | Only upcoming events. |  |
| `--past`, `--history`, `--previous` | Only past events. |  |

```sh
agenteng events --city London --upcoming
```

### agenteng event

Read one event by its published ID (or a city: london, san-francisco).

EVENT_ID is an event ID from agenteng events, or a city. Omit it in a terminal to pick one.

```text
agenteng event [OPTIONS] [EVENT_ID]
```

```sh
agenteng event agenteng-london-2026
```

### agenteng agenda

Read an event's public agenda; optionally export .ics.

EVENT_ID is an event ID or a city (london, san-francisco). Omit it in a terminal to pick one.

```text
agenteng agenda [OPTIONS] [EVENT_ID]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--topic` TEXT | Only sessions matching this text, for example memory. |  |
| `--format` CHOICE | json for Result JSON, ics for a calendar file. One of: `json`, `ics`. | `json` |
| `--output` FILE | Write an .ics calendar when --format ics. |  |

```sh
agenteng agenda agenteng-london-2026 --format ics --output london.ics
```

### agenteng speakers

List published speakers with roles, companies, talks and abstracts.

```text
agenteng speakers [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Only speakers at this event ID. |  |
| `--city` TEXT | Only speakers in London or San Francisco. |  |
| `--search` TEXT | Match name, company, talk title or abstract. |  |

```sh
agenteng speakers --city London --search memory
```

### agenteng speaker

Read one speaker: bio fields, links, projects, disciplines and full abstract.

SPEAKER_ID is a speaker ID from agenteng speakers, for example samuel-colvin.

```text
agenteng speaker [OPTIONS] SPEAKER_ID
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Event ID, when the speaker appears at more than one. |  |

```sh
agenteng speaker samuel-colvin
```

### agenteng talks

List published talks with full abstracts.

```text
agenteng talks [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Only talks at this event ID. |  |
| `--search` TEXT | Match talk title, abstract or speaker. |  |
| `--speaker` TEXT | Only talks by this speaker ID. |  |

```sh
agenteng talks --search memory
```

### agenteng talk

Read one talk by session ID, speaker ID, or --search text.

IDENTIFIER is a session ID or speaker ID from agenteng talks.

```text
agenteng talk [OPTIONS] [IDENTIFIER]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Only look in this event ID. |  |
| `--search` TEXT | Find the talk by title or abstract text. |  |

```sh
agenteng talk samuel-colvin
```

### agenteng faq

Read published FAQ answers from the conference website.

```text
agenteng faq [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Only FAQ entries for this event ID. |  |
| `--search` TEXT | Match FAQ question or answer text. |  |

```sh
agenteng faq --search tickets
```

### agenteng venue

Read venue address, tour link, track and accessibility notes.

EVENT_ID is an event ID or a city (london, san-francisco). Omit it in a terminal to pick one.

```text
agenteng venue [OPTIONS] [EVENT_ID]
```

```sh
agenteng venue london
```

### agenteng sponsors

List published sponsors and London support options.

```text
agenteng sponsors [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--city` TEXT | Only sponsors in London or San Francisco. |  |

```sh
agenteng sponsors --city London
```

### agenteng conduct

Read the published code of conduct summary and report contact.

```text
agenteng conduct [OPTIONS]
```

```sh
agenteng conduct
```

### agenteng themes

List published program themes from the website.

```text
agenteng themes [OPTIONS]
```

```sh
agenteng themes
```

### agenteng tickets

Read published prices and the official registration link.

EVENT_ID is an event ID or a city (london, san-francisco). Omit it in a terminal to pick one.

```text
agenteng tickets [OPTIONS] [EVENT_ID]
```

```sh
agenteng tickets london
```

### agenteng recordings

Find published recordings.

```text
agenteng recordings [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Only recordings from this event ID. |  |
| `--city` TEXT | Only recordings from London or San Francisco. |  |

```sh
agenteng recordings --city London
```

## At the event

### agenteng now

Show what is on now from the published timed agenda.

EVENT_ID is an event ID or a city; defaults to the live conference.

```text
agenteng now [OPTIONS] [EVENT_ID]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--at` TEXT | Pretend it is this time: ISO (2026-10-16T10:15) or HH:MM on the event day. |  |
| `--screen` | Full-screen venue display; same as `agenteng live`. |  |

```sh
agenteng now agenteng-london-2026 --at 10:40
```

### agenteng next

Show the next published session from the timed agenda.

EVENT_ID is an event ID or a city; defaults to the live conference.

```text
agenteng next [OPTIONS] [EVENT_ID]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--at` TEXT | Pretend it is this time: ISO (2026-10-16T10:15) or HH:MM on the event day. |  |

```sh
agenteng next agenteng-london-2026 --at 10:40
```

### agenteng live

Full-screen now/next board for venue screens. Ctrl-C exits.

Piped or with --json it prints one Result JSON snapshot instead.

```text
agenteng live [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Event ID or city; defaults to the live conference. |  |
| `--refresh` INTEGER | Seconds between screen refreshes. | `30` |
| `--at` TEXT | Pretend it is this time: ISO (2026-10-16T10:15) or HH:MM on the event day. The clock then runs forward from it. |  |
| `--once` | Draw one frame and exit (no full screen). |  |

```sh
agenteng live --event london --at 10:40 --refresh 15
```

### agenteng bingo

Talk bingo from published talk terms. Local only; nothing is sent.

```text
agenteng bingo [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Event ID or city; defaults to the London conference. |  |
| `--size` CHOICE | Grid size: 5x5 with a free centre, or 4x4. One of: `4`, `5`. | `5` |
| `--seed` INTEGER | Same seed, same card. Printed on every card. |  |
| `--format` CHOICE | Printable text, SVG or HTML. Default: a card in the terminal, JSON when piped. One of: `text`, `svg`, `html`, `json`. |  |
| `--output` FILE | Write the card to a file. |  |
| `--play` | Mark squares as you hear them (terminal only). |  |

```sh
agenteng bingo --seed 7 --size 4 --format html --output bingo.html
```

## Search and ask

### agenteng search

Search public sources without model calls.

QUERY is the text to find in published talks, speakers, FAQ, themes and site pages.

```text
agenteng search [OPTIONS] QUERY
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Only search this event ID. |  |
| `--city` TEXT | Only search London or San Francisco. |  |

```sh
agenteng search 'context engineering' --city London
```

### agenteng ask

Find attributed excerpts, or explicitly request an enabled model engine.

QUERY is a plain question, for example "When is the next London conference?".

```text
agenteng ask [OPTIONS] QUERY
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--event` TEXT | Only answer from this event ID. |  |
| `--engine` CHOICE | lookup needs no model; standard and rlm need a server-side enabled model. One of: `lookup`, `auto`, `standard`, `rlm`. | `lookup` |

```sh
agenteng ask 'When is the next London conference?'
```

### agenteng query

Execute the same JSON request accepted by MCP and A2A.

PAYLOAD is one Request JSON object, for example '{"operation":"events"}'.

```text
agenteng query [OPTIONS] PAYLOAD
```

```sh
agenteng query '{"operation":"events","city":"London","upcoming":true}'
```

## Agent Engineering HQ and discovery

### agenteng about

What Agent Engineering is, who runs it, and how to connect your agent.

```text
agenteng about [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--chair` | Only the conference chair. |  |
| `--organiser`, `--organizer` | Only the organiser. |  |
| `--connect` | Only how to connect agents. |  |

```sh
agenteng about --connect
```

### agenteng hq

Agent Engineering HQ: the manifesto, the mindset and further reading.

SECTION is optional: manifesto, mindset or reading. Omit it for all three.

```text
agenteng hq [OPTIONS] [[manifesto|mindset|reading]]
```

```sh
agenteng hq manifesto
```

### agenteng discover

Find AgentEng London/San Francisco events and agent connection details.

```text
agenteng discover [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--city` TEXT | London or San Francisco. |  |

```sh
agenteng discover --city 'San Francisco'
```

### agenteng participate

Find organizer contact and guidance for talk/event ideas.

```text
agenteng participate [OPTIONS]
```

```sh
agenteng participate
```

## Tool directory

### agenteng disciplines

List the twelve disciplines, tool counts and available filters.

```text
agenteng disciplines [OPTIONS]
```

```sh
agenteng disciplines
```

### agenteng tools

Browse the full tool directory offline; alphabetical, paginated and model-free.

```text
agenteng tools [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--discipline` CHOICE | Only tools in this discipline. One of: `prompt`, `context`, `harness`, `eval`, `memory`, `inference`, `loop`, `agentic`, `code`, `protocol`, `graph`, `search`. |  |
| `--kind` CHOICE | Only tools of this kind. One of: `agent`, `framework`, `cli`, `ide`, `extension`, `sandbox`, `connector`, `protocol`, `registry`, `model`, `runtime`, `hosting`, `database`, `search`, `evaluation`, `observability`, `security`, `browser`, `app`, `embedding`, `documentation`. |  |
| `--category` TEXT | Exact source category; use agenteng --json disciplines to find categories. |  |
| `--search` TEXT | Match names, aliases, IDs and category tags. |  |
| `--limit` INTEGER | Tools per page. | `20` |
| `--offset` INTEGER | Skip this many tools (next page). | `0` |
| `--status` CHOICE | Listing status to show; all shows every status. One of: `listed`, `hold`, `deprecated`, `all`. | `listed` |

```sh
agenteng tools --discipline memory --kind database --limit 10
```

### agenteng tool

Read a tool's links, tags, aliases and source provenance.

TOOL_ID is a tool ID from agenteng tools, for example langgraph.

```text
agenteng tool [OPTIONS] TOOL_ID
```

```sh
agenteng tool langgraph
```

## Connect agents and run servers

### agenteng connect

Print A2A, MCP or ACP setup instructions without changing client configuration.

CLIENT is a2a, mcp, acp, codex, claude-code, cursor or generic. Output is plain text.

```text
agenteng connect [OPTIONS] {a2a|mcp|acp|codex|claude-code|cursor|generic}
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--transport` CHOICE | stdio runs agenteng mcp locally; http uses the hosted MCP server. One of: `stdio`, `http`. | `stdio` |
| `--url` TEXT | Hosted server base URL for A2A or HTTP MCP. | `https://a2a.agentengineering.world` |

```sh
agenteng connect a2a
agenteng connect mcp --transport http
agenteng connect acp
agenteng connect claude-code --transport http
```

### agenteng mcp

Run one-tool MCP over stdio (install [mcp]).

```text
agenteng mcp [OPTIONS]
```

```sh
agenteng mcp
```

### agenteng serve

Run the combined HTTP, MCP and A2A server (install [server]).

```text
agenteng serve [OPTIONS]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--host` TEXT | Address to listen on. | `127.0.0.1` |
| `--port` INTEGER | Port to listen on. | `8000` |
| `--access-log`, `--no-access-log` | Per-request access lines (client address, path, status). Off: the host's own request log is enough, and AgentEng adds none. |  |

```sh
agenteng serve --host 127.0.0.1 --port 8000
```

### agenteng code

Experimental: drive an ACP coding agent with AgentEng context (install [acp]).

Spawns the agent over the Agent Client Protocol, attaches the AgentEng MCP server and streams its reply. Every permission request is asked in the terminal; without a terminal it is rejected. Nothing is auto-approved.

With no PROMPT in a terminal (or with --chat) it opens a chat on one session: /help, /context ID, /agent, /exit or Ctrl-D. Ctrl-C cancels the current turn. With --chat and piped stdin, each line is one turn.

PROMPT is optional free text for one turn.

```text
agenteng code [OPTIONS] [PROMPT]...
```

| Option | Meaning | Default |
| --- | --- | --- |
| `--agent` TEXT | Agent to launch (see --list). Default: first installed. |  |
| `--agent-command` TEXT | Custom ACP agent command line, for example 'my-agent --acp'. |  |
| `--list` | Show known ACP agents and which are on PATH. |  |
| `--cwd` DIRECTORY | Working directory for the agent session (default: current directory). |  |
| `--context` TEXT | Attach a talk, event, speaker or tool:ID record to the prompt. Repeatable. |  |
| `--no-mcp` | Do not attach the AgentEng MCP server. |  |
| `--npx` | Launch a missing npm-distributed agent through npx. |  |
| `--show-thoughts` | Show the agent's thought chunks. |  |
| `--allow-always-option` | Also offer the agent's 'allow always' choice in permission prompts (hidden by default). |  |
| `--chat` | Keep one session open for several turns (default with no PROMPT in a terminal). |  |
| `--json` | Stream newline-delimited JSON events. |  |

```sh
agenteng code --agent claude "summarise talk agenteng-london-2026-2 in three bullets"
```

## Environment

| Variable | What it does |
| --- | --- |
| `AGENTENG_OUTPUT=json` | Always print Result JSON, as `--json` does. |
| `AGENTENG_CONFIG_DIR` | Folder for `agenteng code` logs. Default `$XDG_CONFIG_HOME/agenteng`, else `~/.config/agenteng`. |

Installer variables are listed under [installer options](index.md#installer-options).
Server settings are in [`.env.example`](https://github.com/SuperagenticAI/agenteng/blob/main/.env.example).
