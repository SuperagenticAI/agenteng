"""Public transports reject personal features without creating local state."""

import json

import httpx
import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from agenteng.cli import main
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.server import create_app
from agenteng.service import Service

REMOVED = [
    "save",
    "unsave",
    "my_agenda",
    "plan",
    "proposal_draft",
    "proposal_preview",
    "proposal_export",
    "proposal_prepare",
    "proposal_submit",
    "proposal_status",
    "proposal_withdraw",
]


@pytest.mark.parametrize("operation", REMOVED)
def test_personal_operations_not_in_contract(operation):
    with pytest.raises(ValidationError):
        Request.model_validate({"operation": operation})


@pytest.mark.parametrize(
    "command", ["save", "unsave", "my-agenda", "plan", "proposal", "engage", "inbox"]
)
def test_personal_commands_removed(command):
    result = CliRunner().invoke(main, [command])
    assert result.exit_code == 2
    assert "No such command" in result.output


@pytest.mark.asyncio
async def test_http_and_a2a_reject_private_fields_without_echoing_or_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTENG_CONFIG_DIR", str(tmp_path / "unused"))
    # Old settings cannot resurrect private storage.
    monkeypatch.setenv("AGENTENG_ENABLE_INTAKE", "1")
    monkeypatch.setenv("AGENTENG_INBOX", str(tmp_path / "inbox.sqlite3"))
    app = create_app(Service(Settings.from_env()))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            for operation in REMOVED:
                request = {
                    "operation": operation,
                    "contact_email": "PRIVATE_SENTINEL@example.invalid",
                }
                response = await client.post("/v1/query", json=request)
                assert response.status_code == 422
                assert "PRIVATE_SENTINEL" not in response.text
                response = await client.post(
                    "/",
                    headers={"A2A-Version": "1.0"},
                    json={
                        "jsonrpc": "2.0",
                        "id": operation,
                        "method": "SendMessage",
                        "params": {
                            "message": {
                                "messageId": operation,
                                "role": "ROLE_USER",
                                "parts": [{"data": request}],
                            }
                        },
                    },
                )
                assert "error" in response.json()
                assert "PRIVATE_SENTINEL" not in response.text
            card = (await client.get("/.well-known/agent-card.json")).json()
            assert "agenteng-participation" not in json.dumps(card)
            assert not card.get("securitySchemes")
            assert (await client.get("/health")).json()["private_intake_enabled"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("operation", ["now", "next", "live"])
def test_cancelled_event_cannot_advertise_running_sessions(service, operation):
    service.events["agenteng-london-2026"].cancelled = True
    result = service.lookup(
        Request(
            operation=operation, event_id="agenteng-london-2026", at="2026-10-16T09:20:00+01:00"
        )
    )
    assert result.status == "unavailable"
    assert "cancelled" in result.answer
    assert not result.data.get("session") and not result.data.get("current")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query", ["What time do doors open for London?", "When should I arrive for London?"]
)
async def test_public_arrival_answers_work_without_model(service, query):
    result = await service.execute(Request(operation="chat", query=query))
    assert result.engine == "lookup"
    assert "08:00" in result.answer and "Everyman" in result.answer
    assert result.sources


def test_question_submission_does_not_route_to_proposals(service):
    result = service.lookup(
        Request(operation="ask", query="How do I submit a question during a talk?")
    )
    assert "propose" not in result.answer and "talk or event idea" not in result.answer
