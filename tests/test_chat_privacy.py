import json

import httpx
import pytest

from agenteng.chat_privacy import PRIVACY_REPLY, has_sensitive_input
from agenteng.config import Settings
from agenteng.models import Request
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
