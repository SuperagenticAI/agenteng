# Changelog

## Unreleased

### Changed

- `docs/COMMANDS.md`: a full command reference for every visible command and subcommand, with options, examples, the Result JSON fields, the commands that print other output, and exit codes. A test keeps it complete.
- Every visible option now has `--help` text, and commands with arguments explain them.
- User-facing copy says `agenteng` instead of `ae` (about `connect_commands`, the bingo `command` and card footer, `now --screen` help, the save error, the live board footer, `agenteng code` messages and the installer's next steps). `ae` remains the short developer alias.
- Empty but valid results (no bookmarks in `my-agenda`, nothing on in `now`, zero `search` hits, an empty `talks --search`) now exit `0` in the CLI. Unknown IDs still exit `1`. The Result JSON is unchanged, so MCP, A2A and HTTP clients see the same `status`.
- Docs: installer environment variables, `AGENTENG_OUTPUT` and `AGENTENG_CONFIG_DIR` in `.env.example`, `agenteng` in doc examples, and the bingo skill text now says the card is in `data` with printable formats in `artifact`.

## 0.0.7 - 2026-10-06

### Added

- `agenteng live` (also `agenteng now --screen`): a full-screen, auto-refreshing now/next board for venue screens with the event title, venue and track, a large clock, the current talk with a progress bar, next up and later sessions. `--event`, `--refresh SECONDS`, `--at` (ISO time or `HH:MM` on the event day; the clock runs forward from it) and `--once`. Piped or with `--json` it prints one Result JSON snapshot. New `live` operation for MCP, A2A and HTTP; `now` and `next` also accept `at`.
- `agenteng bingo`: talk bingo cards (5x5 with a free centre, or 4x4) built only from terms that appear in the event's published talk titles, abstracts and agenda, plus the speakers' published disciplines. `--seed` makes cards reproducible and is printed on every card; `--format text|svg|html` and `--output` give printable cards; `--play` marks squares in the terminal and calls bingo. New `bingo` operation; local only, nothing is sent.
- `agenteng about` (organiser, conference chair, links and how to connect agents: install line, remote MCP URL, agent card) and `agenteng hq [manifesto|mindset|reading]` (Agent Engineering HQ content). Both come from published website data, exported by `scripts/export-website.mjs` into new `about` and `hq` catalogue records with source evidence.
- Website command wording: city slugs (`--city san-francisco`, `sf`, `london`) for every city filter including MCP and A2A requests, `events [CITY]`, `events --next` / `--history` / `--previous`, hidden `--london` / `--sf` shortcuts, city names as event IDs (`agenteng agenda london`), `agenteng --list-disciplines`, `agenteng --themes`, `agenteng --list-cities`, `agenteng --info`, `agenteng inspect --speaker SLUG` and `agenteng whoami --chair`. Existing commands and JSON are unchanged. The short `ae` alias works the same for local developer convenience; website copy always shows `agenteng`.
- `docs/SITE-SYNC.md` and `tests/fixtures/site_commands.tsv`: all 45 commands shown on agentengineering.world with their status; CI runs every row. 17 run after this change (3 in 0.0.6).
- Menu entries for the live board, talk bingo, about and Agent Engineering HQ; an `agenteng-event-day` A2A skill.

### Fixed

- The remote MCP server reports the agenteng version in `serverInfo` instead of the MCP SDK version.
- `--remote` requests omit default fields so a newer CLI keeps working against an older server.
- Privacy: a new config directory and `acp-logs/` are created `0700`; bookmarks are written `0600` from the start (atomic replace). `agenteng serve` no longer writes per-request access lines (client address, path) unless `--access-log` is passed. New privacy section in `docs/DATA.md`.
- README and docs: `agenteng --json events` (global options go before the command) and a working `--catalogue` example with export instructions.

### Documentation

- Site sync guide: conference website command examples always use `agenteng`, never the `ae` alias.

## 0.0.6 - 2026-10-06

### Added

- Experimental `ae code` ACP client in the new optional `agenteng[acp]` extra (official `agent-client-protocol` Python SDK). It launches an Agent Client Protocol coding agent (Claude Code and Codex adapters, Gemini CLI, Copilot, Cursor, OpenCode, goose, Qwen Code, fast-agent, Kimi, or any `--agent-command`), attaches the AgentEng MCP server to the session, adds talk, event, speaker or tool records named in the prompt, and streams messages, tool calls and plans as rich output or `--json` events. `ae code --list` shows which agents are on `PATH`. Every permission request is asked in the terminal and rejected without one; nothing is auto-approved. See `docs/ACP.md`.
- `ae code` chat mode: with no prompt in a terminal, or with `--chat`, one ACP session stays open across turns. Ctrl-C sends `session/cancel` (also at a permission prompt), Ctrl-D or `/exit` ends the chat, and `/help`, `/context ID` and `/agent` are available. `--chat` with piped stdin runs one turn per line; `--json` alone stays single-shot.
- "Code with an agent (ACP, experimental)" in the `ae` menu: pick an installed agent (or see install hints) and optionally a talk, then chat.
- Diffs in `ae code`: ACP diff content renders as coloured unified diffs in permission prompts and tool-call streams, truncated after 40 lines with a "view the full diff" option; `--json` permission events add a `diffs` summary.

### Fixed

- `ae talk SESSION_ID` resolves exact session IDs such as `agenteng-london-2026-14` instead of returning a text-search match.

### Changed

- Default the Cloud Build `_PUBLIC_URL` substitution to `https://a2a.agentengineering.world`, so tag deploys keep the custom domain instead of resetting `AGENTENG_PUBLIC_URL` to the generated `run.app` URL (which made the custom domain return `400 Invalid host header`). Forks can set `_PUBLIC_URL` empty or to another origin on their trigger.

### Documentation

- Only the `push-new-tag` Cloud Build trigger should deploy. The deployment guide now has console and `gcloud` steps to disable the Cloud Run wizard branch trigger.

## 0.0.5 - 2026-10-05

### Added

- Native `ae` console-script alias alongside `agenteng`.
- Rich human-readable TTY output (cards and tables), with auto JSON for agents via `--json`, `AGENTENG_OUTPUT=json`, or piped stdout.
- Interactive `ae` / `agenteng` menu (questionary) for browsing events, search, tools, proposals and agent connection.
- Full website content parity: talk abstracts, speaker bios and links, FAQ, venue, sponsors, code of conduct, and program themes.
- Local engagement helpers: `now` / `next`, `save` / `unsave` / `my-agenda` bookmarks, and `agenda --format ics` export.

## 0.0.4

### Changed

- Replace the wheel-mirror installer with a branded, SuperQode-style AgentEng installer: an animated purple and blue terminal intro, then `uv tool install` of the latest `agenteng` from PyPI with the `server` extra (MCP and A2A included). It bootstraps uv when missing, falls back to a user virtualenv with pip, never uses sudo, and upgrades on re-run. `AGENTENG_VERSION` and `AGENTENG_EXTRAS` override the defaults.
- Advertise the one-line installer at `https://a2a.agentengineering.world/install.sh`, which serves the script as plain text, until the conference site allows non-browser access to `/install.sh`.
- Release metadata checks now require the installer to stay version-free, install from PyPI and never download wheels from the website `/releases/` mirror.

### Documentation

- Mark the hosted A2A agent live at `https://a2a.agentengineering.world` and list its public endpoints.
- Add "Invalid host header" troubleshooting to the deployment guide and explain why `_PUBLIC_URL` must stay set on the Cloud Build trigger.

## 0.0.3

### Fixed

- Install Git in the Cloud Build verification image so the Git-ignore release test can run; trust only the shared `/workspace` checkout across builder containers.
- Include Git error output when the ignore-rule test fails, instead of reporting only mismatched paths.

## 0.0.2

### Changed

- Reject invalid public URLs at startup with a clear configuration error, instead of failing requests in host-validation middleware.

- Default the Cloud Run service name to `agenteng`; document the trigger override for the published `v0.0.1` tag.

## 0.0.1

### Changed

- Align the initial package and installer release to `0.0.1`; derive the HTTP API version from package metadata and show the expected tag in release-check failures.

- Use `agenteng` as the Python package distribution name, matching the CLI and module.

### Added

- Tag-triggered Cloud Build deployment with release validation, generated Cloud Run URL setup, dedicated runtime identity, live MCP/A2A checks and a console setup guide.

- Minimal Markdown documentation with the official logo and favicon, MkDocs Material preview and GitHub Pages publishing.

- Version-tag PyPI publishing and GitHub releases using verified CI artifacts, with release metadata validation and existing-tag retry support.

- Offline tool directory: 456 listings covering 461 attributed source entries across twelve disciplines; CLI/MCP/A2A list, search, filters, aliases and pagination, crawlable pages/feed, and validated maintainer import.

- Public event catalogue with source attribution, snapshot freshness and timezone-aware event states.
- `agenteng` CLI for events, speakers, agendas, published ticket terms, recordings, search and session/calendar planning.
- One-tool MCP server over stdio and Streamable HTTP; A2A 1.0 discovery and JSON-RPC adapter.
- Optional ordinary synthesis and Monty RLM, disabled by default, with one child or leaf delegation and depth one.
- Versioned wheel installer, release staging, Cloud Run configuration and local/CI verification.
- Read-only participation guidance for talk and event ideas, with explicit organizer discretion.
- Apache-2.0 license, contributor/security/community documentation and GitHub issue forms.
- London/San Francisco discovery, source-backed invited-programme policy, crawlable event pages/JSON-LD, event feeds and agent/crawler guides.
- Codex, Claude Code, Cursor and generic MCP connection instructions plus a remote stdio bridge.
- Guided offline drafts, completeness checks and private-permission JSON/Markdown export.
- Opt-in single-organizer SQLite intake pilot: participant credentials, confirmed previews, durable receipts, scoped status/history, withdrawal, retention and local organizer review.

Hosted intake remains disabled by default and requires persistent private storage; the supplied Cloud Run configuration serves public discovery/drafting.
