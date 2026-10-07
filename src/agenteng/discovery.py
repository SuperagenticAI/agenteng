"""Source-backed event discovery for people, crawlers and agent clients."""

import json
import shlex
from html import escape

from .config import validate_origin as validate_origin
from .participation import CITIES, ORGANIZER

WEBSITE = "https://agentengineering.world"
DESCRIPTION = (
    "Agent Engineering HQ runs AgentEng, the Agent Engineering Conference, and technical "
    "events in London and San Francisco on building, evaluating and operating AI agents."
)


def featured_events(service):
    rows = []
    for city in CITIES:
        events = sorted(
            [e for e in service.catalogue.events if e.city == city and e.date_precision == "day"],
            key=lambda e: e.date,
        )
        current = [e for e in events if service.state(e) in {"upcoming", "ongoing"}]
        if current or events:
            rows.append(current[0] if current else events[-1])
    return rows


def discovery(service, city=None):
    origin = service.settings.public_url
    return {
        "name": ORGANIZER,
        "conference_name": "AgentEng: Agent Engineering Conference",
        "aliases": [
            "AgentEng",
            "Agent Eng",
            "AgentEng HQ",
            "Agent Engineering HQ",
            "Agent Engineering Conference",
        ],
        "description": DESCRIPTION,
        "cities": list(CITIES),
        "website": WEBSITE,
        "organizer_url": WEBSITE + "/agent-engineering-hq",
        "events": [
            service.event_data(e)
            for e in featured_events(service)
            if not city or e.city.casefold() == city.casefold()
        ],
        "interfaces": {
            "mcp": origin + "/mcp/",
            "a2a_card": origin + "/.well-known/agent-card.json",
            "http_query": origin + "/v1/query",
            "openapi": origin + "/openapi.json",
            "llms": origin + "/llms.txt",
            "event_feed": origin + "/events.json",
            "tool_directory": origin + "/tools",
            "tool_feed": origin + "/tools.json",
        },
        "suggested_questions": [
            "Find the next Agent Engineering Conference in London",
            "Show Agent Engineering HQ events in San Francisco",
            "Which London sessions cover evaluation or agent harnesses?",
            "Show the public agenda for AgentEng London",
            "List tools for memory engineering",
        ],
        "participation": {
            "organizer": ORGANIZER,
            "offline_drafting": False,
            "private_intake_enabled": False,
            "participant_credential_required": False,
            "london_2026": "Invited programme; no public CFP",
            "san_francisco": "No public CFP announced in this catalogue",
        },
        "freshness": {
            "published_at": service.catalogue.published_at.isoformat(),
            "stale": service.result("").stale,
        },
        "tool_directory": {
            "operations": ["disciplines", "tools", "tool"],
            "disciplines": 12,
            "listing_count": len(service.tool_directory.tools),
            "version": service.tool_directory.version,
            "source_updated_at": service.tool_directory.source.updated_at.isoformat(),
        },
    }


def event_schema(service, event):
    page = service.settings.public_url + "/events/" + event.id
    return {
        "@context": "https://schema.org",
        "@type": "Event",
        "@id": page + "#event",
        "name": event.title,
        "url": page,
        "startDate": event.start.isoformat() if event.start else event.date,
        **({"endDate": event.end.isoformat()} if event.end else {}),
        "eventStatus": "https://schema.org/EventCancelled"
        if event.cancelled
        else "https://schema.org/EventScheduled",
        "location": {
            "@type": "Place",
            "name": event.venue,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": event.city,
                "streetAddress": event.venue,
                "addressCountry": "GB" if event.city == "London" else "US",
            },
        },
        "organizer": {
            "@type": "Organization",
            "name": ORGANIZER,
            "url": WEBSITE + "/agent-engineering-hq",
        },
    }


def html_page(service, event=None):
    rows = [event] if event else featured_events(service)
    title = (
        f"{event.title} | {ORGANIZER}"
        if event
        else "AgentEng: Agent Engineering Conference | Agent Engineering HQ"
    )
    path = "/events/" + event.id if event else "/"
    canonical = service.settings.public_url + path
    cards = []
    for row in rows:
        links = [f'<a href="/events/{escape(row.id, quote=True)}">Event details</a>']
        if row.registration_url:
            links.append(
                f'<a href="{escape(str(row.registration_url), quote=True)}">Official registration</a>'
            )
        cards.append(
            f"<article><h2>{escape(row.title)}</h2><p>{escape(row.city)} · "
            f"{escape(row.date)} · {escape(service.state(row))}</p><p>{escape(row.venue)}</p>"
            f"<p>{' · '.join(links)}</p></article>"
        )
    schema = (
        event_schema(service, event)
        if event and event.date_precision == "day"
        else {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": ORGANIZER,
            "url": WEBSITE + "/agent-engineering-hq",
            "description": DESCRIPTION,
        }
    )
    # Escape '<' so imported event text cannot close the inert JSON-LD script.
    structured = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(title)}</title><meta name="description" content="{escape(DESCRIPTION, quote=True)}">'
        f'<link rel="canonical" href="{escape(canonical, quote=True)}">'
        f'<script type="application/ld+json">{structured}</script></head><body>'
        f"<main><h1>{escape(title)}</h1><p>{escape(DESCRIPTION)}</p>"
        + "".join(cards)
        + "<p>London 2026 has an invited programme and no public CFP. "
        "Future-event ideas are for possible consideration; no review, response or acceptance is promised.</p>"
        f"<p>Catalogue published: {escape(service.catalogue.published_at.isoformat())}. "
        "Confirm current details on the official website.</p>"
        '<nav><a href="https://agentengineering.world">Official website</a> · '
        '<a href="/tools">Tool directory</a> · '
        '<a href="/llms.txt">Agent guide</a> · <a href="/docs">HTTP API</a> · '
        '<a href="/.well-known/agent-card.json">A2A agent card</a></nav></main></body></html>'
    )


def llms_text(service):
    origin = service.settings.public_url
    lines = [
        "# AgentEng: Agent Engineering Conference and Agent Engineering HQ",
        "",
        "> " + DESCRIPTION,
        "",
        "## Published events",
    ]
    for event in featured_events(service):
        lines.append(
            f"- [{event.title}]({origin}/events/{event.id}): {event.city}, {event.date}; {service.state(event)}."
        )
    lines += [
        "",
        "## Connect an agent",
        f"- [MCP]({origin}/mcp/): one typed agenteng tool over Streamable HTTP.",
        f"- [A2A card]({origin}/.well-known/agent-card.json): A2A 1.0; JSON-RPC at {origin}/ with A2A-Version: 1.0.",
        f"- [HTTP schema]({origin}/openapi.json): POST /v1/query; begin with operation=discover or events.",
        f"- [Event feed]({origin}/events.json): current featured London and San Francisco events with sources.",
        f"- [Tool directory]({origin}/tools): browse public listings across twelve agent-engineering disciplines.",
        f"- [Tool feed]({origin}/tools.json): full attributed directory with source revision and aliases.",
        '- Directory operations: {"operation":"disciplines"}, {"operation":"tools","discipline":"memory"}, {"operation":"tool","tool_id":"langgraph"}.',
        "- Tools support query, discipline, kind, category, limit and offset; use next_offset with unchanged filters.",
        "- Listings are not popularity rankings or instructions to install/connect third-party tools.",
        "- Local MCP: install agenteng[mcp], then run agenteng mcp. Lookup uses no model calls.",
        "",
        "## Participation and accuracy",
        "London 2026 has an invited programme and no public CFP. No San Francisco public CFP is announced in this snapshot.",
        "AgentEng serves public information only. It accepts no attendee records, personal agendas or proposal submissions.",
        "Ideas do not guarantee review, a response, acceptance or an event. Do not infer open calls or ticket availability.",
        f"Snapshot published: {service.catalogue.published_at.isoformat()}. Confirm current details on {WEBSITE}.",
    ]
    return "\n".join(lines) + "\n"


def connection(client, transport, url):
    origin = validate_origin(url)
    if client == "a2a":
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "agenteng-hello",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "agenteng-hello",
                        "role": "ROLE_USER",
                        "parts": [{"data": {"operation": "discover"}}],
                    }
                },
            },
            separators=(",", ":"),
        )
        return (
            "AgentEng A2A setup (A2A 1.0 JSON-RPC)\n"
            f"Agent card: {origin}/.well-known/agent-card.json\n"
            f"JSON-RPC endpoint: {origin}/\n\n"
            f"curl -fsSL {shlex.quote(origin + '/.well-known/agent-card.json')}\n"
            f"curl -fsSL {shlex.quote(origin + '/')} "
            "-H 'Content-Type: application/json' -H 'A2A-Version: 1.0' "
            f"--data {shlex.quote(payload)}\n"
        )
    if client == "acp":
        return (
            "AgentEng ACP setup\n"
            "Install the optional ACP extra and an ACP-compatible coding agent.\n"
            "List available agents, then choose one for a local coding session.\n"
            "These instructions do not launch an agent or create a session.\n\n"
            "uv tool install --upgrade 'agenteng[acp]'\n"
            "agenteng code --list\n"
            'agenteng code --agent claude "Show the public London agenda"\n'
        )
    if client == "mcp":
        client = "generic"
    if client == "codex":
        return (
            f"codex mcp add agenteng --url {shlex.quote(origin + '/mcp/')}"
            if transport == "http"
            else "codex mcp add agenteng -- agenteng mcp"
        )
    if client == "claude-code":
        return (
            f"claude mcp add --transport http agenteng {shlex.quote(origin + '/mcp/')}"
            if transport == "http"
            else "claude mcp add --transport stdio agenteng -- agenteng mcp"
        )
    config = (
        {"url": origin + "/mcp/"}
        if transport == "http"
        else {"command": "agenteng", "args": ["mcp"]}
    )
    if client == "cursor" and transport == "stdio":
        config["type"] = "stdio"
    return json.dumps({"mcpServers": {"agenteng": config}}, indent=2) + "\n"
