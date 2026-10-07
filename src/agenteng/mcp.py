"""Exactly one typed read-only tool over stdio or Streamable HTTP."""

import os
from urllib.parse import urlsplit

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from . import __version__
from .auth import bearer
from .models import Request, Result
from .service import Service


class PublicFastMCP(FastMCP):
    async def call_tool(self, name, arguments):
        try:
            return await super().call_tool(name, arguments)
        except ToolError:
            # SDK validation errors include raw input; keep personal text out of responses.
            raise ToolError(
                "Invalid AgentEng request or unavailable tool; check the published schema."
            ) from None


def create_mcp(service: Service, *, stdio: bool = False) -> FastMCP:
    host = urlsplit(service.settings.public_url).netloc
    mcp = PublicFastMCP(
        "Agent Engineering HQ",
        instructions=(
            "Use the single agenteng tool for public events, agendas, speakers, talks, FAQ, venue, "
            "sponsors, code of conduct, themes, tickets, recordings, search, now/next, "
            "public agendas and participation policy. Start with operation=events to discover event_id. "
            "Use disciplines to find the twelve tool-directory filters, tools to browse/search with "
            "discipline, kind, category, query, limit and offset, and tool with tool_id for links. "
            "Continue pagination with next_offset and unchanged filters. Listings are not popularity rankings. "
            "AgentEng is the Agent Engineering Conference, organized by Agent Engineering HQ in London and San Francisco. "
            "Use about for the organiser, chair and connection details, hq for the manifesto, "
            "mindset and further reading, live for a now/next venue-screen snapshot (at overrides the clock), "
            "and bingo for a reproducible talk bingo card in data (seed, size 4 or 5; format text, svg or html adds a printable copy in artifact). "
            "Use discover for featured public events and interfaces. No attendee records or submissions are accepted. "
            "Default lookup and auto use no server-side model. Standard and RLM engines are operator-only. "
            "The separate opt-in chat operation uses bounded public catalogue tools and lookup fallback."
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
        description="Discover AgentEng conferences in London and San Francisco, browse agent-engineering tools across twelve disciplines, query public facts from Agent Engineering HQ.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=not (
                service.settings.enable_chat
                or service.settings.enable_standard
                or service.settings.enable_rlm
            ),
            openWorldHint=service.settings.enable_chat
            or service.settings.enable_standard
            or service.settings.enable_rlm,
        ),
        structured_output=True,
    )
    async def agenteng(request: Request, ctx: Context) -> Result:
        raw = ctx.request_context.request
        if raw is not None and hasattr(raw, "headers"):
            token = bearer(raw.headers)
        else:
            token = os.getenv("AGENTENG_OPERATOR_TOKEN") if stdio else None
        return await service.execute(request, token=token)

    return mcp
