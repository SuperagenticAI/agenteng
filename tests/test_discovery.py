import json
import re
from xml.etree import ElementTree

from click.testing import CliRunner
import httpx
import pytest

from agenteng.cli import main
from agenteng.discovery import event_schema, html_page, validate_origin
from agenteng.models import Request
from agenteng.server import create_app


def test_focus_identity_and_source_backed_policy(service):
    result = service.lookup(Request(operation="discover"))
    assert result.data["cities"] == ["London", "San Francisco"]
    assert [e["id"] for e in result.data["events"]] == [
        "agenteng-london-2026",
        "sf-code-engineering-2026",
    ]
    assert "Agent Engineering Conference" in result.data["aliases"]
    assert service.events["agenteng-london-2026"].speaker_submission_status == "invited_only"
    assert "london-participation-policy" in service.events["agenteng-london-2026"].source_ids
    for name in ["AgentEng", "Agent Eng", "Agent Engineering HQ", "Agent Engineering Conference"]:
        assert (
            service.lookup(Request(operation="ask", query=name)).data["name"]
            == "Agent Engineering HQ"
        )
    london = service.lookup(
        Request(operation="ask", query="Find the next Agent Engineering Conference in London")
    )
    assert len(london.data["events"]) == 1 and london.data["events"][0]["city"] == "London"
    sf = service.lookup(Request(operation="ask", query="SF agenda"))
    assert sf.data and all(x["event_id"] == "sf-code-engineering-2026" for x in sf.data)


def test_structured_data_preserves_published_names_dates_and_html_safety(service):
    event = service.events["sf-code-engineering-2026"]
    schema = event_schema(service, event)
    assert schema["name"] == event.title
    assert schema["startDate"] == "2026-10-27T18:00:00-07:00"
    assert "endDate" not in schema and "offers" not in schema
    dangerous = event.model_copy(update={"title": '</script><script>alert("x")</script>'})
    page = html_page(service, dangerous)
    assert "</script><script>alert" not in page
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', page).group(1)
    assert json.loads(raw)["name"] == dangerous.title


@pytest.mark.asyncio
async def test_crawlable_routes_and_actual_event_links(service):
    app = create_app(service)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            homepage = await client.get("/")
            assert homepage.status_code == 200 and "Agent Engineering Conference" in homepage.text
            assert "London" in homepage.text and "San Francisco" in homepage.text
            llms = (await client.get("/llms.txt")).text
            assert "invited programme" in llms and "/.well-known/agent-card.json" in llms
            xml = ElementTree.fromstring((await client.get("/sitemap.xml")).text)
            urls = xml.findall("{*}url/{*}loc")
            assert len(urls) > 400
            for url in urls:
                path = url.text.removeprefix(service.settings.public_url)
                assert (await client.get(path)).status_code == 200
            assert (await client.get("/events/unknown")).status_code == 404
            feed = (await client.get("/events.json")).json()
            assert len(feed["data"]["events"]) == 2 and feed["sources"]


@pytest.mark.parametrize("client", ["codex", "claude-code", "cursor", "generic"])
def test_connection_instructions_for_local_and_remote_clients(client):
    runner = CliRunner()
    local = runner.invoke(main, ["connect", client])
    remote = runner.invoke(main, ["connect", client, "--transport", "http"])
    assert local.exit_code == remote.exit_code == 0
    assert "agenteng" in local.output and "https://a2a.agentengineering.world/mcp/" in remote.output
    if client in {"cursor", "generic"}:
        assert json.loads(remote.output)["mcpServers"]["agenteng"]["url"].endswith("/mcp/")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://user:password@example.org",
        "https://example.org/path",
        "https://example.org?token=private",
        "file:///tmp/server",
    ],
)
def test_remote_origins_reject_credentials_and_insecure_transport(url):
    with pytest.raises(ValueError):
        validate_origin(url)
