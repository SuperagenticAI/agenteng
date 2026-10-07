# 🏗️ How AgentEng works

One public catalogue, one request contract and three ways to connect: CLI, MCP
and A2A. Public lookup uses no model calls. Optional inference must be explicitly enabled.
Personal agendas, bookmarks, proposal drafts and private intake are unsupported.

## Public catalogue and lookup

The CLI, MCP and A2A adapters share the same validated `Request`, `Result` and catalogue service. Public content is bundled in the package for offline lookups. The exporter reads an allowlist of TypeScript literals with the website's TypeScript parser, without executing its React pages or querying private databases.

`lookup` and `auto` use no server-side model calls. Search ranks literal public-source matches. Common event, agenda and ticket questions use deterministic routing. Agenda topic filtering matches published session text. Ticket responses describe published price windows and link to the registration provider for availability and approval.

## Protocols and HTTP service

MCP exposes one typed `agenteng` tool over stdio or stateless Streamable HTTP. The default tool is read-only. When an operator enables optional inference, tool annotations reflect its external provider interaction. A2A 1.0 uses official SDK routes, advertises no streaming or push notifications and returns immediate messages. Named HTTP/MCP routes are registered before A2A tenant routes.

The HTTP server checks allowed hosts and origins, caps request bodies at 64 KiB and limits writes to 300 requests per minute per process. Operators need edge quotas for limits spanning replicas. The default process retains no durable conversation, attendee database or proposal inbox. Crawlable HTML, JSON-LD, event feeds and agent/crawler guides describe source-backed London/San Francisco events. Search aliases identify the conference and organizer without changing published event titles.

## Optional synthesis and bounded RLM

Optional `standard` synthesis performs one provider request. Optional RLM keeps source text outside its initial model prompt and exposes one model-visible `run_code` tool in a persistent Monty session. The root can make one child-session OR one leaf delegation total. A child cannot delegate or widen its evidence scope; failed admission consumes the allowance. All calls share conservative token reservation, model-call and deadline limits. Monty limits code size, memory, execution duration and suspensions. Model-generated code has no host filesystem, network or environment callbacks.

Citation validation checks that source IDs are in scope; it cannot prove the truth of generated prose. Standard and RLM engines require operator authorization and explicit activation. Public chat has a separate activation flag, a restricted public lookup loop, bounded history, per-process admission/cooldown, and automatic lookup fallback. They have scripted-provider/sandbox coverage, but live-provider factual quality and billing are not yet validated. Cancelling a request prevents subsequent calls; a request already sent to a provider can still incur billing. The public container omits the RLM runtime and defaults all inference off. Operators can explicitly enable public chat with provider settings; this does not enable private operations or operator engines.

## Verification

Tests exercise catalogue contracts, price transitions, timezones, calendar formatting, HTTP/A2A dispatch, real MCP stdio/HTTP clients, operator gating, sandbox limits, shared delegation budgets and installer checks. A separate core-only environment verifies the built wheel without the optional protocol/model packages.

## Tool-directory snapshots

The tool directory is a separate validated, bundled snapshot with independent source/version/freshness metadata. `disciplines`, `tools` and `tool` share the existing service and all adapters. Bounded alphabetical pages expose total counts and next offsets. Source IDs resolve merged records; derived Graphiti provenance does not shadow Zep. A maintainer-only importer reads bounded local JSON, validates the complete result and atomically replaces the bundle on success. Runtime requests never refresh it. Crawlable tool pages and the full JSON feed use the same records.
