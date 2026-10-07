---
title: Agent Engineering HQ
hide:
  - navigation
  - toc
---

<div class="agenteng-hero" markdown>

<img src="assets/logo.png" alt="Agent Engineering HQ" class="agenteng-hero-logo" width="192" height="192" />

<p class="agenteng-eyebrow">Conferences · Community · Tools</p>

# Agent Engineering HQ

<p class="agenteng-hero-tagline">The home of the agent engineering discipline.</p>

<p class="agenteng-hero-description">Meet the people, explore the tools and find the events shaping agent engineering. Take <strong>AgentEng</strong> with you, from your terminal to the coding agent you already use.</p>

<ul class="agenteng-highlights" aria-label="At a glance">
  <li>📍 London + San Francisco</li>
  <li>🧠 12 disciplines</li>
  <li>💻 CLI · MCP · A2A</li>
  <li>🔓 Open source</li>
</ul>

[🚀 Get started](#installation-and-first-run){ .md-button .md-button--primary }
[🤖 Connect your agent](INTEGRATIONS.md){ .md-button }
[🌍 Event website](https://agentengineering.world){ .md-button }

</div>

## 🧭 Find your starting point { #find-your-starting-point }

<div class="grid cards agenteng-cards" markdown>

-   **📅 Discover events**

    ---

    Find London and San Francisco events, speakers, sessions and official registration links.

    [Explore events →](#explore-events)

-   **🤖 Bring your coding agent**

    ---

    Connect through one MCP tool, A2A or HTTP. Use the same catalogue from your existing workspace.

    [Connect an agent →](INTEGRATIONS.md)

-   **🧰 Explore the tool directory**

    ---

    Browse 456 attributed tools, models and infrastructure listings across twelve disciplines.

    [Browse the directory →](TOOLS.md)

</div>

## 🚀 Installation and first run { #installation-and-first-run }

Install the latest AgentEng from PyPI. The one-liner installs the CLI with the
`server` extras (MCP + A2A). RLM stays optional and is not included.
The installer is served at [agentengineering.world/install.sh](https://agentengineering.world/install.sh)
and mirrored at [a2a.agentengineering.world/install.sh](https://a2a.agentengineering.world/install.sh).

```sh title="Install AgentEng"
curl -fsSL https://agentengineering.world/install.sh | sh
# Or: uv tool install --upgrade 'agenteng[server]'
agenteng                                # interactive menu on a TTY
agenteng discover
agenteng events --upcoming
agenteng --json events                  # Result JSON for agents
agenteng connect cursor
```

### Installer options

The installer reads these optional environment variables. Put them before `sh`:

```sh
curl -fsSL https://agentengineering.world/install.sh | AGENTENG_VERSION=0.0.7 sh
```

| Variable | Default | What it does |
| --- | --- | --- |
| `AGENTENG_VERSION` | latest on PyPI | Pin a PyPI version, for example `0.0.7`. |
| `AGENTENG_EXTRAS` | `server` | Extras to install (`server` is MCP + A2A). Set it empty for the CLI only, or add `acp` as in `server,acp`. |
| `AGENTENG_INSTALL_VERBOSE` | `0` | Set to `1` to stream package manager output instead of writing it to a log. |
| `AGENTENG_UV_INSTALLER_URL` | `https://astral.sh/uv/install.sh` | Alternate uv installer URL, used only when uv is missing. |
| `AGENTENG_INSTALL_DIR` | `$XDG_DATA_HOME/agenteng`, else `~/.local/share/agenteng` | Virtualenv location for the pip fallback. |
| `AGENTENG_BIN_DIR` | `~/.local/bin` | Where the pip fallback links `agenteng` and `ae`. |
| `AGENTENG_PYTHON` | first Python 3.12+ on `PATH` | Python used by the pip fallback. |

`NO_COLOR` turns off the animated, coloured output. The installer never uses sudo.

### CLI environment

| Variable | What it does |
| --- | --- |
| `AGENTENG_OUTPUT=json` | Always print Result JSON, as `--json` does. |
| `AGENTENG_CONFIG_DIR` | Folder for `agenteng code` logs. Default `$XDG_CONFIG_HOME/agenteng`, else `~/.config/agenteng`. |

**Your first result:** published London and San Francisco events as readable cards
(or Result JSON for agents), with supporting source links. The CLI uses its bundled
snapshot, so event lookup, tool browsing  work offline with
**zero model calls** and no provider key.

On a terminal, `agenteng` opens an interactive menu and commands render tables and cards.
Pass `--json`, set `AGENTENG_OUTPUT=json`, or pipe stdout to get the shared Result
JSON used by MCP and A2A. This source tracks the **0.0.7 alpha** release.
Run `agenteng --help` to explore commands, or `agenteng COMMAND --help` for options.
Every command, flag and exit code is listed in the [command reference](COMMANDS.md).
Installing the CLI does not start or publish a hosted service.

The installer also adds `ae`, a short alias for developers: `ae talks` is the same as `agenteng talks`.

## 📅 Explore events { #explore-events }

Find an event, then use its returned ID to explore the agenda, speakers or ticket
terms. Put global options such as `--json` before the command.

```sh title="Find your next event"
agenteng events --city London --upcoming
agenteng events --city 'San Francisco'
agenteng ask 'When is the next London conference?'
agenteng --json events
```

```sh title="Explore a published programme"
agenteng speakers --city London
agenteng speaker samuel-colvin
agenteng talks --search memory
agenteng talk samuel-colvin
agenteng agenda agenteng-london-2026 --topic memory
agenteng agenda agenteng-london-2026 --format ics --output london.ics
agenteng faq --search tickets
agenteng venue agenteng-london-2026
agenteng sponsors
agenteng conduct
agenteng themes
agenteng now agenteng-london-2026
agenteng next agenteng-london-2026
agenteng save samuel-colvin
agenteng agenda --london
agenteng tickets agenteng-london-2026
```

The catalogue is a dated snapshot. Follow the event's official registration link
for current availability and details. See [data and attribution](DATA.md).

## 🎉 At the event { #at-the-event }

```sh title="Venue screens, bingo and the HQ"
agenteng live                           # full-screen now/next board; Ctrl-C exits
agenteng live --at 10:40 --refresh 15   # demo the board at a time on the event day
agenteng now --screen                   # same as agenteng live
agenteng bingo --seed 7                 # talk bingo from published talk terms
agenteng bingo --size 4 --format html --output bingo.html  # printable (text, svg, html)
agenteng bingo --play                   # mark squares in the terminal
agenteng about                          # definition, organiser, chair, links, how to connect agents
agenteng about --connect                # install line, MCP URL and agent card only
agenteng hq                             # manifesto, mindset and further reading
agenteng hq manifesto
```

`agenteng live` shows the current talk with a progress bar, what is next and what comes
later, with the venue, track and a large clock. Piped or with `--json` it prints a
single Result JSON snapshot, the same one agents get from `{"operation":"live"}`.
Bingo cards only use terms that appear in the event's published talk titles,
abstracts and agenda. The seed is printed on every card, so the same command
always deals the same card. Nothing is sent anywhere.

The commands shown on agentengineering.world are tracked in [site sync](SITE-SYNC.md):
city slugs (`--city san-francisco`), `--london` and `--sf`, `events --next` and
`--history`, `--list-disciplines`, `--themes` and `inspect --speaker SLUG` all run.

## 🧠 Twelve disciplines, one directory { #the-twelve-disciplines }

Explore the tooling around the whole discipline, from prompts and memory to
protocols and inference. Listings include names, categories and source links;
they are not popularity rankings or tutorials.

<ul class="agenteng-disciplines" aria-label="Agent engineering disciplines">
  <li>✍️ Prompt</li>
  <li>🧩 Context</li>
  <li>⚙️ Harness</li>
  <li>📏 Eval</li>
  <li>🧠 Memory</li>
  <li>⚡ Inference</li>
  <li>🔄 Loop</li>
  <li>🤖 Agentic</li>
  <li>💻 Code</li>
  <li>🔌 Protocol</li>
  <li>🕸️ Graph</li>
  <li>🔎 Search</li>
</ul>

```sh title="Find tools for your work"
agenteng disciplines
agenteng tools --discipline memory
agenteng tools --discipline inference --kind runtime
agenteng tools --search 'Gemini CLI'
agenteng tool langgraph
```

[Explore filters, pagination and source attribution →](TOOLS.md)

## 🤖 Use AgentEng inside your agent { #connect-your-agent }

Add the installed executable to a client's local MCP configuration:

```json title="Local MCP configuration"
{
  "mcpServers": {
    "agenteng": {
      "command": "agenteng",
      "args": ["mcp"]
    }
  }
}
```

Try asking: **“Find the next London conference”**, **“List memory tools”** or
**“Show the public agenda for London.”**

Run `agenteng connect codex`, `agenteng connect claude-code` or
`agenteng connect cursor` for client-specific setup instructions.
[The connection guide](INTEGRATIONS.md) also covers hosted MCP, A2A and HTTP.

## 🔓 Built in the open { #built-in-the-open }

Improve the code, suggest a source-backed tool correction or help make the docs
clearer. AgentEng shares one typed interface across CLI, MCP and A2A. Optional
model synthesis and RLM are disabled by default; RLM is bounded to depth one and
one child or leaf delegation.

<div class="agenteng-footer-links" markdown>

[⭐ View on GitHub](https://github.com/SuperagenticAI/agenteng){ .md-button }
[🤝 Contribute](https://github.com/SuperagenticAI/agenteng/blob/main/CONTRIBUTING.md){ .md-button }
[🏗️ Architecture](ARCHITECTURE.md){ .md-button }

</div>

<!-- docs-ci-retrigger -->
