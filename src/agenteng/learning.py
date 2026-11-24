"""Offline Agent Engineering learning resources across all 14 disciplines.

Combines the website's 14-discipline taxonomy, modern production primitives,
published conference talks/recordings, attributed directory tools, further
reading, and links to upcoming Agent Engineering conferences. Zero model calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Request, Result
    from .service import Service

SITE = "https://agentengineering.world"

DISCIPLINE_GUIDES: dict[str, dict] = {
    "harness": {
        "primitives": ["Sandboxed Execution", "Tool Policies", "Verification Loops", "Guardrails"],
        "practices": [
            "Isolate tool calls and code execution in ephemeral sandboxes with explicit least-privilege policies.",
            "Treat the harness as the product: deterministic retries, bounded budgets and structured error recovery outperform prompt tweaks.",
        ],
        "protocols": ["MCP", "ACP"],
    },
    "context": {
        "primitives": ["Context Packing", "Compaction", "Prefix Caching", "Grounding"],
        "practices": [
            "Curate high-signal context per step instead of dumping raw tool output into the window.",
            "Structure stable system prefixes to maximize KV-cache hit rates across multi-turn agent trajectories.",
        ],
        "protocols": ["MCP", "WebMCP"],
    },
    "prompt": {
        "primitives": [
            "System Contracts",
            "Structured Outputs",
            "Schema Constraints",
            "Prompt Diffing",
        ],
        "practices": [
            "Version system prompts like code and enforce JSON schema outputs at tool boundaries.",
            "Pair every prompt change with regression evals over realistic, underspecified production tasks.",
        ],
        "protocols": ["MCP"],
    },
    "memory": {
        "primitives": ["Episodic State", "Semantic Recall", "Checkpoints", "Forgetting Policies"],
        "practices": [
            "Separate working trajectory state from durable cross-session memory.",
            "Build explicit retrieval, consolidation and expiry policies rather than relying on a bigger context window.",
        ],
        "protocols": ["MCP", "A2A 1.0"],
    },
    "eval": {
        "primitives": ["Trajectory Evals", "Atomic Rubrics", "Trace Replay", "CI Regression Gates"],
        "practices": [
            "Grade full agent trajectories on underspecified real-world tasks instead of static toy benchmarks.",
            "Use deterministic checks where possible and atomic rubrics with trace replay in CI.",
        ],
        "protocols": ["OpenTelemetry", "MCP"],
    },
    "inference": {
        "primitives": [
            "vLLM / SGLang",
            "KV-Cache Reuse",
            "Speculative Decoding",
            "Latency Budgeting",
        ],
        "practices": [
            "Optimize serving for multi-turn agent loops with prefix caching and batch scheduling.",
            "Match model size and quantization to step criticality to keep long-running agents economically viable.",
        ],
        "protocols": ["OpenAI-compatible HTTP"],
    },
    "loop": {
        "primitives": ["Control Flow", "Stopping Conditions", "Self-Correction", "Step Budgets"],
        "practices": [
            "Bound autonomous loops with explicit max steps, cost ceilings and verifier checkpoints.",
            "Design clear handoff and escalation paths when tool calls fail repeatedly.",
        ],
        "protocols": ["MCP", "A2A 1.0"],
    },
    "agentic": {
        "primitives": ["SDLC Automation", "PR & CI Agents", "Review Gates", "Human-in-the-Loop"],
        "practices": [
            "Embed verification gates (tests, linters, type checks) directly inside autonomous engineering workflows.",
            "Measure end-to-end merge quality and review overhead rather than raw generated lines.",
        ],
        "protocols": ["ACP", "MCP"],
    },
    "code": {
        "primitives": ["Coding Agents", "AST Patching", "Repo Maps", "Test Verification"],
        "practices": [
            "Give coding agents fast repository search, structured diffs and tight test feedback loops.",
            "Run untrusted generated code inside isolated containers with deterministic verification harnesses.",
        ],
        "protocols": ["ACP", "MCP"],
    },
    "protocol": {
        "primitives": ["MCP (Streamable HTTP & stdio)", "A2A 1.0 Agent Cards", "ACP", "A2UI"],
        "practices": [
            "Expose callable, typed tool contracts (MCP, CLI, A2A) so agents prefer structured APIs over fragile UI scraping.",
            "Publish /.well-known/agent-card.json and /llms.txt so autonomous agents and LLMs discover capabilities accurately.",
        ],
        "protocols": ["MCP", "A2A 1.0", "ACP", "A2UI", "llms.txt"],
    },
    "graph": {
        "primitives": [
            "Knowledge Graphs",
            "State Machines",
            "DAG Orchestration",
            "Multi-Hop Retrieval",
        ],
        "practices": [
            "Model entity relationships and multi-step execution state explicitly as graphs for auditable traversal.",
            "Combine graph traversal with vector search when agents must reason across connected records.",
        ],
        "protocols": ["MCP"],
    },
    "search": {
        "primitives": ["Hybrid Retrieval", "Query Planning", "Phased Ranking", "Rerankers"],
        "practices": [
            "Combine lexical, vector and structured filters with multi-phase ranking for high-precision grounding.",
            "Let agents iteratively refine queries based on retrieval confidence rather than single-shot RAG.",
        ],
        "protocols": ["MCP"],
    },
    "factory": {
        "primitives": [
            "Spec-to-Code Pipelines",
            "Multi-Agent Orchestration",
            "Merge Queues",
            "QA Agents",
        ],
        "practices": [
            "Design software factories around explicit specs, deterministic test suites and automated review gates.",
            "Optimize harness latency and parallel worker isolation so multi-agent pipelines stay maintainable.",
        ],
        "protocols": ["ACP", "MCP", "A2A 1.0"],
    },
    "decision": {
        "primitives": [
            "Planning Under Uncertainty",
            "Policy Routing",
            "Confidence Thresholds",
            "Audit Logs",
        ],
        "practices": [
            "Separate high-stakes policy decisions from free-form generation using explicit guardrails and audit trails.",
            "Log inputs, retrieved context and justification metadata for every consequential agent action.",
        ],
        "protocols": ["A2A 1.0", "MCP"],
    },
}


def _conferences_cta(service: Service) -> list[dict]:
    upcoming = []
    for event_id in ("agenteng-london-2027", "agenteng-sf-2027"):
        ev = service.events.get(event_id)
        if ev:
            upcoming.append(
                {
                    "id": ev.id,
                    "title": ev.title,
                    "city": ev.city,
                    "date": ev.date,
                    "venue": ev.venue,
                    "status": ev.registration_status or "announced",
                    "url": str(ev.page_url) if ev.page_url else SITE,
                }
            )
    return upcoming


def _matching_talks(service: Service, discipline_id: str, short: str) -> list[dict]:
    needle = short.casefold()
    matches = []
    for talk in service.catalogue.talks:
        if talk.kind == "a2a":
            continue
        haystack = " ".join([talk.title, talk.summary or "", " ".join(talk.topics)]).casefold()
        if needle in haystack or discipline_id in haystack:
            matches.append(
                {
                    "slug": talk.slug,
                    "title": talk.title,
                    "speaker": talk.speaker.name if talk.speaker else None,
                    "company": talk.speaker.company if talk.speaker else None,
                    "event": talk.event_name,
                    "url": str(talk.url),
                    "youtube_url": (
                        f"https://www.youtube.com/watch?v={talk.youtube_id}"
                        if talk.youtube_id
                        else None
                    ),
                }
            )
    return matches[:6]


def _sample_tools(service: Service, discipline_id: str) -> tuple[int, list[dict]]:
    matched = [
        t
        for t in service.tool_directory.tools
        if t.status == "listed" and discipline_id in t.disciplines
    ]
    matched.sort(key=lambda t: (t.name.casefold(), t.id))
    sample = [
        {
            "id": t.id,
            "name": t.name,
            "kind": t.kind,
            "url": str(t.website_url or t.repository_url),
        }
        for t in matched[:8]
    ]
    return len(matched), sample


def learn(service: Service, request: Request) -> Result:
    """Return Agent Engineering learning resources for all 14 disciplines or one discipline."""
    target = (request.discipline or request.topic or request.query or "").strip().casefold()
    site_disciplines = {d.id: d for d in service.catalogue.disciplines}
    aliases = {
        "evaluation": "eval",
        "evals": "eval",
        "coding": "code",
        "protocols": "protocol",
        "mcp": "protocol",
        "a2a": "protocol",
        "acp": "protocol",
        "factories": "factory",
        "decisions": "decision",
        "harnesses": "harness",
        "prompts": "prompt",
        "loops": "loop",
        "graphs": "graph",
        "retrieval": "search",
    }
    resolved = aliases.get(target, target)
    conferences = _conferences_cta(service)
    hq_reading = (
        [r.model_dump(mode="json") for r in service.catalogue.hq.further_reading]
        if service.catalogue.hq
        else []
    )
    source_ids = [
        s
        for s in ("hq", "about", "hq-further-reading", "agenteng-london-2027", "agenteng-sf-2027")
        if s in service.sources
    ]

    if resolved and resolved in site_disciplines:
        disc = site_disciplines[resolved]
        guide = DISCIPLINE_GUIDES.get(resolved, {})
        talks = _matching_talks(service, disc.id, disc.short)
        tool_count, tools = _sample_tools(service, disc.id)
        data = {
            "discipline": {
                "id": disc.id,
                "title": disc.title,
                "description": disc.description,
                "primitives": guide.get("primitives", []),
                "practices": guide.get("practices", []),
                "protocols": guide.get("protocols", []),
                "cli_tools_command": f"agenteng tools --discipline {disc.id}",
            },
            "talks": talks,
            "tool_count": tool_count,
            "sample_tools": tools,
            "further_reading": hq_reading[:5],
            "upcoming_conferences": conferences,
            "website": SITE,
            "agent_endpoints": {
                "llms_txt": f"{SITE}/llms.txt",
                "mcp": f"{service.settings.public_url}/mcp/",
                "a2a_card": f"{service.settings.public_url}/.well-known/agent-card.json",
            },
        }
        return service.result(
            f"{disc.title}: {disc.description} "
            f"{len(talks)} matching talk(s), {tool_count} tool listing(s). "
            f"Explore live at Agent Engineering London 2027 ({SITE}/london-2027).",
            data,
            source_ids,
        )

    if target and resolved not in site_disciplines:
        return service.result(
            f"Unknown discipline {target!r}. Choose one of: {', '.join(site_disciplines)}.",
            {"disciplines": list(site_disciplines), "upcoming_conferences": conferences},
            source_ids,
            status="not_found",
        )

    items = []
    for disc in service.catalogue.disciplines:
        guide = DISCIPLINE_GUIDES.get(disc.id, {})
        tool_count, _ = _sample_tools(service, disc.id)
        items.append(
            {
                "id": disc.id,
                "title": disc.title,
                "description": disc.description,
                "primitives": guide.get("primitives", []),
                "protocols": guide.get("protocols", []),
                "tool_count": tool_count,
                "command": f"agenteng learn {disc.id}",
            }
        )
    data = {
        "title": "Agent Engineering Learning Hub (14 Disciplines)",
        "summary": (
            "Production practices, conference talks, open-source tools and open protocols "
            "(MCP, A2A 1.0, ACP) curated by Agent Engineering HQ."
        ),
        "disciplines": items,
        "further_reading": hq_reading,
        "upcoming_conferences": conferences,
        "website": SITE,
        "gallery_url": f"{SITE}/gallery",
    }
    return service.result(
        f"Agent Engineering Learning Hub: {len(items)} disciplines, {len(service.catalogue.talks)} talks/videos, "
        f"{len(service.tool_directory.tools)} tools. Run `agenteng learn <discipline>` (e.g. `agenteng learn harness`) "
        f"or explore London 2027 at {SITE}/london-2027.",
        data,
        source_ids,
    )
