import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from agenteng.cli import main
from agenteng.server import LimitsMiddleware, create_app


@pytest.mark.asyncio
async def test_http_and_real_a2a_jsonrpc(service):
    app = create_app(service)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://localhost",
            headers={"A2A-Version": "1.0"},
        ) as client,
    ):
        assert (await client.get("/health")).json()["default_engine"] == "lookup"
        card_response = await client.get("/.well-known/agent-card.json")
        assert card_response.status_code == 200
        assert "max-age=300" in card_response.headers["cache-control"]
        card = card_response.json()
        assert card["supportedInterfaces"][0]["protocolVersion"] == "1.0"
        direct = await client.post("/v1/query", json={"operation": "events", "upcoming": True})
        payload = {
            "jsonrpc": "2.0",
            "id": "test",
            "method": "SendMessage",
            "params": {
                "message": {
                    "messageId": "user-1",
                    "role": "ROLE_USER",
                    "parts": [{"data": {"operation": "events", "upcoming": True}}],
                }
            },
        }
        response = await client.post("/", json=payload)
        data = response.json()
        assert "error" not in data, data
        parts = data["result"]["message"]["parts"]
        assert parts[1]["data"] == direct.json()
        payload["params"]["message"]["parts"] = [{"text": "memory"}]
        assert "error" not in (await client.post("/", json=payload)).json()
        payload["params"]["message"]["parts"] = [{"data": {"operation": "tickets"}}]
        assert (await client.post("/", json=payload)).json()["error"]["code"] == -32602
        assert (await client.post("/v1/query", json={"operation": "tickets"})).status_code == 422
        assert (
            await client.post(
                "/v1/query",
                json={"operation": "events"},
                headers={"Origin": "https://evil.example"},
            )
        ).status_code == 403
        assert (await client.post("/v1/query", content=b"x" * 65537)).status_code == 413
        assert (await client.get("/health", headers={"Host": "evil.example"})).status_code == 400
        assert "#!/bin/sh" in (await client.get("/install.sh")).text
        assert (await client.get("/catalogue.json")).json()[
            "source_hash"
        ] == service.catalogue.source_hash


@pytest.mark.asyncio
async def test_real_mcp_streamable_http(service):
    app = create_app(service)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), follow_redirects=True) as http,
        streamable_http_client("http://localhost/mcp/", http_client=http) as (
            read,
            write,
            _,
        ),
        ClientSession(read, write) as session,
    ):
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "Agent Engineering HQ"
        listing = await session.list_tools()
        assert [t.name for t in listing.tools] == ["agenteng"]
        tool = listing.tools[0]
        assert tool.annotations.readOnlyHint is True
        assert tool.outputSchema
        called = await session.call_tool(
            "agenteng",
            {"request": {"operation": "tickets", "event_id": "agenteng-london-2026"}},
        )
        assert not called.isError
        result = called.structuredContent
        assert result["data"]["current_offers"][0]["amount"] == 149
        assert result["sources"]
        participation = await session.call_tool(
            "agenteng", {"request": {"operation": "participate"}}
        )
        assert participation.structuredContent["data"]["automated_submission_available"] is False
        disabled = await session.call_tool(
            "agenteng",
            {"request": {"operation": "ask", "query": "memory", "engine": "rlm"}},
        )
        assert disabled.structuredContent["status"] == "unavailable"
        for operation in ["save", "my_agenda", "plan", "proposal_submit"]:
            rejected = await session.call_tool(
                "agenteng",
                {
                    "request": {
                        "operation": operation,
                        "contact_email": "PRIVATE_MCP_SENTINEL@example.invalid",
                    }
                },
            )
            assert rejected.isError
            assert "PRIVATE_MCP_SENTINEL" not in rejected.model_dump_json()
        invalid = await session.call_tool("agenteng", {"request": {"operation": "tickets"}})
        assert invalid.isError


@pytest.mark.asyncio
async def test_real_mcp_stdio():
    env = {**os.environ, "PYTHONPATH": str(Path("src").resolve()), "PYTHONDONTWRITEBYTECODE": "1"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "agenteng", "mcp"], env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        assert len((await session.list_tools()).tools) == 1
        called = await session.call_tool("agenteng", {"request": {"operation": "events"}})
        assert called.structuredContent["catalogue_version"]
        assert len(called.structuredContent["data"]) == 11
        tools = await session.call_tool(
            "agenteng", {"request": {"operation": "tools", "discipline": "memory"}}
        )
        assert tools.structuredContent["data"]["total"] > 3


def test_cli_output_and_calendar(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["--json", "events", "--upcoming"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["engine"] == "lookup"
    result = runner.invoke(main, ["--json", "tickets", "missing"])
    assert result.exit_code == 1 and json.loads(result.output)["status"] == "not_found"
    path = tmp_path / "agenda.ics"
    result = runner.invoke(
        main, ["agenda", "agenteng-london-2026", "--format", "ics", "--output", str(path)]
    )
    assert result.exit_code == 0, result.output
    assert b"BEGIN:VCALENDAR\r\n" in path.read_bytes()


@pytest.mark.asyncio
async def test_global_rate_limit():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def ok(request):
        return JSONResponse({"ok": True})

    app = LimitsMiddleware(Starlette(routes=[Route("/", ok, methods=["POST"])]), per_minute=1)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://localhost"
    ) as client:
        assert (await client.post("/")).status_code == 200
        assert (await client.post("/")).status_code == 429


@pytest.mark.asyncio
async def test_operator_credential_required_on_all_http_transports():
    from dataclasses import replace

    from agenteng.config import Settings
    from agenteng.service import Service

    class Provider:
        calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            evidence = json.loads(messages[1]["content"])["evidence"]
            return {
                "message": {
                    "content": json.dumps(
                        {"answer": "Supported finding.", "source_ids": [evidence[0]["source_id"]]}
                    )
                },
                "usage": {},
            }

    provider = Provider()
    settings = replace(Settings(), enable_standard=True, operator_token="operator")
    app = create_app(Service(settings, provider=provider))
    request = {"operation": "ask", "query": "memory", "engine": "standard", "limit": 1}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost", follow_redirects=True
        ) as client,
    ):
        assert (await client.post("/v1/query", json=request)).json()["status"] == "unavailable"
        assert provider.calls == 0
        assert (
            await client.post(
                "/v1/query", json=request, headers={"Authorization": "Bearer operator"}
            )
        ).json()["status"] == "ok"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "SendMessage",
            "params": {
                "message": {
                    "messageId": "op",
                    "role": "ROLE_USER",
                    "parts": [{"data": request}],
                }
            },
        }
        headers = {"A2A-Version": "1.0"}
        response = (await client.post("/", json=payload, headers=headers)).json()
        assert response["result"]["message"]["parts"][1]["data"]["status"] == "unavailable"
        response = (
            await client.post(
                "/", json=payload, headers={**headers, "Authorization": "Bearer operator"}
            )
        ).json()
        assert response["result"]["message"]["parts"][1]["data"]["status"] == "ok"
        for authenticated in [False, True]:
            client.headers["Authorization"] = "Bearer operator" if authenticated else "Bearer wrong"
            async with streamable_http_client("http://localhost/mcp/", http_client=client) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    response = await session.call_tool("agenteng", {"request": request})
                    assert response.structuredContent["status"] == (
                        "ok" if authenticated else "unavailable"
                    )
        assert provider.calls == 3


def test_cli_participation_guidance():
    result = CliRunner().invoke(main, ["--json", "participate"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["automated_submission_available"] is False
    assert payload["sources"][0]["id"] == "contact"


@pytest.mark.asyncio
async def test_participation_http_and_a2a_are_read_only(service):
    app = create_app(service)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client,
    ):
        direct = (await client.post("/v1/query", json={"operation": "participate"})).json()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "SendMessage",
            "params": {
                "message": {
                    "messageId": "participate",
                    "role": "ROLE_USER",
                    "parts": [{"text": "How can I propose a talk?"}],
                }
            },
        }
        response = (await client.post("/", json=payload, headers={"A2A-Version": "1.0"})).json()
        assert response["result"]["message"]["parts"][1]["data"] == direct
        assert direct["data"]["automated_submission_available"] is False


@pytest.mark.asyncio
async def test_website_a2a_cors_preflight_and_message(service):
    """The website can discover and query A2A 1.0 from an allowed origin."""
    app = create_app(service)
    origin = "https://agentengineering.world"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client,
    ):
        preflight = await client.options(
            "/",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,a2a-version",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert "a2a-version" in preflight.headers["access-control-allow-headers"].lower()
        card = await client.get("/.well-known/agent-card.json", headers={"Origin": origin})
        assert card.status_code == 200
        assert card.headers["access-control-allow-origin"] == origin
        response = await client.post(
            "/",
            headers={"Origin": origin, "A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "website-chat",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "website-user-1",
                        "contextId": "website-session-1",
                        "role": "ROLE_USER",
                        "parts": [
                            {"data": {"operation": "tools", "discipline": "memory", "limit": 6}}
                        ],
                    }
                },
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        payload = response.json()
        assert "error" not in payload, payload
        result = payload["result"]["message"]["parts"][1]["data"]
        assert result["status"] == "ok"
        assert result["data"]["items"]
        denied = await client.options(
            "/",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,a2a-version",
            },
        )
        assert denied.status_code == 403
        assert "access-control-allow-origin" not in denied.headers
