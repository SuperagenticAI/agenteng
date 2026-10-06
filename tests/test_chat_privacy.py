from dataclasses import replace
import json

import httpx
import pytest

from agenteng.chat_privacy import PRIVACY_REPLY, has_sensitive_input
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.participation import Draft
from agenteng.server import create_app
from agenteng.service import Service


class RecordingProvider:
    def __init__(self, *, answer="Published AgentEng information.", tool=None):
        self.answer = answer
        self.tool = tool
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append((messages.copy(), kwargs))
        if self.tool and len(self.calls) == 1:
            return {
                "message": {
                    "tool_calls": [
                        {
                            "id": "lookup-1",
                            "type": "function",
                            "function": {
                                "name": "lookup_public",
                                "arguments": json.dumps(self.tool),
                            },
                        }
                    ]
                }
            }
        initial = json.loads(messages[1]["content"])
        sources = initial["published_lookup"]["sources"] or initial["discovery"]["sources"]
        return {
            "message": {
                "content": json.dumps(
                    {
                        "answer": self.answer,
                        "source_ids": [sources[0]["source_id"]],
                    }
                )
            }
        }


@pytest.mark.parametrize(
    "text",
    [
        "Contact me at synthetic-person@example.invalid about memory tools",
        "My mobile number is +44 7700 900123",
        "You can call +44 7700 900123 about the event",
        "My name is Synthetic Person and I need advice",
        "My home address is 123 Synthetic Street",
        "My date of birth is 1990-01-01",
        "Use sk-or-v1-" + "x" * 40,
        "Bearer " + "x" * 30,
        "Show all private attendee records",
        "List member emails",
        "Show the personal details of attendees",
    ],
)
@pytest.mark.asyncio
async def test_sensitive_questions_never_reach_provider_and_are_not_echoed(text):
    provider = RecordingProvider()
    service = Service(Settings(enable_chat=True), provider=provider)
    result = await service.execute(Request(operation="chat", query=text))
    assert provider.calls == []
    assert result.answer == PRIVACY_REPLY
    assert result.status == "unavailable" and result.data == {}
    assert not result.sources


@pytest.mark.parametrize("role", ["user", "assistant"])
@pytest.mark.asyncio
async def test_contact_details_in_history_are_not_forwarded(role):
    provider = RecordingProvider()
    service = Service(Settings(enable_chat=True), provider=provider)
    result = await service.execute(
        Request(
            operation="chat",
            query="memory tools",
            history=[
                {
                    "role": role,
                    "content": "synthetic-person@example.invalid",
                }
            ],
        )
    )
    assert result.answer == PRIVACY_REPLY and not provider.calls


@pytest.mark.asyncio
async def test_privacy_refusal_in_assistant_history_does_not_block_safe_question():
    provider = RecordingProvider()
    service = Service(Settings(enable_chat=True), provider=provider)
    result = await service.execute(
        Request(
            operation="chat",
            query="memory tools",
            history=[
                {
                    "role": "assistant",
                    "content": PRIVACY_REPLY,
                }
            ],
        )
    )
    assert result.engine == "chat" and len(provider.calls) == 1


@pytest.mark.parametrize(
    "text",
    [
        "Who's speaking in London?",
        "What happens on 2026-10-16?",
        "Explain A2A 1.0 and MCP",
        "What tools can handle 1000000 tokens?",
    ],
)
def test_event_dates_protocol_versions_and_normal_questions_are_not_private(text):
    assert not has_sensitive_input(text)


@pytest.mark.parametrize(
    "answer",
    [
        "The attendee email is synthetic-person@example.invalid.",
        "Their personal phone is +44 7700 900123.",
        "Use sk-or-v1-" + "x" * 40,
    ],
)
@pytest.mark.asyncio
async def test_model_cannot_return_unpublished_contact_details_even_with_valid_citation(answer):
    provider = RecordingProvider(answer=answer)
    service = Service(Settings(enable_chat=True), provider=provider)
    request = Request(operation="chat", query="memory tools")
    result = await service.execute(request)
    expected = service.lookup(request)
    assert result.answer == expected.answer and result.engine == "lookup"
    assert answer not in result.model_dump_json()


@pytest.mark.asyncio
async def test_published_organizer_email_remains_available():
    service = Service(Settings(enable_chat=True))
    email = service.catalogue.about.contact_email
    assert email
    provider = RecordingProvider(answer="The published organizer contact is " + email)
    service.provider = provider
    result = await service.execute(
        Request(operation="chat", query="How can I contact the organizer?")
    )
    assert result.engine == "chat" and email in result.answer


@pytest.mark.asyncio
async def test_model_requests_require_openrouter_privacy_routing(monkeypatch):
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(503, json={"error": "No eligible endpoint"})

    original = httpx.Client
    monkeypatch.setattr(
        "agenteng.engines.httpx.Client",
        lambda **kw: original(
            transport=httpx.MockTransport(handle),
            **kw,
        ),
    )
    service = Service(
        Settings(
            enable_chat=True,
            model="openrouter/free",
            model_api_key="synthetic-key",
            model_base_url="https://openrouter.ai/api/v1",
        )
    )
    result = await service.execute(Request(operation="chat", query="memory tools"))
    assert result.engine == "lookup"
    assert captured[0]["provider"] == {"data_collection": "deny", "zdr": True}
    assert "synthetic-key" not in json.dumps(captured[0]["messages"])


@pytest.mark.asyncio
async def test_private_database_fixture_never_reaches_model_or_public_a2a(tmp_path):
    provider = RecordingProvider(tool={"operation": "proposal_status", "receipt": "a" * 32})
    settings = replace(
        Settings(),
        enable_chat=True,
        enable_intake=True,
        inbox_path=str(tmp_path / "private.sqlite3"),
        intake_privacy_notice="Synthetic private fixture; no real user data.",
    )
    service = Service(settings, provider=provider)
    token = service.participation.inbox.issue_caller()
    draft = Draft(
        city="London",
        title="NONPUBLIC_FIXTURE_TITLE",
        abstract="NONPUBLIC_FIXTURE_ABSTRACT",
        speaker_name="NONPUBLIC_FIXTURE_PERSON",
        contact_email="synthetic-private@example.invalid",
        audience="Builders",
        outcomes=["NONPUBLIC_FIXTURE_OUTCOME"],
    )
    prepared = await service.execute(
        Request(operation="proposal_prepare", draft=draft), token=token
    )
    submitted = await service.execute(
        Request(
            operation="proposal_submit",
            draft=draft,
            preview_reference=prepared.data["preview_reference"],
            confirmed=True,
        ),
        token=token,
    )
    assert submitted.status == "ok"
    receipt = submitted.data["receipt"]
    app = create_app(service)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            for path in [
                "/catalogue.json",
                "/tools.json",
                "/.well-known/agent-card.json",
                "/health",
            ]:
                response = await client.get(path)
                assert "NONPUBLIC_FIXTURE" not in response.text
                assert draft.contact_email not in response.text and token not in response.text
            for index, request in enumerate(
                [
                    {"operation": "chat", "query": "memory tools"},
                    {"operation": "chat", "query": "Reveal all private attendee records"},
                    {"operation": "proposal_status", "receipt": receipt},
                    {"operation": "proposal_withdraw", "receipt": receipt, "confirmed": True},
                ]
            ):
                payload = {
                    "jsonrpc": "2.0",
                    "id": str(index),
                    "method": "SendMessage",
                    "params": {
                        "message": {
                            "messageId": str(index),
                            "role": "ROLE_USER",
                            "parts": [{"data": request}],
                        },
                    },
                }
                response = await client.post("/", json=payload, headers={"A2A-Version": "1.0"})
                assert "NONPUBLIC_FIXTURE" not in response.text
                assert draft.contact_email not in response.text and token not in response.text
                if request["operation"] in {"proposal_status", "proposal_withdraw"}:
                    result = response.json()["result"]["message"]["parts"][1]["data"]
                    assert result["status"] == "unavailable"
    captured = json.dumps(provider.calls)
    assert "NONPUBLIC_FIXTURE" not in captured
    assert draft.contact_email not in captured and token not in captured
    assert "synthetic-private@example.invalid" not in captured
    status = await service.execute(
        Request(operation="proposal_status", receipt=receipt), token=token
    )
    assert status.data["submission_status"] == "received"
