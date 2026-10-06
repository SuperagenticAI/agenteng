# Changelog

## Unreleased

### Added

- Experimental `ae code` ACP client (optional `agenteng[acp]` extra): launch an Agent Client Protocol coding agent (Claude Code and Codex adapters, Gemini CLI, Copilot, Cursor, OpenCode, goose, Qwen Code, fast-agent, Kimi, or any `--agent-command`), attach the AgentEng MCP server to the session, add talk, event, speaker or tool records named in the prompt, and stream messages, tool calls and plans as rich output or `--json` events. Permission requests are always asked in the terminal and rejected without one; nothing is auto-approved. `ae code --list` shows which agents are on `PATH`. See `docs/ACP.md`.
- `ae code` chat mode: with no prompt in a terminal, or with `--chat`, keep one ACP session open across turns. Ctrl-C sends `session/cancel` (also at a permission prompt), Ctrl-D or `/exit` ends the chat, and `/help`, `/context ID` and `/agent` are available. `--chat` with piped stdin runs one turn per line; `--json` alone stays single-shot.
- "Code with an agent (ACP, experimental)" in the `ae` menu: pick an installed agent (or see install hints) and optionally a talk, then chat.
- `ae code` renders ACP diff content as coloured unified diffs in permission prompts and tool-call streams, truncated after 40 lines with a "view the full diff" option; `--json` permission events add a `diffs` summary.

### Fixed

- `ae talk SESSION_ID` now resolves exact session IDs such as `agenteng-london-2026-14` instead of a text-search match.

### Changed

- Default the Cloud Build `_PUBLIC_URL` substitution to `https://a2a.agentengineering.world`, so tag deploys keep the custom domain instead of resetting `AGENTENG_PUBLIC_URL` to the generated `run.app` URL (which made the custom domain return `400 Invalid host header`). Forks can set `_PUBLIC_URL` empty or to another origin on their trigger.
- Document that only the `push-new-tag` Cloud Build trigger should deploy; disable the Cloud Run wizard branch trigger.
- Add console and `gcloud` steps for disabling the Cloud Run wizard branch trigger to the deployment guide.

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
