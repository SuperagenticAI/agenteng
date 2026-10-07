"""Combined read-only HTTP, hosted MCP and A2A application."""

import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Query
from fastapi import Path as PathParameter
from fastapi import Request as HTTPRequest
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import HTMLResponse, JSONResponse, Response

from . import __version__
from .a2a import add_a2a
from .auth import bearer
from .discovery import featured_events, html_page, llms_text
from .mcp import create_mcp
from .models import Request, Result
from .service import Service
from .tool_directory import DisciplineID, ToolKind
from .tool_pages import tool_page


class LimitsMiddleware:
    """Bound body size and process-wide request rate before protocol parsing.

    No IP trust assumptions behind proxies. For multi-instance hosting, enforce
    caller/global quotas at the edge; this in-memory cap is per process only.
    """

    def __init__(self, app, per_minute=300, max_body=65536):
        self.app, self.per_minute, self.max_body = app, per_minute, max_body
        self.seen = deque()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        now = time.monotonic()
        while self.seen and self.seen[0] < now - 60:
            self.seen.popleft()
        if len(self.seen) >= self.per_minute:
            return await JSONResponse(
                {"error": "Request rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "60"},
            )(scope, receive, send)
        self.seen.append(now)
        # Buffer bounded requests once; do not rely on an untrusted Content-Length.
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_body:
                return await JSONResponse({"error": "Request body too large"}, status_code=413)(
                    scope, receive, send
                )
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()

        return await self.app(scope, replay, send)


def create_app(service: Service | None = None):
    service = service or Service()
    mcp = create_mcp(service)

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="Agent Engineering HQ", version=__version__, lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # FastAPI's default errors repeat input values, including personal text pasted into a public request.
        return JSONResponse(
            {"error": "Invalid AgentEng request; check the published schema."}, status_code=422
        )

    app.add_middleware(LimitsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(service.settings.allowed_origins),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "A2A-Version",
            "MCP-Protocol-Version",
            "MCP-Session-Id",
        ],
        expose_headers=["MCP-Session-Id"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            urlsplit(service.settings.public_url).hostname,
            "localhost",
            "127.0.0.1",
            "[::1]",
        ],
    )

    @app.middleware("http")
    async def origin_check(request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in service.settings.allowed_origins:
            return JSONResponse({"error": "Origin not allowed"}, status_code=403)
        response = await call_next(request)
        if request.url.path == "/.well-known/agent-card.json":
            response.headers["Cache-Control"] = "public, max-age=300"
        elif request.method == "POST":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", include_in_schema=False)
    async def landing():
        return HTMLResponse(html_page(service))

    @app.get("/events/{event_id}", include_in_schema=False)
    async def event_page(event_id: str):
        event = service.events.get(event_id)
        if not event:
            return Response("Published event not found", status_code=404)
        return HTMLResponse(html_page(service, event))

    @app.get("/events.json")
    async def event_feed():
        return service.lookup(Request(operation="discover"))

    @app.get("/tools", include_in_schema=False)
    async def tools_page(
        discipline: DisciplineID | None = None,
        kind: ToolKind | None = None,
        category: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
        query: Annotated[str, Query(max_length=4000)] = "",
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0, le=10000)] = 0,
        tool_status: Literal["listed", "hold", "deprecated", "all"] = "listed",
    ):
        payload = Request(
            operation="tools",
            discipline=discipline,
            kind=kind,
            category=category,
            query=query,
            limit=limit,
            offset=offset,
            tool_status=tool_status,
        )
        return HTMLResponse(tool_page(service, service.lookup(payload), payload))

    @app.get("/tools/{tool_id}", include_in_schema=False)
    async def tool_detail(tool_id: Annotated[str, PathParameter(min_length=1, max_length=128)]):
        payload = Request(operation="tool", tool_id=tool_id)
        result = service.lookup(payload)
        if result.status != "ok":
            return Response("Tool not found", status_code=404)
        return HTMLResponse(tool_page(service, result, payload))

    @app.get("/tools.json")
    async def tool_feed():
        return JSONResponse(
            service.tool_directory.model_dump(mode="json"),
            headers={
                "ETag": 'W/"' + service.tool_directory.version + '"',
                "Cache-Control": "public, max-age=300",
            },
        )

    @app.get("/llms.txt", include_in_schema=False)
    async def llms():
        return Response(llms_text(service), media_type="text/plain")

    @app.get("/robots.txt", include_in_schema=False)
    async def robots():
        return Response(
            "User-agent: *\nAllow: /\nDisallow: /mcp/\nDisallow: /v1/\n"
            f"Sitemap: {service.settings.public_url}/sitemap.xml\n",
            media_type="text/plain",
        )

    @app.get("/sitemap.xml", include_in_schema=False)
    async def sitemap():
        from xml.sax.saxutils import escape

        urls = [
            service.settings.public_url + "/",
            service.settings.public_url + "/tools",
            *[service.settings.public_url + "/events/" + e.id for e in featured_events(service)],
            *[
                service.settings.public_url + "/tools/" + t.id
                for t in service.tool_directory.tools
                if t.status == "listed"
            ],
        ]
        body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        body += "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls) + "</urlset>"
        return Response(body, media_type="application/xml")

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "catalogue_version": service.catalogue.version,
            "published_at": service.catalogue.published_at,
            "stale": service.result("").stale,
            "default_engine": "lookup",
            "chat_enabled": service.settings.enable_chat,
            "standard_enabled": service.settings.enable_standard,
            "rlm_enabled": service.settings.enable_rlm,
            "private_intake_enabled": False,
            "tool_directory_version": service.tool_directory.version,
            "tool_listing_count": len(service.tool_directory.tools),
        }

    @app.get("/catalogue.json")
    async def catalogue():
        return JSONResponse(
            service.catalogue.model_dump(mode="json"),
            headers={
                "ETag": '"' + service.catalogue.source_hash + '"',
                "Cache-Control": "public, max-age=300",
            },
        )

    @app.get("/install.sh", include_in_schema=False)
    async def installer():
        return Response(
            Path(__file__).with_name("data").joinpath("install.sh").read_text(),
            media_type="text/plain",
            headers={"Cache-Control": "public, max-age=300"},
        )

    @app.post("/v1/query", response_model=Result)
    async def query(payload: Request, request: HTTPRequest):
        return await service.execute(payload, token=bearer(request.headers))

    app.mount("/mcp", mcp.streamable_http_app())
    # A2A tenant catch-all routes must be registered after our named routes.
    app.state.agent_card = add_a2a(app, service)
    app.state.service = service
    return app
