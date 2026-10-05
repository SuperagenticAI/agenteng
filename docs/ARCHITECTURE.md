# 🏗️ How AgentEng works

One public catalogue, one request contract and three ways to connect: CLI, MCP
and A2A. Lookup and drafting use no model calls. Optional inference and private
intake are separate capabilities that an operator must explicitly enable.

## Public catalogue and lookup

The CLI, MCP and A2A adapters share the same validated `Request`, `Result` and catalogue service. Public content is bundled in the package for offline lookups. The exporter reads an allowlist of TypeScript literals with the website's TypeScript parser, without executing its React pages or querying private databases.

`lookup` and `auto` use no server-side model calls. Search ranks literal public-source matches. Common event, agenda and ticket questions use deterministic routing. Topic-based planning matches published session text; it is not a personalized attendance guarantee. Ticket responses describe published price windows and link to the registration provider for availability and approval.

## Protocols and HTTP service

MCP exposes one typed `agenteng` tool over stdio or stateless Streamable HTTP. The default tool is read-only. When an operator enables optional inference, tool annotations reflect its external provider interaction. A2A 1.0 uses official SDK routes, advertises no streaming or push notifications and returns immediate messages. Named HTTP/MCP routes are registered before A2A tenant routes.

The HTTP server checks allowed hosts and origins, caps request bodies at 64 KiB and limits writes to 300 requests per minute per process. Operators need edge quotas for limits spanning replicas. The default process retains no durable conversation, attendee database or proposal inbox. Crawlable HTML, JSON-LD, event feeds and agent/crawler guides describe source-backed London/San Francisco events. Search aliases identify the conference and organizer without changing published event titles.

## Drafting and private intake

Draft contracts are shared across all transports, with no model or external submission effects. Optional private intake uses a separate SQLite store on an operator-managed persistent volume. Per-participant credentials are hashed, distinct from inference credentials and separate from local organizer filesystem access. Prepared previews bind the owner, canonical draft and current policy; submission checks call state in the transaction and returns a receipt after commit. Retry, status and withdrawal remain owner-scoped. Withdrawal erases active content, while retention removes records/history. HTTP validation errors omit input and POST responses are not cacheable. No private data is added to the public catalogue. See [pilot requirements](PARTICIPATION.md).

Enabling intake changes the single broad MCP tool to advertise writes and destructive withdrawal. A2A advertises the participant bearer scheme on the private skill. The remote stdio bridge conservatively advertises possible writes because remote configuration may differ. Local organizer review commands have no remote administration route. Neither receipt nor acceptance automatically publishes or schedules a talk.

## Optional synthesis and bounded RLM

Optional `standard` synthesis performs one provider request. Optional RLM keeps source text outside its initial model prompt and exposes one model-visible `run_code` tool in a persistent Monty session. The root can make one child-session OR one leaf delegation total. A child cannot delegate or widen its evidence scope; failed admission consumes the allowance. All calls share conservative token reservation, model-call and deadline limits. Monty limits code size, memory, execution duration and suspensions. Model-generated code has no host filesystem, network or environment callbacks.

Citation validation checks that source IDs are in scope; it cannot prove the truth of generated prose. Optional engines require operator authorization and explicit activation. They have scripted-provider/sandbox coverage, but live-provider factual quality and billing are not yet validated. Cancelling a request prevents subsequent calls; a request already sent to a provider can still incur billing. The public container omits the RLM runtime and disables inference.

## Verification

Tests exercise catalogue contracts, price transitions, timezones, calendar formatting, HTTP/A2A dispatch, real MCP stdio/HTTP clients, operator gating, sandbox limits, shared delegation budgets and installer checks. A separate core-only environment verifies the built wheel without the optional protocol/model packages.

## Tool-directory snapshots

The tool directory is a separate validated, bundled snapshot with independent source/version/freshness metadata. `disciplines`, `tools` and `tool` share the existing service and all adapters. Bounded alphabetical pages expose total counts and next offsets. Source IDs resolve merged records; derived Graphiti provenance does not shadow Zep. A maintainer-only importer reads bounded local JSON, validates the complete result and atomically replaces the bundle on success. Runtime requests never refresh it. Crawlable tool pages and the full JSON feed use the same records.
