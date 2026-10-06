"""Exactly one typed read-only tool over stdio or Streamable HTTP."""

import os
from urllib.parse import urlsplit

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from . import __version__
from .auth import bearer
from .models import Request, Result
from .service import Service
from .participation import PRIVATE_OPERATIONS


def create_mcp(service: Service, *, stdio: bool = False) -> FastMCP:
    host = urlsplit(service.settings.public_url).netloc
    mcp = FastMCP(
        "Agent Engineering HQ",
        instructions=(
            "Use the single agenteng tool for public events, agendas, speakers, talks, FAQ, venue, "
            "sponsors, code of conduct, themes, tickets, recordings, search, now/next, local bookmarks, "
            "session planning and participation guidance. Start with operation=events to discover event_id. "
            "Use disciplines to find the twelve tool-directory filters, tools to browse/search with "
            "discipline, kind, category, query, limit and offset, and tool with tool_id for links. "
            "Continue pagination with next_offset and unchanged filters. Listings are not popularity rankings. "
            "AgentEng is the Agent Engineering Conference, organized by Agent Engineering HQ in London and San Francisco. "
            "Use about for the organiser, chair and connection details, hq for the manifesto, "
            "mindset and further reading, live for a now/next venue-screen snapshot (at overrides the clock), "
            "and bingo for a reproducible talk bingo card (seed, size 4 or 5, format text/svg/html). "
            "Use discover for featured events and interfaces; proposal_draft/preview/export prepare ideas without sending. "
            "Private intake requires organizer-issued participant access, proposal_prepare and explicit contributor "
            "confirmation before proposal_submit. London 2026 has an invited programme and no public CFP. "
            "Default lookup and auto use no server-side model. Model engines are operator-only."
        ),
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[
                host,
                "127.0.0.1",
                "127.0.0.1:*",
                "localhost",
                "localhost:*",
                "[::1]",
                "[::1]:*",
            ],
            allowed_origins=list(service.settings.allowed_origins),
        ),
    )

    # FastMCP reports the MCP SDK version in serverInfo unless the server sets its own.
    mcp._mcp_server.version = __version__

    @mcp.tool(
        name="agenteng",
        description="Discover AgentEng conferences in London and San Francisco, browse agent-engineering tools across twelve disciplines, query public facts and prepare proposals for Agent Engineering HQ.",
        annotations=ToolAnnotations(
            readOnlyHint=not service.settings.enable_intake,
            destructiveHint=service.settings.enable_intake,
            idempotentHint=not (
                service.settings.enable_standard
                or service.settings.enable_rlm
                or service.settings.enable_intake
            ),
            openWorldHint=service.settings.enable_standard or service.settings.enable_rlm,
        ),
        structured_output=True,
    )
    async def agenteng(request: Request, ctx: Context) -> Result:
        raw = ctx.request_context.request
        if raw is not None and hasattr(raw, "headers"):
            token = bearer(raw.headers)
        else:
            name = (
                "AGENTENG_PARTICIPANT_TOKEN"
                if request.operation in PRIVATE_OPERATIONS
                else "AGENTENG_OPERATOR_TOKEN"
            )
            token = os.getenv(name) if stdio else None
        return await service.execute(request, token=token)

    return mcp
