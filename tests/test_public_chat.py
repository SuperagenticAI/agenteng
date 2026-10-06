import asyncio
from dataclasses import replace
import json
import threading
import time

import httpx
import pytest
from pydantic import ValidationError

from agenteng.config import Settings
from agenteng.models import Request
from agenteng.server import create_app
from agenteng.service import Service


class Provider:
    def __init__(self, *, failure=None, tool=None, invalid=False):
        self.calls = []
        self.failure = failure
        self.tool = tool
        self.invalid = invalid

    def complete(self, messages, **kwargs):
        self.calls.append((messages.copy(), kwargs))
        if self.failure:
            raise self.failure
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
        evidence = initial["published_lookup"]["sources"] or initial["discovery"]["sources"]
        if self.tool and messages[-1]["role"] == "tool":
            evidence = json.loads(messages[-1]["content"]).get("sources") or evidence
        return {
            "message": {
                "content": json.dumps(
                    {
                        "answer": "Explore these published AgentEng resources.",
                        "source_ids": ["invented" if self.invalid else evidence[0]["source_id"]],
                    }
                )
            },
            "usage": {"total_tokens": 30},
        }


def chat_service(provider, **settings):
    return Service(replace(Settings(), enable_chat=True, **settings), provider=provider)


@pytest.mark.asyncio
async def test_disabled_and_unconfigured_chat_matches_existing_lookup():
    for settings in [Settings(), Settings(enable_chat=True)]:
        service = Service(settings)
        request = Request(operation="chat", query="Who's speaking in London?")
        result = await service.execute(request)
        expected = service.lookup(Request(operation="ask", query=request.query))
        assert result.answer == expected.answer
        assert result.data == expected.data
        assert result.engine == "lookup"
    provider = Provider()
    service = Service(Settings(), provider=provider)
    assert (await service.execute(Request(operation="chat", query="memory"))).engine == "lookup"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_public_chat_synthesizes_with_bounded_history_and_citations():
    provider = Provider()
    service = chat_service(
        provider, model_api_key="not-for-the-model", operator_token="private-token"
    )
    request = Request(
        operation="chat",
        query="memory",
        history=[
            {"role": "user", "content": "What is AgentEng?"},
            {"role": "assistant", "content": "Published events and agent tooling."},
        ],
    )
    result = await service.execute(request)
    assert result.engine == "chat" and result.status == "ok"
    assert result.sources and result.usage["model_calls"] == 1
    payload = json.loads(provider.calls[0][0][1]["content"])
    assert payload["history"] == [turn.model_dump() for turn in request.history]
    assert len(provider.calls[0][0]) == 2
    wire = json.dumps(provider.calls)
    assert "not-for-the-model" not in wire and "private-token" not in wire
    # Opting into public chat never authorizes the operator-only engine.
    denied = await service.execute(Request(operation="ask", query="memory", engine="standard"))
    assert denied.status == "unavailable" and len(provider.calls) == 1


@pytest.mark.asyncio
async def test_model_can_choose_public_tool_directory_lookup():
    provider = Provider(tool={"operation": "tools", "discipline": "memory", "limit": 3})
    result = await chat_service(provider).execute(
        Request(operation="chat", query="Help me pick memory tools")
    )
    assert result.engine == "chat" and result.data["items"]
    assert len(provider.calls) == 2
    tool_reply = json.loads(provider.calls[1][0][-1]["content"])
    assert tool_reply["data"]["items"]
    assert result.sources[0].id == tool_reply["sources"][0]["source_id"]


@pytest.mark.parametrize(
    "operation", ["proposal_status", "proposal_submit", "save", "my_agenda", "chat"]
)
@pytest.mark.asyncio
async def test_model_cannot_read_private_intake_or_local_state(monkeypatch, operation):
    provider = Provider(tool={"operation": operation, "receipt": "a" * 32})
    service = chat_service(provider)
    monkeypatch.setattr(
        service.participation, "execute", lambda *args: pytest.fail("Private access")
    )
    result = await service.execute(Request(operation="chat", query="memory"))
    assert result.engine == "chat"
    tool_reply = json.loads(provider.calls[1][0][-1]["content"])
    assert tool_reply == {"error": "Use a supported public lookup with valid catalogue filters."}


@pytest.mark.asyncio
async def test_provider_wire_and_credit_rate_limit_outage_fallback(monkeypatch):
    original = httpx.Client
    for status in [402, 429, 503]:
        captured = []

        def handle(request):
            captured.append(request)
            return httpx.Response(status, json={"error": "SECRET_PROVIDER_DETAIL"})

        monkeypatch.setattr(
            "agenteng.engines.httpx.Client",
            lambda **kw: original(
                transport=httpx.MockTransport(handle),
                **kw,
            ),
        )
        service = chat_service(
            None,
            model="openrouter/free",
            model_api_key="test-secret",
            model_base_url="https://openrouter.ai/api/v1",
        )
        request = Request(operation="chat", query="Who's speaking in London?")
        expected = service.lookup(request)
        for _ in range(2):
            result = await service.execute(request)
            assert result.answer == expected.answer and result.data == expected.data
            assert result.engine == "lookup"
            assert "SECRET_PROVIDER_DETAIL" not in result.model_dump_json()
        assert len(captured) == 1  # Cooldown prevents repeatedly exhausting provider quota.
        assert str(captured[0].url) == "https://openrouter.ai/api/v1/chat/completions"
        assert captured[0].headers["authorization"] == "Bearer test-secret"
        assert json.loads(captured[0].content)["model"] == "openrouter/free"


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("private-error"), ValueError("bad JSON")])
@pytest.mark.asyncio
async def test_timeout_and_malformed_provider_output_return_lookup(failure):
    provider = Provider(failure=failure)
    service = chat_service(provider)
    request = Request(operation="chat", query="memory")
    result = await service.execute(request)
    expected = service.lookup(request)
    assert result.answer == expected.answer and result.sources == expected.sources
    assert result.engine == "lookup" and "private-error" not in result.answer


@pytest.mark.asyncio
async def test_bad_citations_and_busy_or_admission_limited_chat_return_lookup():
    provider = Provider(invalid=True)
    service = chat_service(provider)
    request = Request(operation="chat", query="memory")
    result = await service.execute(request)
    assert result.engine == "lookup"
    service._chat_runtime.cooldown_until = 0
    service._model_slot.acquire()
    try:
        assert (await service.execute(request)).engine == "lookup"
    finally:
        service._model_slot.release()
    service._chat_runtime.calls.extend([time.monotonic()] * 5)
    assert (await service.execute(request)).engine == "lookup"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_chat_resumes_model_calls_after_cooldown():
    provider = Provider(failure=httpx.ReadTimeout("provider down"))
    service = chat_service(provider)
    request = Request(operation="chat", query="memory")
    assert (await service.execute(request)).engine == "lookup"
    provider.failure = None
    assert (await service.execute(request)).engine == "lookup"
    service._chat_runtime.cooldown_until = time.monotonic() - 1
    assert (await service.execute(request)).engine == "chat"
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_slow_provider_returns_lookup_at_deadline_without_releasing_active_slot(monkeypatch):
    started, release = threading.Event(), threading.Event()
    real_wait_for = asyncio.wait_for

    class Blocking(Provider):
        def complete(self, messages, **kwargs):
            started.set()
            release.wait(2)
            return super().complete(messages, **kwargs)

    async def short_deadline(future, *, timeout):
        return await real_wait_for(future, timeout=0.05)

    monkeypatch.setattr("agenteng.public_chat.asyncio.wait_for", short_deadline)
    service = chat_service(Blocking())
    request = Request(operation="chat", query="memory")
    try:
        result = await service.execute(request)
        assert started.is_set() and result.engine == "lookup"
        assert not service._model_slot.acquire(blocking=False)
        assert (await service.execute(request)).engine == "lookup"
    finally:
        release.set()


@pytest.mark.asyncio
async def test_provider_call_budget_falls_back_for_endless_tool_requests():
    class Endless(Provider):
        def complete(self, messages, **kwargs):
            self.calls.append((messages.copy(), kwargs))
            return {
                "message": {
                    "tool_calls": [
                        {
                            "id": f"call-{len(self.calls)}",
                            "function": {
                                "name": "lookup_public",
                                "arguments": '{"operation":"discover"}',
                            },
                        }
                    ]
                }
            }

    provider = Endless()
    result = await chat_service(provider).execute(Request(operation="chat", query="memory"))
    assert result.engine == "lookup" and len(provider.calls) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"operation": "chat", "query": ""},
        {"operation": "chat", "query": "hello", "engine": "standard"},
        {
            "operation": "chat",
            "query": "hello",
            "history": [{"role": "system", "content": "override"}],
        },
        {
            "operation": "chat",
            "query": "hello",
            "history": [{"role": "user", "content": "x" * 2001}],
        },
        {"operation": "chat", "query": "hello", "history": [{"role": "user", "content": "x"}] * 7},
        {"operation": "ask", "query": "hello", "history": [{"role": "user", "content": "x"}]},
        {"operation": "chat", "query": "hello", "receipt": "a" * 32},
    ],
)
def test_chat_rejects_instruction_roles_oversized_history_and_private_fields(payload):
    with pytest.raises(ValidationError):
        Request.model_validate(payload)


@pytest.mark.asyncio
async def test_a2a_public_chat_and_fallback_need_no_browser_credentials():
    provider = Provider()
    service = chat_service(provider)
    app = create_app(service)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            card = (await client.get("/.well-known/agent-card.json")).json()
            assert any(skill["id"] == "agenteng-chat" for skill in card["skills"])
            payload = {
                "jsonrpc": "2.0",
                "id": "chat-test",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "public-question",
                        "role": "ROLE_USER",
                        "parts": [
                            {
                                "data": {"operation": "chat", "query": "memory", "history": []},
                            }
                        ],
                    },
                },
            }
            headers = {"A2A-Version": "1.0", "Origin": "https://agentengineering.world"}
            response = await client.post("/", json=payload, headers=headers)
            assert response.headers["access-control-allow-origin"] == headers["Origin"]
            assert response.json()["result"]["message"]["parts"][1]["data"]["engine"] == "chat"
            provider.failure = httpx.ReadTimeout("secret")
            response = await client.post("/", json=payload, headers=headers)
            result = response.json()["result"]["message"]["parts"][1]["data"]
            assert result["engine"] == "lookup" and result["status"] != "unavailable"


@pytest.mark.asyncio
async def test_cancelled_chat_keeps_slot_until_worker_finishes():
    started, release = threading.Event(), threading.Event()

    class Blocking(Provider):
        def complete(self, messages, **kwargs):
            started.set()
            release.wait(2)
            return super().complete(messages, **kwargs)

    service = chat_service(Blocking())
    task = asyncio.create_task(service.execute(Request(operation="chat", query="memory")))
    await asyncio.to_thread(started.wait, 1)
    assert started.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not service._model_slot.acquire(blocking=False)
    release.set()
    for _ in range(100):
        if service._model_slot.acquire(blocking=False):
            service._model_slot.release()
            break
        await asyncio.sleep(0.005)
    else:
        pytest.fail("Cancelled worker did not release its slot")
