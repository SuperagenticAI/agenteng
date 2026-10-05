import asyncio
from datetime import timedelta
from dataclasses import replace
import json
import subprocess
import sys

from click.testing import CliRunner
import httpx
import pytest
from pydantic import ValidationError
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.server import create_app
from agenteng.service import Service
from agenteng.tool_directory import ToolDirectory, load_tool_directory
from agenteng.tool_import import normalize_snapshot


def test_complete_directory_and_pagination(service):
    directory = service.tool_directory
    assert directory.source.entry_count == 461
    assert len(directory.tools) == 456
    seen = []
    offset = 0
    while True:
        result = service.lookup(
            Request(operation="tools", limit=37, offset=offset, tool_status="all")
        )
        assert result.engine == "lookup" and result.usage == {}
        assert len(result.data["items"]) <= 37
        seen.extend(row["id"] for row in result.data["items"])
        offset = result.data["next_offset"]
        if offset is None:
            break
    assert len(seen) == len(set(seen)) == 456
    assert set(seen) == {tool.id for tool in directory.tools}
    beyond = service.lookup(Request(operation="tools", offset=10000))
    assert beyond.data["items"] == [] and beyond.data["next_offset"] is None
    source_ids = {sid for tool in directory.tools for sid in tool.source_ids}
    assert len(source_ids) == 461
    assert {"amp-code", "cline"} <= source_ids


def test_discipline_filters_aliases_and_source_status(service):
    disciplines = service.lookup(Request(operation="disciplines")).data
    assert len(disciplines["items"]) == 12
    assert all(row["tool_count"] > 0 for row in disciplines["items"])
    assert len(disciplines["categories"]) == 27
    rows = service.lookup(
        Request(operation="tools", discipline="inference", kind="runtime", limit=100)
    ).data["items"]
    assert {"ollama", "vllm", "sglang", "llama-cpp"} <= {r["id"] for r in rows}
    assert all(r["kind"] == "runtime" and "inference" in r["disciplines"] for r in rows)
    found = service.lookup(Request(operation="tools", query="Gemini CLI"))
    assert [r["id"] for r in found.data["items"]] == ["gemini-cli"]
    assert (
        service.lookup(Request(operation="tool", tool_id="letta-memory")).data["tool"]["id"]
        == "letta"
    )
    assert service.lookup(Request(operation="tool", tool_id="zep")).data["tool"]["name"] == "Zep"
    graphiti = service.lookup(Request(operation="tool", tool_id="graphiti")).data["tool"]
    assert graphiti["derived_from"] == "zep"
    assert graphiti["repository_url"] == "https://github.com/getzep/graphiti"
    listed = service.lookup(Request(operation="tools", category="agent frameworks", limit=100))
    assert "autogen" not in {r["id"] for r in listed.data["items"]}
    held = service.lookup(Request(operation="tools", tool_status="hold", limit=100))
    assert {r["id"] for r in held.data["items"]} == {"autogen", "semantic-kernel", "qoder"}
    empty = service.lookup(Request(operation="tools", query="nonexistent-product-zzzz"))
    assert empty.status == "ok" and empty.data["total"] == 0
    assert service.lookup(Request(operation="tool", tool_id="not-a-tool")).status == "not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {"operation": "tool"},
        {"operation": "tools", "discipline": "invented"},
        {"operation": "tools", "kind": "invented"},
        {"operation": "tools", "offset": -1},
        {"operation": "tools", "limit": 101},
        {"operation": "tools", "city": "London"},
        {"operation": "events", "discipline": "memory"},
        {"operation": "tools", "tool_id": "ollama"},
        {"operation": "tools", "engine": "rlm"},
        {"operation": "disciplines", "query": "memory"},
    ],
)
def test_directory_contract_rejects_invalid_and_mixed_requests(payload):
    with pytest.raises(ValidationError):
        Request.model_validate(payload)


def test_directory_offline_routing_and_independent_freshness(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Directory lookup must not contact network/providers")

    monkeypatch.setattr(httpx, "post", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    service = Service(
        replace(Settings(), enable_standard=True, enable_rlm=True), provider=forbidden
    )
    for operation in ["tools", "disciplines", "tool"]:
        request = Request(
            operation=operation, tool_id="ollama" if operation == "tool" else None, engine="auto"
        )
        assert asyncio.run(service.execute(request)).engine == "lookup"
    routed = service.lookup(Request(operation="ask", query="Show tools for memory engineering"))
    assert len(routed.data["items"]) > 3
    assert all("memory" in t["disciplines"] for t in routed.data["items"])
    assert (
        "organizer_email"
        in service.lookup(
            Request(operation="ask", query="Submit a proposal about memory tools")
        ).data
    )
    service.clock = lambda: service.tool_directory.source.updated_at + timedelta(hours=49)
    stale = service.lookup(Request(operation="tools"))
    assert stale.stale
    assert stale.published_at == service.tool_directory.source.updated_at
    assert stale.catalogue_version == service.tool_directory.version


def test_cli_directory_json_text_and_unknown_ids():
    runner = CliRunner()
    result = runner.invoke(main, ["--json", "tools", "--discipline", "memory", "--limit", "2"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["data"]["items"]) == 2 and payload["data"]["next_offset"] == 2
    # Non-TTY stdout returns the shared Result JSON (agents / pipes).
    piped = runner.invoke(main, ["tools", "--limit", "2"])
    assert piped.exit_code == 0, piped.output
    assert json.loads(piped.output)["data"]["next_offset"] == 2
    assert "memory" in runner.invoke(main, ["disciplines"]).output
    alias = runner.invoke(main, ["--json", "tool", "letta-memory"])
    assert json.loads(alias.output)["data"]["tool"]["id"] == "letta"
    assert runner.invoke(main, ["tool", "unknown"]).exit_code == 1


@pytest.mark.asyncio
async def test_tool_http_a2a_and_real_mcp_parity(service):
    app = create_app(service)
    payload = {"operation": "tools", "discipline": "code", "kind": "cli", "limit": 3, "offset": 3}
    expected = service.lookup(Request.model_validate(payload)).model_dump(mode="json")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost", follow_redirects=True
        ) as client:
            assert (await client.post("/v1/query", json=payload)).json() == expected
            rpc = {
                "jsonrpc": "2.0",
                "id": "directory",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "directory-request",
                        "role": "ROLE_USER",
                        "parts": [{"data": payload}],
                    }
                },
            }
            response = (await client.post("/", json=rpc, headers={"A2A-Version": "1.0"})).json()
            assert response["result"]["message"]["parts"][1]["data"] == expected
            rpc["params"]["message"]["parts"] = [{"text": "List inference tools"}]
            response = (await client.post("/", json=rpc, headers={"A2A-Version": "1.0"})).json()
            assert all(
                "inference" in t["disciplines"]
                for t in response["result"]["message"]["parts"][1]["data"]["data"]["items"]
            )
            async with streamable_http_client("http://localhost/mcp/", http_client=client) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    assert len((await session.list_tools()).tools) == 1
                    result = await session.call_tool("agenteng", {"request": payload})
                    assert not result.isError and result.structuredContent == expected
            card = (await client.get("/.well-known/agent-card.json")).json()
            assert "agenteng-tools" in {s["id"] for s in card["skills"]}


@pytest.mark.asyncio
async def test_crawlable_tools_feed_and_safe_pages(service):
    app = create_app(service)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            page = await client.get("/tools?discipline=memory&limit=2")
            assert page.status_code == 200 and "Next page" in page.text
            assert "discipline=memory" in page.text and "offset=2" in page.text
            assert (await client.get("/tools/langgraph")).status_code == 200
            assert (await client.get("/tools/unknown")).status_code == 404
            assert (await client.get("/tools?offset=-1")).status_code == 422
            assert (await client.get("/tools?category=")).status_code == 422
            feed = await client.get("/tools.json")
            assert len(feed.json()["tools"]) == 456
            assert feed.headers["etag"] == 'W/"' + service.tool_directory.version + '"'
            assert "/tools/langgraph" in (await client.get("/sitemap.xml")).text
            assert 'operation":"tools' in (await client.get("/llms.txt")).text
    from agenteng.tool_pages import tool_page

    request = Request(operation="tool", tool_id="langgraph")
    result = service.lookup(request)
    result.data["tool"]["name"] = '</script><script>alert("x")</script>'
    assert "</script><script>alert" not in tool_page(service, result, request)


def snapshot(entries):
    return json.dumps({"updatedAt": "2026-10-04T06:40:51Z", "tools": entries}).encode()


def entry(tid="example", **kwargs):
    return {
        "id": tid,
        "name": "Example",
        "category": "Agent Frameworks",
        "websiteUrl": "https://example.org",
        **kwargs,
    }


def test_importer_projects_only_facts_and_validates_aliases():
    content = snapshot(
        [entry(description="SECRET MARKETING CLAIM", trending=True, githubStars=999999)]
    )
    directory = normalize_snapshot(content, "a" * 40)
    assert "SECRET MARKETING CLAIM" not in directory.model_dump_json()
    assert "githubStars" not in directory.model_dump_json()
    for entries in [
        [entry(), entry()],
        [entry(category="Unreviewed")],
        [entry(websiteUrl="javascript:alert(1)")],
        [entry(websiteUrl="https://user:secret@example.org")],
        [entry(name="bad\x1b[31m")],
        [entry(id="bad/id")],
    ]:
        with pytest.raises((ValueError, ValidationError)):
            normalize_snapshot(snapshot(entries), "a" * 40)
    invalid = load_tool_directory().model_dump(mode="json")
    invalid["tools"].append(invalid["tools"][0])
    with pytest.raises(ValidationError):
        ToolDirectory.model_validate(invalid)


def test_import_command_keeps_last_valid_bundle_on_failure(tmp_path):
    source = tmp_path / "source.json"
    output = tmp_path / "tools.json"
    output.write_text("LAST VALID BUNDLE")
    source.write_text("not JSON")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/import-tools.py",
            str(source),
            "--commit",
            "a" * 40,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and output.read_text() == "LAST VALID BUNDLE"
    source.write_bytes(snapshot([entry()]))
    result = subprocess.run(
        [
            sys.executable,
            "scripts/import-tools.py",
            str(source),
            "--commit",
            "a" * 40,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert len(ToolDirectory.model_validate_json(output.read_text()).tools) == 1
