# 🧰 Explore the tool directory

Browse tools, models and infrastructure through the CLI, the existing single MCP tool, A2A or HTTP. Listing, searching and reading details work offline without a provider key or model calls.

The initial snapshot covers 461 SuperRadar source entries normalized into 456 listings: six duplicate records are merged with aliases, and Graphiti is separated from Zep with explicit provenance. There is no per-discipline quota. Four entries marked Hold or deprecated upstream remain available outside default browse results.

## CLI

```sh
agenteng disciplines
agenteng tools --discipline memory
agenteng tools --discipline inference --kind runtime
agenteng tools --category 'Agentic CLI'
agenteng tools --search 'Gemini CLI'
agenteng tools --limit 100 --offset 100 --status all
agenteng tool langgraph
agenteng tool letta-memory
agenteng --json tools --discipline code --limit 25
```

Global options such as `--json` and `--remote` go before the command. Text output shows names, IDs, kinds, discipline tags and links; JSON preserves the complete shared result. Search matches names, aliases, identifiers and category tags; all search words must match. Results are alphabetical. Repeat the same filters with `next_offset` until null to retrieve every match. `limit` is 1–100 and bounds each response, not directory coverage.

`--status listed` is the default. `hold`, `deprecated` and `all` expose attributed upstream status, not independently established maintenance or suitability.

## Disciplines and filters

The twelve IDs match the conference website: `prompt`, `context`, `harness`, `eval`, `memory`, `inference`, `loop`, `agentic`, `code`, `protocol`, `graph`, `search`. One canonical product can appear in multiple disciplines, so counts overlap. Source categories offer finer filters such as Agentic CLI, Sandbox, Memory Systems and Vector Stores. Kinds distinguish protocols, frameworks, CLIs, IDEs, models, databases, runtimes, hosting, registries, connectors and other families. `agenteng --json disciplines` lists available categories and kinds.

Tags describe discovery categories, not delivered AgentEng adapters or vendor integrations.

## MCP, A2A and HTTP

Call the existing MCP tool named `agenteng` with:

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

Other requests are `{"operation":"disciplines"}` and `{"operation":"tool","tool_id":"langgraph"}`. A2A JSON data parts and `POST /v1/query` use the inner request object unchanged. The A2A card advertises the `agenteng-tools` skill. Plain questions such as “List inference tools” route deterministically; typed requests provide exact control over filters and pagination. Event search remains separate. See [connection instructions](INTEGRATIONS.md).

`tools` accepts `query`, `discipline`, `kind`, `category`, `limit`, `offset` and `tool_status`. `tool` requires `tool_id` and resolves merged source IDs. Invalid filters return validation errors, empty searches return successful empty pages, and unknown detail IDs return `not_found`. Directory requests reject event filters and model engines.

Self-hosting provides crawlable `/tools`, `/tools/TOOL_ID` and the full `/tools.json` export, linked from the agent guide and sitemap. Query operations provide bounded pages. Installing the package does not publish endpoints or register the agent in a marketplace.

## Attribution and corrections

Names and public links come from the pinned [SuperRadar snapshot](https://github.com/SuperagenticAI/superradar/blob/47606d3ffe2b730f5c45401374d1bcaab3569e14/superradar-tools.json), updated October 4, 2026. Results include its revision, content hash and update time, plus the normalized directory version. Directory freshness is independent of the event catalogue.

`source_listed` means metadata is attributed to that catalogue, not independently verified against every vendor. AgentEng supplies discipline/kind classifications. The importer omits promotional descriptions, adoption rings, rankings, star counts, logos and license/deployment claims. Listing implies no sponsorship, endorsement, installation, integration or claim of popularity. Linked products and assets retain their own rights; AgentEng's software license does not relicense them.

Suggest additions, corrected names/links, duplicate merges or discipline changes with primary public references. Disclose relevant affiliations. Maintainers review suggestions without promising inclusion, a response or a deadline. Keep private proposals and contact details out of public reports.

## Maintainer refresh

Import a local checkout of the allowlisted source. No public request fetches mutable remote JSON or runs upstream scripts. Confirm the full commit SHA and source rights, review changed names/links/tags, and write factual summaries independently if adding them. From an installed source checkout:

```sh
uv run --frozen python scripts/import-tools.py /path/to/superradar-tools.json --commit FULL_40_CHARACTER_COMMIT_SHA
```

The importer bounds input, validates URLs, IDs, references and known categories, preserves aliases/provenance, then atomically replaces the bundle. Validation failure leaves the previous bundle intact. Unknown source categories require an explicit classification update. Review the diff and run release checks before distributing a refreshed version; there is no background sync.
