#!/usr/bin/env python3
"""Check live discovery, HTTP and the single hosted MCP tool after deployment."""

import argparse
import asyncio

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from agenteng.discovery import validate_origin

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("url")
args = parser.parse_args()


async def check():
    base = validate_origin(args.url)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for path in [
            "/health",
            "/catalogue.json",
            "/.well-known/agent-card.json",
            "/",
            "/events.json",
            "/llms.txt",
            "/robots.txt",
            "/sitemap.xml",
        ]:
            response = await client.get(base + path)
            response.raise_for_status()
            print(path, "ok")
        discovery = (await client.get(base + "/events.json")).json()
        assert discovery["data"]["cities"] == ["London", "San Francisco"]
        for event in discovery["data"]["events"]:
            (await client.get(base + "/events/" + event["id"])).raise_for_status()
        response = await client.post(base + "/v1/query", json={"operation": "events"})
        response.raise_for_status()
        assert response.json()["engine"] == "lookup"
        card = (await client.get(base + "/.well-known/agent-card.json")).json()
        assert card["supportedInterfaces"][0]["url"] == base + "/"
        response = await client.post(
            base + "/",
            headers={"A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "smoke",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "smoke",
                        "role": "ROLE_USER",
                        "parts": [{"data": {"operation": "events"}}],
                    }
                },
            },
        )
        response.raise_for_status()
        assert "error" not in response.json(), response.json()
        print("A2A SendMessage ok")
        async with streamable_http_client(base + "/mcp/", http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                assert [t.name for t in (await session.list_tools()).tools] == ["agenteng"]
                result = await session.call_tool("agenteng", {"request": {"operation": "events"}})
                assert not result.isError and result.structuredContent["engine"] == "lookup"
                print("MCP agenteng ok")


asyncio.run(check())
