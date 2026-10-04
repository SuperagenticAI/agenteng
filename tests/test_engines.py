import json
import threading
import time
from collections import deque
from dataclasses import replace

import pytest

from agenteng.config import Settings
from agenteng.engines import Budget, HTTPProvider, run_engine
from agenteng.models import Request, Source
from agenteng.service import Service

SOURCES = [
    Source(
        id="memory",
        url="https://agentengineering.world/agenda",
        text="Memory systems use retrieval.",
    ),
    Source(
        id="eval",
        url="https://agentengineering.world/agenda",
        text="Evaluation uses regression checks.",
    ),
]
SETTINGS = Settings(max_reserved_tokens=60000, request_timeout=15)


def final(ids=None, answer="Published evidence."):
    return {
        "content": json.dumps({"answer": answer, "source_ids": ["memory"] if ids is None else ids})
    }


def code(value):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "code-1",
                "type": "function",
                "function": {"name": "run_code", "arguments": json.dumps({"code": value})},
            }
        ],
    }


class ScriptedProvider:
    def __init__(self, messages):
        self.messages = deque(messages)
        self.calls = []

    def complete(self, messages, **kwargs):
        self.calls.append((messages.copy(), kwargs))
        return {"message": self.messages.popleft(), "usage": {"total_tokens": 10}}


def run(messages, engine="rlm", settings=SETTINGS):
    provider = ScriptedProvider(messages)
    result = run_engine(
        Request(operation="ask", query="Compare memory and eval", engine=engine),
        SOURCES,
        settings,
        provider,
        threading.Event(),
    )
    return result, provider


def test_standard_is_one_call():
    result, provider = run([final()], "standard")
    assert len(provider.calls) == 1
    assert result["usage"]["model_calls"] == 1
    assert result["usage"]["delegations"] == 0


def test_real_monty_root_single_child():
    result, provider = run(
        [
            code("finding = rlm.run('Extract memory', ['memory'])"),
            code("ctx.read('memory')"),
            final(),
            final(),
        ]
    )
    assert result["usage"]["delegations"] == 1
    assert result["usage"]["model_calls"] == 4
    assert result["usage"]["total_tokens"] == 40
    assert len(provider.calls) == 4
    # Child manifest is scoped; the model receives no unrelated eval source.
    assert '"source_id": "eval"' not in provider.calls[1][0][1]["content"]
    assert provider.calls[0][1]["tools"][0]["function"]["name"] == "run_code"


def test_real_monty_persistent_variables():
    result, provider = run([code("x = 40"), code("x + 2"), final()])
    assert provider.calls[2][0][-1]["content"] == "42"
    assert result["usage"]["delegations"] == 0


def test_leaf_uses_single_delegation():
    result, _ = run([code("llm_query('Extract', ['memory'])"), final(), final()])
    assert result["usage"]["model_calls"] == 3
    assert result["usage"]["delegations"] == 1


@pytest.mark.parametrize(
    "root,child",
    [
        ("rlm.run('Extract', ['memory'])", "rlm.run('Again', ['memory'])"),
        ("rlm.run('Extract', ['memory'])", "llm_query('Again', ['memory'])"),
        ("rlm.run('Extract', ['memory'])", "ctx.read('eval')"),
    ],
)
def test_child_cannot_delegate_or_expand_read_scope(root, child):
    with pytest.raises(Exception):
        run([code(root), code(child)])


@pytest.mark.parametrize(
    "program",
    [
        "open('/etc/passwd').read()",
        "import os\nos.environ",
        "rlm.run('Read', ['missing'])",
        "while True:\n    pass",
        "'x' * 20000000",
    ],
)
def test_sandbox_and_invalid_scope_fail_closed(program):
    with pytest.raises(Exception):
        run([code(program)])


def test_child_and_leaf_share_allowance():
    with pytest.raises(Exception):
        run(
            [code("rlm.run('Extract', ['memory'])"), final(), code("llm_query('More', ['memory'])")]
        )
    with pytest.raises(Exception):
        run(
            [code("llm_query('Extract', ['memory'])"), final(), code("rlm.run('More', ['memory'])")]
        )


def test_failed_delegation_is_not_refunded():
    budget = Budget(SETTINGS, threading.Event())
    with pytest.raises(ValueError, match="subset"):
        budget.delegate(0, ["missing"], {"memory"})
    assert budget.delegations == 1
    with pytest.raises(ValueError, match="one delegation"):
        budget.delegate(0, ["memory"], {"memory"})


@pytest.mark.parametrize("engine", ["standard", "rlm"])
def test_invented_citations_rejected(engine):
    with pytest.raises(ValueError, match="Unknown source"):
        run([final(["invented"])], engine)


def test_reserved_tokens_and_calls_are_shared():
    with pytest.raises(ValueError, match="budget"):
        run(
            [code("rlm.run('Extract', ['memory'])"), final(), final()],
            settings=replace(SETTINGS, max_model_calls=2),
        )
    with pytest.raises(ValueError, match="budget"):
        run([final()], "standard", replace(SETTINGS, max_reserved_tokens=10))
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(TimeoutError):
        Budget(SETTINGS, cancelled).remaining()


@pytest.mark.asyncio
async def test_service_authorized_engine_and_sanitized_error():
    s = Service(
        replace(SETTINGS, enable_standard=True, operator_token="operator"),
        provider=ScriptedProvider([final(["invented"])]),
    )
    result = await s.execute(
        Request(operation="ask", query="memory", engine="standard"), token="operator"
    )
    assert result.status == "unavailable"
    assert "invented" not in result.answer


def test_provider_wire_contract(monkeypatch):
    import httpx

    captured = {}

    def handle(request):
        captured["body"] = json.loads(request.content)
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": final(), "finish_reason": "stop"}],
                "usage": {"total_tokens": 12},
            },
        )

    original = httpx.Client
    monkeypatch.setattr(
        "agenteng.engines.httpx.Client",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    provider = HTTPProvider(replace(SETTINGS, model="operator-chosen-model", model_api_key="fake"))
    result = provider.complete(
        [{"role": "user", "content": "question"}], tools=None, max_tokens=100, timeout=1
    )
    assert result["usage"]["total_tokens"] == 12
    assert captured["body"]["max_completion_tokens"] == 100
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["authorization"] == "Bearer fake"


@pytest.mark.asyncio
async def test_deadline_blocks_further_provider_calls():
    class SlowProvider:
        calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            time.sleep(0.12)
            return {"message": final(), "usage": {}}

    provider = SlowProvider()
    settings = replace(
        SETTINGS, request_timeout=0.03, enable_standard=True, operator_token="operator"
    )
    service = Service(settings, provider=provider)
    request = Request(operation="ask", query="memory", engine="standard")
    assert (await service.execute(request, token="operator")).status == "unavailable"
    assert service._model_slot.locked()
    assert "busy" in (await service.execute(request, token="operator")).answer
    import asyncio

    await asyncio.sleep(0.15)
    assert not service._model_slot.locked() and provider.calls == 1
