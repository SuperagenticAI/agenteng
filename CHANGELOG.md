# Changelog

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
