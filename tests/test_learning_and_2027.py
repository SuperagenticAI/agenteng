"""Tests for 2027 conferences, offline 14-discipline learning hub, and modern connect clients."""

from __future__ import annotations

import json
import re

import pytest
from click.testing import CliRunner

from agenteng.cli import main
from agenteng.models import Request
from agenteng.output import make_console
from agenteng.render import render_result
from agenteng.service import Service

SITE = "https://agentengineering.world"


def run_cli(*args: str):
    runner = CliRunner()
    return runner.invoke(main, list(args), env={"AGENTENG_OUTPUT": "json"})


def test_london_2027_and_sf_2027_in_catalogue_and_cli():
    service = Service()
    london27 = service.events["agenteng-london-2027"]
    assert london27.date == "2027-02-17"
    assert london27.city == "London"
    assert "Everyman Canary Wharf" in london27.venue
    assert london27.registration_status == "coming_soon"
    assert london27.offers == []
    assert london27.registration_url is None
    assert str(london27.page_url) == f"{SITE}/london-2027"
    # Verify "limited spaces" and zero "100" capacity wording or ticket prices
    london27_json = json.dumps(service.event_data(london27))
    assert "limited spaces" in london27_json.casefold()
    assert not re.search(
        r"(?:~|around\s+)?100\s+(?:engineers|attendees|builders)", london27_json, re.I
    )
    assert "\u2014" not in london27_json

    sf27 = service.events["agenteng-sf-2027"]
    assert sf27.date == "2027-06-29"
    assert sf27.city == "San Francisco"
    assert sf27.registration_status == "coming_soon"
    assert str(sf27.page_url) == f"{SITE}/san-francisco"

    # Aliases and website shortcuts
    for args in (
        ("event", "london-2027"),
        ("event", "--london-2027"),
        ("conference", "--overview", "--london-2027"),
        ("edition", "--builders"),
    ):
        res = run_cli(*args)
        assert res.exit_code == 0, (args, res.output)
        payload = json.loads(res.output)
        assert payload["data"][0]["id"] == "agenteng-london-2027"

    # Tickets coming soon (zero prices / offers)
    tickets = json.loads(run_cli("tickets", "london-2027").output)
    assert tickets["status"] == "ok"
    assert tickets["data"]["registration_status"] == "coming_soon"
    assert tickets["data"]["current_offers"] == []
    assert tickets["data"]["published_offers"] == []
    assert tickets["data"]["page_url"] == f"{SITE}/london-2027"
    assert "£" not in tickets["answer"]

    # FAQs for 2027 editions
    l27_faqs = json.loads(run_cli("faq", "--event", "london-2027").output)
    assert l27_faqs["status"] == "ok"
    assert any(f["event_id"] == "agenteng-london-2027" for f in l27_faqs["data"])
    sf27_faqs = json.loads(run_cli("faq", "--event", "sf-2027").output)
    assert sf27_faqs["status"] == "ok"
    assert any(f["event_id"] == "agenteng-sf-2027" for f in sf27_faqs["data"])


def test_learning_hub_overview_and_disciplines():
    service = Service()

    overview = service.lookup(Request(operation="learn"))
    assert overview.status == "ok"
    assert len(overview.data["disciplines"]) == 14
    assert {c["id"] for c in overview.data["upcoming_conferences"]} == {
        "agenteng-london-2027",
        "agenteng-sf-2027",
    }

    for disc in ("harness", "protocol", "memory", "factory", "decision"):
        res = service.lookup(Request(operation="learn", discipline=disc))
        assert res.status == "ok", disc
        assert res.data["discipline"]["id"] == disc
        assert res.data["discipline"]["primitives"]
        assert res.data["discipline"]["practices"]
        assert res.data["website"] == SITE
        assert f"{SITE}/london-2027" in res.answer

        console = make_console(record=True, width=100)
        render_result(res, "learn", console)
        rendered = console.export_text()
        assert res.data["discipline"]["title"] in rendered
        assert "\u2014" not in rendered

    # Render overview cleanly
    console = make_console(record=True, width=100)
    render_result(overview, "learn", console)
    assert "Agent Engineering Learning Hub" in console.export_text()

    # CLI JSON & ask intent routing
    cli_res = run_cli("learn", "harness")
    assert cli_res.exit_code == 0, cli_res.output
    assert json.loads(cli_res.output)["data"]["discipline"]["id"] == "harness"

    asked = service.lookup(Request(operation="ask", query="Learn harness engineering practices"))
    assert asked.status == "ok"
    assert asked.data["discipline"]["id"] == "harness"


def test_tools_factory_and_decision_point_to_learn():
    for disc in ("factory", "decision"):
        res = run_cli("tools", "--discipline", disc)
        assert res.exit_code == 0, (disc, res.output)
        body = json.loads(res.output)
        assert body["status"] == "ok"
        assert body["data"]["total"] == 0
        assert f"agenteng learn {disc}" in body["answer"]


@pytest.mark.parametrize(
    "client",
    ["all", "cli", "windsurf", "vscode", "gemini-cli", "opencode", "cline"],
)
def test_modern_connect_clients(client: str):
    res = run_cli("connect", client)
    assert res.exit_code == 0, (client, res.output)
    assert "agenteng" in res.output.casefold()
    assert "\u2014" not in res.output


def test_connect_protocol_all_and_a2a_learn_skill():
    res = run_cli("connect", "--protocol", "all")
    assert res.exit_code == 0, res.output
    assert "A2A" in res.output and "MCP" in res.output and "ACP" in res.output

    from starlette.testclient import TestClient

    from agenteng.server import create_app

    with TestClient(create_app(), base_url="https://a2a.agentengineering.world") as client:
        card = client.get("/.well-known/agent-card.json").json()
        learn_skill = next(s for s in card["skills"] if s["id"] == "agenteng-learn")
        for ex in learn_skill["examples"]:
            Request.model_validate_json(ex)

        resp = client.post("/v1/query", json={"operation": "learn", "discipline": "protocol"})
        assert resp.status_code == 200
        assert resp.json()["data"]["discipline"]["id"] == "protocol"

        llms = client.get("/llms.txt").text
        assert "London 2027" in llms and "San Francisco 2027" in llms and "learn" in llms
