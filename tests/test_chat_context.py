import json

import httpx
import pytest

from agenteng.chat_context import chat_fallback
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.service import Service


@pytest.mark.parametrize(
    "question,word",
    [
        ("What is MCP?", "Model Context Protocol"),
        ("Explain A2A", "Agent2Agent"),
        ("What does ACP mean?", "Agent Client Protocol"),
    ],
)
@pytest.mark.asyncio
async def test_protocol_basics_answer_question_when_provider_is_unavailable(question, word):
    class Down:
        def complete(self, *args, **kwargs):
            raise httpx.ReadTimeout("synthetic outage")

    service = Service(Settings(enable_chat=True), provider=Down())
    result = await service.execute(Request(operation="chat", query=question))
    assert word in result.answer and result.engine == "lookup"
    assert result.data == {} and result.sources
    assert all(source.id.startswith("protocol-") for source in result.sources)
    assert result.usage["fallback_reason"] == "provider_unavailable"


@pytest.mark.asyncio
async def test_greeting_uses_no_model_or_irrelevant_event_cards():
    class Unexpected:
        def complete(self, *args, **kwargs):
            pytest.fail("Greeting should need no provider")

    result = await Service(Settings(enable_chat=True), provider=Unexpected()).execute(
        Request(operation="chat", query="Hi!")
    )
    assert "Hi! I'm AgentEng" in result.answer
    assert result.data == {} and result.sources == []


def test_protocol_comparison_does_not_list_unrelated_faqs():
    result = chat_fallback(
        Service(Settings()),
        Request(operation="chat", query="What's the difference between MCP and A2A?"),
    )
    assert "Model Context Protocol" in result.answer and "Agent2Agent" in result.answer
    assert {source.id for source in result.sources} == {"protocol-mcp", "protocol-a2a"}
    assert result.data == {}


def test_followup_retains_previous_question_in_static_fallback():
    request = Request(
        operation="chat",
        query="Tell me more",
        history=[{"role": "user", "content": "What is ACP?"}],
    )
    result = chat_fallback(Service(Settings()), request)
    assert "Agent Client Protocol" in result.answer


def test_mcp_speaker_request_keeps_event_lookup():
    request = Request(operation="chat", query="Which speakers are talking about MCP in London?")
    service = Service(Settings())
    result = chat_fallback(service, request)
    assert result.data and all("name" in speaker for speaker in result.data)
    assert all(not source.id.startswith("protocol-") for source in result.sources)


@pytest.mark.asyncio
async def test_last_faq_lookup_cannot_replace_cards_from_cited_speakers():
    class Provider:
        calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "faq-check",
                                "function": {
                                    "name": "lookup_public",
                                    "arguments": '{"operation":"faq","limit":2}',
                                },
                            }
                        ]
                    }
                }
            initial = json.loads(messages[1]["content"])
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "answer": "Here are the published speakers.",
                            "source_ids": [
                                source["source_id"]
                                for source in initial["published_lookup"]["sources"]
                            ],
                        }
                    )
                }
            }

    service = Service(Settings(enable_chat=True), provider=Provider())
    request = Request(operation="chat", query="Who's speaking in London?")
    result = await service.execute(request)
    assert result.engine == "chat"
    assert result.data == service.lookup(request).data
    assert all("name" in speaker and "question" not in speaker for speaker in result.data)


@pytest.mark.asyncio
async def test_protocol_citation_has_no_unrelated_initial_cards_and_accepts_fenced_json():
    class Provider:
        def complete(self, messages, **kwargs):
            assert "protocol_basics" in json.loads(messages[1]["content"])
            return {
                "message": {
                    "content": '```json\n{"answer":"MCP connects AI applications to tools and data.","source_ids":["protocol-mcp"]}\n```'
                }
            }

    result = await Service(Settings(enable_chat=True), provider=Provider()).execute(
        Request(operation="chat", query="What is MCP?")
    )
    assert result.engine == "chat" and result.data == {}
    assert [source.id for source in result.sources] == ["protocol-mcp"]


@pytest.mark.asyncio
async def test_fenced_output_still_rejects_unknown_citations():
    class Provider:
        def complete(self, *args, **kwargs):
            return {
                "message": {
                    "content": '```json\n{"answer":"Invented answer","source_ids":["private-record"]}\n```'
                }
            }

    result = await Service(Settings(enable_chat=True), provider=Provider()).execute(
        Request(operation="chat", query="What is MCP?")
    )
    assert result.engine == "lookup" and result.usage["fallback_reason"] == "invalid_response"
    assert "Invented answer" not in result.answer
