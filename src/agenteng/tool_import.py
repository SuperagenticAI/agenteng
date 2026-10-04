"""Maintainer-only normalization of a pinned, local SuperRadar JSON snapshot.

Only names, identifiers and public links are imported. Descriptions, images,
rankings, popularity flags and source license/deployment claims are omitted.
This module never downloads content or executes source code.
"""

import hashlib
import json
import re

from .tool_directory import DirectorySource, Tool, ToolDirectory

# AgentEng classifications, independent of the source's Adopt/Trial/Assess rings.
CATEGORIES = {
    "Sandbox": (["harness"], "sandbox"),
    "Agent Frameworks": (["harness", "loop"], "framework"),
    "Connectors": (["protocol", "context"], "connector"),
    "Agentic CLI": (["code", "agentic"], "cli"),
    "Multi-Agent Orchestration": (["loop"], "framework"),
    "Agentic IDE": (["code", "agentic"], "ide"),
    "Memory Systems": (["memory", "context"], "database"),
    "Foundational Models": (["inference"], "model"),
    "Inference Engines": (["inference"], "runtime"),
    "Security": (["harness"], "security"),
    "Coding Models": (["code", "inference"], "model"),
    "Observability": (["eval"], "observability"),
    "Coding Agents": (["code", "agentic"], "agent"),
    "Web, Browser & API": (["context"], "app"),
    "Agent Protocols": (["protocol"], "protocol"),
    "Code Review": (["code", "eval"], "evaluation"),
    "Model Serving": (["inference"], "hosting"),
    "Search": (["search"], "search"),
    "Wiki": (["context", "code"], "documentation"),
    "Model Hosts": (["inference"], "hosting"),
    "Vibe Code (Browser)": (["code", "agentic"], "app"),
    "Extensions": (["code"], "extension"),
    "Sovereign AI": (["inference"], "model"),
    "Vector Stores": (["context", "search"], "database"),
    "Embedding Model Providers": (["context", "search"], "embedding"),
    "Knowledge Graphs": (["graph"], "database"),
    "Evaluation": (["eval"], "evaluation"),
}
OVERRIDES = {
    "baml": (["prompt", "code"], "framework"),
    "dspy": (["prompt", "loop"], "framework"),
    "gepa": (["prompt", "eval"], "evaluation"),
    "langfuse": (["prompt", "eval"], "observability"),
    "langsmith": (["prompt", "eval"], "observability"),
    "braintrust": (["prompt", "eval"], "evaluation"),
    "promptfoo": (["prompt", "eval"], "evaluation"),
    "zep": (["memory", "context"], "database"),
    "cognee": (["memory", "context", "graph"], "framework"),
    "letta": (["memory", "harness", "loop"], "framework"),
    "langmem": (["memory", "context"], "framework"),
    "llamaindex": (["context", "search", "harness"], "framework"),
    "cocoindex": (["context", "search"], "framework"),
    "firecrawl": (["context", "search"], "connector"),
    "fastmcp": (["protocol"], "framework"),
    "laravel-mcp": (["protocol"], "framework"),
    "smithery": (["protocol"], "registry"),
    "glama-mcp": (["protocol"], "registry"),
    "mcpjam": (["protocol", "eval"], "evaluation"),
    "cursor-projects": (["agentic", "code"], "app"),
    "github-agent-hq": (["agentic", "code"], "app"),
    "gitlab-duo-agent-platform": (["agentic", "code"], "app"),
    "mistral-studio-skills": (["prompt", "eval"], "observability"),
    "browser-use": (["harness", "context"], "browser"),
    "browserbase": (["harness", "context"], "browser"),
    "stagehand": (["harness", "context"], "browser"),
}
# Explicit duplicates only: do not merge similarly named products automatically.
MERGES = {
    "letta-memory": "letta",
    "z-ai": "glm-5",
    "deepseek-v3-2": "deepseek",
    "claude": "opus",
    "opus-4-6": "fable-5",
    "mimo-v2-flash-coding": "mimo-v2-flash",
}
NAMES = {"cursor": "Cursor", "amp-code": "Amp", "mem0": "Mem0"}
ALIASES = {
    "gemini-cli": ["Gemini CLI", "Antigravity CLI"],
    "windsurf": ["Windsurf", "Devin Desktop"],
    "google-antigravity": ["Antigravity"],
    "letta": ["Letta Memory"],
    "openai-agentsdk": ["OpenAI Agents SDK", "openai-agents-python"],
}


def normalize_snapshot(content: bytes, commit: str) -> ToolDirectory:
    if len(content) > 8 * 1024 * 1024:
        raise ValueError("Source snapshot exceeds 8 MiB")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Supply a full lowercase source commit SHA")
    source = json.loads(content)
    entries = source["tools"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 10000:
        raise ValueError("Invalid source entry count")
    if len({t["id"] for t in entries}) != len(entries):
        raise ValueError("Duplicate source tool IDs")
    ids = {t["id"] for t in entries}
    repositories = source.get("toolRepositories", {})
    rows = {}
    for entry in entries:
        sid = entry["id"]
        # Validate IDs before incorporating them into lookup aliases.
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", sid) or len(sid) > 128:
            raise ValueError("Invalid source ID")
        tid = MERGES.get(sid, sid)
        if tid not in ids:
            tid = sid
        category = entry["category"]
        if category not in CATEGORIES:
            raise ValueError(f"Unreviewed source category: {category}")
        disciplines, kind = OVERRIDES.get(sid, CATEGORIES[category])
        repo = repositories.get(sid, {})
        deprecated = entry.get("deprecated", False)
        if not isinstance(deprecated, bool):
            raise ValueError("Deprecated flag must be boolean")
        status = (
            "deprecated" if deprecated else "hold" if entry.get("state") == "Hold" else "listed"
        )
        candidate = Tool(
            id=tid,
            name=NAMES.get(tid, entry["name"]),
            source_ids=[sid],
            aliases=sorted(set([entry["name"], *ALIASES.get(tid, [])])),
            categories=[category],
            disciplines=disciplines,
            kind=kind,
            website_url=entry.get("websiteUrl"),
            repository_url=entry.get("githubUrl") or repo.get("repo"),
            docs_url=repo.get("docs"),
            status=status,
        )
        if tid not in rows:
            rows[tid] = candidate
        else:
            previous = rows[tid]
            # Prefer the explicit canonical record, retaining all source identities.
            primary = candidate if sid == tid else previous
            secondary = previous if sid == tid else candidate
            combined = primary.model_dump()
            for key in ["source_ids", "aliases", "categories", "disciplines"]:
                combined[key] = sorted(set(getattr(primary, key) + getattr(secondary, key)))
            for key in ["website_url", "repository_url", "docs_url"]:
                combined[key] = getattr(primary, key) or getattr(secondary, key)
            rows[tid] = Tool.model_validate(combined)
    # Graphiti and Zep have different public identities. The source's Zep record
    # links to Graphiti; derive a separate attributed listing instead of conflating them.
    if (
        "graphiti" not in rows
        and "zep" in rows
        and str(rows["zep"].repository_url).rstrip("/") == "https://github.com/getzep/graphiti"
    ):
        zep = rows["zep"]
        rows["graphiti"] = Tool(
            id="graphiti",
            name="Graphiti",
            source_ids=zep.source_ids,
            derived_from="zep",
            categories=["Knowledge Graphs", "Memory Systems"],
            disciplines=["graph", "memory"],
            kind="framework",
            website_url=zep.repository_url,
            repository_url=zep.repository_url,
        )
        rows["zep"] = zep.model_copy(update={"repository_url": None})
    directory_source = DirectorySource(
        url=f"https://github.com/SuperagenticAI/superradar/blob/{commit}/superradar-tools.json",
        commit=commit,
        sha256=hashlib.sha256(content).hexdigest(),
        updated_at=source["updatedAt"],
        entry_count=len(entries),
    )
    tools = sorted(rows.values(), key=lambda t: (t.name.casefold(), t.id))
    normalized_hash = hashlib.sha256(
        json.dumps([t.model_dump(mode="json") for t in tools], sort_keys=True).encode()
    ).hexdigest()
    return ToolDirectory(
        version="tools-" + commit[:12] + "-" + normalized_hash[:12],
        source=directory_source,
        tools=tools,
    )
