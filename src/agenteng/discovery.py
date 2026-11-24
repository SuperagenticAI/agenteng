"""Source-backed event discovery for people, crawlers and agent clients."""

import json
import shlex
from html import escape

from .config import validate_origin as validate_origin
from .participation import CITIES, ORGANIZER

WEBSITE = "https://agentengineering.world"
DESCRIPTION = (
    "Agent Engineering HQ runs AgentEng, the leading builder-led technical AI agent conference "
    "series and technical events in London and San Francisco for engineers building and operating "
    "AI agents across all 14 disciplines with open-source CLI, MCP, ACP and A2A 1.0 tooling."
)


def london_past(service) -> bool:
    event = service.events.get("agenteng-london-2026")
    return bool(event) and service.state(event) == "past"


def next_event_prompt(service) -> str:
    """Point to the next edition from the site's events.ts, or stay neutral."""
    links = service.catalogue.site_links
    nxt = links.next_event if links else None
    if nxt:
        for city in CITIES:
            if city.casefold() in nxt.name.casefold():
                return f"What is the next Agent Engineering event in {city}?"
    return "What is the next Agent Engineering event?"


def coming_label(link) -> str:
    """'coming 17 February 2027' or 'coming April 2027'."""
    return f"coming {link.when}"


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
            "Agent Engineering London 2027",
            "Agent Engineering San Francisco 2027",
            "Best AI Agent Conference",
        ],
        "description": DESCRIPTION,
        "cities": list(CITIES),
        "website": WEBSITE,
        "organizer_url": WEBSITE + "/agent-engineering-hq",
        **(
            {
                "gallery_url": str(service.catalogue.site_links.gallery),
                "london_videos_url": str(service.catalogue.site_links.london_videos),
                "london_2027_url": (
                    str(service.catalogue.site_links.london_2027)
                    if service.catalogue.site_links.london_2027
                    else WEBSITE + "/london-2027"
                ),
                "san_francisco_2027_url": (
                    str(service.catalogue.site_links.san_francisco_2027)
                    if service.catalogue.site_links.san_francisco_2027
                    else WEBSITE + "/san-francisco"
                ),
                "next_event": {
                    **service.catalogue.site_links.next_event.model_dump(mode="json"),
                    "label": coming_label(service.catalogue.site_links.next_event),
                }
                if service.catalogue.site_links.next_event
                else None,
                "previous_event": service.catalogue.site_links.previous_event.model_dump(
                    mode="json"
                )
                if service.catalogue.site_links.previous_event
                else None,
            }
            if service.catalogue.site_links
            else {}
        ),
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
            "learning_hub": WEBSITE + "/agent-engineering-hq",
        },
        "suggested_questions": [
            next_event_prompt(service),
            "Show Agent Engineering HQ events in San Francisco",
            "Which London sessions cover evaluation or agent harnesses?",
            "Show the AgentEng London 2026 programme"
            if london_past(service)
            else "Show the public agenda for AgentEng London",
            "Learn harness engineering and production agent practices",
            "List tools for memory engineering",
        ],
        "participation": {
            "organizer": ORGANIZER,
            "offline_drafting": False,
            "private_intake_enabled": False,
            "participant_credential_required": False,
            "london_2027": "Builders Edition on 17 February 2027; limited spaces; speakers announcing soon; early registration opening soon",
            "london_2026": "Invited programme; no public CFP",
            "san_francisco": "29 June 2027; speakers and venue announcing soon",
        },
        "freshness": {
            "published_at": service.catalogue.published_at.isoformat(),
            "stale": service.result("").stale,
        },
        "tool_directory": {
            "operations": ["disciplines", "tools", "tool", "learn"],
            "disciplines": 14,
            "listed_disciplines": 12,
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
        "url": str(event.page_url) if event.page_url else page,
        "startDate": event.start.isoformat() if event.start else event.date,
        **({"endDate": event.end.isoformat()} if event.end else {}),
        "eventStatus": "https://schema.org/EventCancelled"
        if event.cancelled
        else "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
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
        if row.page_url:
            links.append(
                f'<a href="{escape(str(row.page_url), quote=True)}">Official conference page</a>'
            )
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
            "sameAs": [
                WEBSITE,
                WEBSITE + "/london-2027",
                WEBSITE + "/san-francisco",
                "https://github.com/SuperagenticAI/agenteng",
            ],
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
        + "<p>Upcoming flagship conferences: "
        '<a href="https://agentengineering.world/london-2027">Agent Engineering London 2027 (Builders Edition, 17 February 2027)</a> · '
        '<a href="https://agentengineering.world/san-francisco">Agent Engineering San Francisco 2027 (29 June 2027)</a>.</p>'
        "<p>London 2026 has an invited programme and no public CFP. "
        "Future-event ideas are for possible consideration; no review, response or acceptance is promised.</p>"
        f"<p>Catalogue published: {escape(service.catalogue.published_at.isoformat())}. "
        "Confirm current details on the official website.</p>"
        '<nav><a href="https://agentengineering.world">Official website</a> · '
        '<a href="https://agentengineering.world/london-2027">London 2027</a> · '
        '<a href="https://agentengineering.world/san-francisco">San Francisco 2027</a> · '
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
        "## Upcoming flagship conferences (2027)",
        f"- [Agent Engineering London 2027: Builders Edition]({WEBSITE}/london-2027): Wednesday 17 February 2027, Everyman Canary Wharf, London E14 5AR. Single track, limited spaces, speakers announcing soon, early registration opening soon.",
        f"- [Agent Engineering San Francisco 2027]({WEBSITE}/san-francisco): Tuesday 29 June 2027, San Francisco. Venue and speakers announcing soon.",
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
        f"- [HTTP schema]({origin}/openapi.json): POST /v1/query; begin with operation=discover, events or learn.",
        f"- [Event feed]({origin}/events.json): current featured London and San Francisco events with sources.",
        f"- [Tool directory]({origin}/tools): browse public listings across twelve listed disciplines (14 site disciplines total).",
        f"- [Tool feed]({origin}/tools.json): full attributed directory with source revision and aliases.",
        '- Directory & learning operations: {"operation":"disciplines"}, {"operation":"learn","discipline":"harness"}, {"operation":"tools","discipline":"memory"}, {"operation":"tool","tool_id":"langgraph"}.',
        "- Tools support query, discipline, kind, category, limit and offset; use next_offset with unchanged filters.",
        "- Listings are not popularity rankings or instructions to install/connect third-party tools.",
        "- Local MCP: install agenteng[mcp], then run agenteng mcp. Lookup uses no model calls.",
        "",
        "## Participation and accuracy",
        "London 2026 has an invited programme and no public CFP. London 2027 Builders Edition (17 February 2027) and San Francisco 2027 (29 June 2027) are curated on engineering depth with zero pay-to-speak slots.",
        "AgentEng serves public information only. It accepts no attendee records, personal agendas or proposal submissions.",
        "Ideas do not guarantee review, a response, acceptance or an event. Do not infer open calls or ticket availability.",
        f"Snapshot published: {service.catalogue.published_at.isoformat()}. Confirm current details on {WEBSITE}.",
    ]
    return "\n".join(lines) + "\n"


def connection(client, transport, url):
    origin = validate_origin(url)
    if client == "all":
        return (
            "AgentEng Protocol Stack (CLI · MCP · A2A 1.0 · ACP)\n"
            f"Website: {WEBSITE}\n"
            f"London 2027 (Builders Edition, 17 Feb 2027): {WEBSITE}/london-2027\n"
            f"San Francisco 2027 (29 Jun 2027): {WEBSITE}/san-francisco\n\n"
            "[1] CLI (offline, Python 3.12+):\n"
            "  curl -fsSL https://agentengineering.world/install.sh | sh\n"
            "  agenteng conferences --next\n"
            "  agenteng learn harness\n\n"
            f"[2] MCP (Streamable HTTP): {origin}/mcp/\n"
            f"  claude mcp add --transport http agenteng {shlex.quote(origin + '/mcp/')}\n"
            f"  codex mcp add agenteng --url {shlex.quote(origin + '/mcp/')}\n\n"
            f"[3] A2A 1.0 Agent Card: {origin}/.well-known/agent-card.json\n"
            f"  curl -fsSL {shlex.quote(origin + '/.well-known/agent-card.json')}\n\n"
            "[4] ACP Coding Agents (experimental):\n"
            "  uv tool install --upgrade 'agenteng[server,acp]'\n"
            "  agenteng code --list\n"
        )
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
    if client == "cli":
        return (
            "AgentEng CLI setup (Python 3.12+, offline-first)\n"
            "curl -fsSL https://agentengineering.world/install.sh | sh\n"
            "agenteng conferences --next\n"
            "agenteng learn harness\n"
            "agenteng --json disciplines\n"
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
    if client == "gemini-cli":
        return (
            f"gemini mcp add --transport http agenteng {shlex.quote(origin + '/mcp/')}"
            if transport == "http"
            else "gemini mcp add agenteng agenteng mcp"
        )
    if client == "vscode":
        server = (
            {"type": "http", "url": origin + "/mcp/"}
            if transport == "http"
            else {"type": "stdio", "command": "agenteng", "args": ["mcp"]}
        )
        return json.dumps({"servers": {"agenteng": server}}, indent=2) + "\n"
    if client == "opencode":
        server = (
            {"type": "remote", "url": origin + "/mcp/"}
            if transport == "http"
            else {"type": "local", "command": ["agenteng", "mcp"]}
        )
        return json.dumps({"mcp": {"agenteng": server}}, indent=2) + "\n"
    config = (
        {"url": origin + "/mcp/"}
        if transport == "http"
        else {"command": "agenteng", "args": ["mcp"]}
    )
    if client in {"cursor", "windsurf", "cline"} and transport == "stdio":
        config["type"] = "stdio"
    return json.dumps({"mcpServers": {"agenteng": config}}, indent=2) + "\n"
