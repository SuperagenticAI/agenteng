"""Agent-to-Agent (A2A) Talks: AI-generated videos kept apart from the programme."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from click.testing import CliRunner
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agenteng.a2a import agent_card
from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.output import make_console
from agenteng.render import render_result
from agenteng.server import create_app
from agenteng.service import Service

DISCLAIMER = (
    "These videos are produced by the Agent Engineering team using AI. They are separate "
    "from the conference programme and are not created, reviewed or endorsed by our speakers."
)


@pytest.fixture
def service():
    return Service(Settings(), clock=lambda: datetime(2026, 10, 15, 13, tzinfo=UTC))


def test_catalogue_mirrors_the_published_page(service):
    page = service.catalogue.a2a_talks
    assert page.title == "Agent-to-Agent (A2A) Talks"
    assert str(page.url) == "https://agentengineering.world/agent-to-agent"
    assert page.disclaimer == DISCLAIMER
    assert len(page.videos) == 10
    assert [v.session for v in page.videos] == [f"{n:03d}" for n in range(1, 11)]
    assert all(v.duration == "00:30" and v.duration_sec == 30 for v in page.videos)
    assert all(str(v.url) == f"https://www.youtube.com/watch?v={v.youtube_id}" for v in page.videos)
    first, last = page.videos[0], page.videos[-1]
    assert (first.title, first.youtube_id, first.tag) == (
        "Coding Agent Engineering",
        "ZVYEIFYx-ME",
        "coding-agents",
    )
    assert (last.title, last.youtube_id, last.tag) == (
        "Memory Engineering",
        "tumzJBGV79U",
        "memory",
    )


def test_operation_returns_videos_with_the_exact_disclaimer(service):
    result = service.lookup(Request(operation="a2a-talks"))
    assert result.status == "ok"
    assert DISCLAIMER in result.answer
    assert result.data["disclaimer"] == DISCLAIMER
    assert result.data["ai_generated"] is True and result.data["part_of_programme"] is False
    assert len(result.data["videos"]) == 10
    assert [s.id for s in result.sources] == ["a2a-talks"]
    memory = service.lookup(Request(operation="a2a-talks", topic="memory"))
    assert [v["title"] for v in memory.data["videos"]] == ["Memory Engineering"]
    assert service.lookup(Request(operation="a2a-talks", topic="nope")).status == "not_found"


def test_videos_never_mix_into_speakers_talks_or_agenda(service):
    ids = {v.youtube_id for v in service.catalogue.a2a_talks.videos}
    titles = {v.title for v in service.catalogue.a2a_talks.videos}
    for op in ["speakers", "talks", "agenda"]:
        result = service.lookup(Request(operation=op, event_id="agenteng-london-2026"))
        text = json.dumps(result.model_dump(mode="json"))
        assert "a2a-talks" not in {s.id for s in result.sources}
        assert not any(i in text for i in ids), op
        assert not any(f'"{t}"' in text for t in titles), op
    for query in ["memory engineering talk", "Who is speaking about memory?", "What talks are on?"]:
        result = service.lookup(Request(operation="ask", query=query))
        assert "a2a-talks" not in {s.id for s in result.sources}, query
    assert not any(s.id.startswith("a2a-") for s in service.catalogue.speakers)
    assert not any(s.id.startswith("a2a-") for s in service.catalogue.sessions)


@pytest.mark.parametrize(
    "query",
    ["What are the A2A talks?", "Show me the Agent-to-Agent videos", "agent to agent talks"],
)
def test_ask_routes_named_a2a_questions(service, query):
    result = service.lookup(Request(operation="ask", query=query))
    assert [s.id for s in result.sources] == ["a2a-talks"]
    assert DISCLAIMER in result.answer


def test_cli_json_and_card():
    runner = CliRunner()
    out = runner.invoke(main, ["--json", "a2a-talks", "--topic", "security"])
    assert out.exit_code == 0, out.output
    data = json.loads(out.output)["data"]
    assert [v["title"] for v in data["videos"]] == ["Security Engineering"]
    shortcut = runner.invoke(main, ["--json", "--agent-to-agent"])
    assert len(json.loads(shortcut.output)["data"]["videos"]) == 10


def test_card_shows_disclaimer_and_no_json(service):
    console = make_console(record=True, width=120)
    render_result(service.lookup(Request(operation="a2a-talks")), "a2a-talks", console)
    text = console.export_text()
    assert "Agent-to-Agent (A2A) Talks" in text and "AI-generated" in text
    assert "endorsed by our speakers" in text
    assert "Memory Engineering" in text and "memory, 00:30" in text
    assert "youtu.be/tumzJBGV79U" in text
    assert '"videos"' not in text


def test_agent_card_skill(service):
    skills = {s.id: s for s in agent_card(service).skills}
    skill = skills["agenteng-a2a-talks"]
    assert skill.name == "Agent-to-Agent (A2A) Talks"
    assert DISCLAIMER in skill.description
    assert '{"operation":"a2a-talks"}' in skill.examples


@pytest.mark.asyncio
async def test_mcp_a2a_talks(service):
    app = create_app(service)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), follow_redirects=True) as http,
        streamable_http_client("http://localhost/mcp/", http_client=http) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        called = await session.call_tool("agenteng", {"request": {"operation": "a2a-talks"}})
        assert not called.isError
        assert called.structuredContent["data"]["disclaimer"] == DISCLAIMER
