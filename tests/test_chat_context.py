import json
from datetime import UTC, datetime

import httpx
import pytest

from agenteng.chat_context import chat_fallback
from agenteng.config import Settings
from agenteng.models import Request
from agenteng.service import Service


@pytest.mark.parametrize(
    "question",
    [
        "Who us talking about memory engineering",
        "Who is talking about memory engineering?",
        "Who's speaking about memory in London?",
        "Who will be presenting on memory?",
        "When is the memory talk?",
        "What time does Tobie Morgan Hitchcock's session start?",
        "Which talks cover memory?",
    ],
)
@pytest.mark.asyncio
async def test_published_topic_answers_need_no_ai_even_during_provider_cooldown(question):
    from agenteng.public_chat import PublicChat

    class Unexpected:
        def complete(self, *args, **kwargs):
            pytest.fail("Published programme questions should need no provider")

    service = Service(
        Settings(enable_chat=True),
        provider=Unexpected(),
        clock=lambda: datetime(2026, 10, 7, tzinfo=UTC),
    )
    service._chat_runtime = PublicChat(service)
    service._chat_runtime.cooldown_until = float("inf")
    result = await service.execute(Request(operation="chat", query=question))
    assert result.status == "ok" and result.engine == "lookup"
    assert "Tobie Morgan Hitchcock" in result.answer
    assert "SurrealDB" in result.answer and "Memory Is Not a Bigger Context Window" in result.answer
    assert "16 October 2026" in result.answer and "15:50–16:20" in result.answer
    assert result.data and result.sources
    assert not result.usage or "fallback_reason" not in result.usage
    # Shared lookup supports CLI, MCP and structured A2A requests as well.
    assert service.lookup(Request(operation="ask", query=question)).answer == result.answer


def test_topic_answers_exclude_cancelled_events_and_respect_explicit_filters():
    from agenteng.chat_context import published_talk_answer

    service = Service(clock=lambda: datetime(2026, 10, 7, tzinfo=UTC))
    question = "Who is talking about memory engineering?"
    assert (
        published_talk_answer(
            service, Request(operation="ask", query=question, city="San Francisco")
        ).status
        == "not_found"
    )
    service.catalogue = service.catalogue.model_copy(
        update={
            "events": [
                event.model_copy(update={"cancelled": True}) for event in service.catalogue.events
            ]
        }
    )
    assert (
        published_talk_answer(service, Request(operation="ask", query=question)).status
        == "not_found"
    )


@pytest.mark.parametrize(
    "question",
    [
        "Who is talking about memory in San Francisco?",
        "Who is talking about nuclear reactors?",
    ],
)
@pytest.mark.asyncio
async def test_topic_answers_do_not_invent_talks_or_cross_city_filters(question):
    result = await Service().execute(Request(operation="chat", query=question))
    assert result.status == "not_found" and result.data == []
    assert "Tobie" not in result.answer


@pytest.mark.asyncio
async def test_memory_question_over_the_browser_a2a_transport():
    from agenteng.server import create_app

    app = create_app(Service())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client,
    ):
        response = await client.post(
            "/",
            headers={"A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "memory-question",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "memory-question",
                        "role": "ROLE_USER",
                        "parts": [
                            {
                                "data": {
                                    "operation": "chat",
                                    "query": "Who us talking about memory engineering",
                                }
                            }
                        ],
                    }
                },
            },
        )
    result = response.json()["result"]["message"]["parts"][1]["data"]
    assert result["status"] == "ok" and "Tobie Morgan Hitchcock" in result["answer"]
    assert result["data"][0]["name"] == "Tobie Morgan Hitchcock"
    assert result["sources"] and not result["usage"]


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


@pytest.mark.parametrize("question", ["How are you?", "Hi there!", "Hello AgentEng", "Thanks!"])
@pytest.mark.asyncio
async def test_small_talk_never_searches_faq_or_calls_provider(question):
    class Unexpected:
        def complete(self, *args, **kwargs):
            pytest.fail("Small talk must not need inference")

    result = await Service(Settings(enable_chat=True), provider=Unexpected()).execute(
        Request(operation="chat", query=question)
    )
    assert result.status == "ok" and result.data == {} and result.sources == []
    assert "source excerpts" not in result.answer and "FAQ" not in result.answer


@pytest.mark.parametrize("question", ["Who are you?", "What can you do?", "What is AgentEng?"])
def test_identity_fallback_explains_agent_infrastructure_without_event_dump(question):
    result = chat_fallback(Service(Settings()), Request(operation="chat", query=question))
    assert "open-source agent infrastructure" in result.answer
    assert "MCP" in result.answer and "A2A" in result.answer and "ACP" in result.answer
    assert result.data == {} and [source.id for source in result.sources] == ["agenteng-tooling"]


def test_agent_engineering_definition_is_a_direct_public_answer():
    result = chat_fallback(
        Service(Settings()), Request(operation="chat", query="What is agent engineering?")
    )
    assert "designing, building, evaluating" in result.answer
    assert result.data == {} and [source.id for source in result.sources] == ["about"]


def test_conversational_filler_cannot_match_unrelated_faqs():
    result = chat_fallback(
        Service(Settings()), Request(operation="chat", query="Could you give me some more?")
    )
    assert result.status == "not_found" and result.data == {} and result.sources == []


def test_practical_attendance_question_still_gets_published_invoice_answer():
    result = chat_fallback(
        Service(Settings()), Request(operation="chat", query="How do I get an invoice?")
    )
    assert "Download Invoice" in result.answer
    assert result.sources and any(source.id == "faq-6" for source in result.sources)
    assert result.data == {}


@pytest.mark.parametrize(
    ("question", "source_id", "policy"),
    [
        (
            "Do you cover travel and accommodation costs?",
            "faq-20",
            "We cannot cover travel or accommodation costs for speakers or attendees.",
        ),
        (
            "Do you cover travel costs for speakers?",
            "faq-20",
            "We cannot cover travel or accommodation costs for speakers or attendees.",
        ),
        (
            "Can I get a visa invitation letter?",
            "faq-21",
            "we do not provide visa invitation letters or handle visa-related matters.",
        ),
    ],
)
def test_travel_and_visa_questions_use_published_policy_without_a_model(
    question, source_id, policy
):
    result = chat_fallback(Service(Settings()), Request(operation="chat", query=question))
    assert result.status == "ok"
    assert policy in result.answer
    assert source_id in {source.id for source in result.sources}
    assert result.engine == "lookup"


@pytest.mark.asyncio
async def test_supplied_protocol_evidence_requests_final_json_without_tools():
    class Provider:
        def complete(self, messages, **kwargs):
            assert kwargs["tools"] is None
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "answer": "MCP connects agents to tools and data.",
                            "source_ids": ["protocol-mcp"],
                        }
                    )
                }
            }

    result = await Service(Settings(enable_chat=True), provider=Provider()).execute(
        Request(operation="chat", query="What is MCP?")
    )
    assert result.engine == "chat" and result.data == {}


@pytest.mark.asyncio
async def test_model_faq_call_is_rejected_for_non_attendance_question():
    class Provider:
        calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            if self.calls == 1:
                assert (
                    "faq"
                    not in kwargs["tools"][0]["function"]["parameters"]["properties"]["operation"][
                        "enum"
                    ]
                )
                return {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "irrelevant-faq",
                                "function": {
                                    "name": "lookup_public",
                                    "arguments": '{"operation":"faq"}',
                                },
                            }
                        ]
                    }
                }
            tool_result = json.loads(messages[-1]["content"])
            assert "error" in tool_result and "data" not in tool_result
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "answer": "I can help explain MCP, which connects AI applications to tools and data.",
                            "source_ids": ["protocol-mcp"],
                        }
                    )
                }
            }

    result = await Service(Settings(enable_chat=True), provider=Provider()).execute(
        Request(operation="chat", query="Can you help me with zyzzyva?")
    )
    assert result.engine == "chat" and result.data == {}
    assert all(not source.id.startswith("faq-") for source in result.sources)
