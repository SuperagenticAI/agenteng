"""Small, reviewed public context for chat and its model-free fallback.

Protocol summaries are bundled paraphrases of the linked official introductions.
No runtime web, private catalogue, or model is needed to answer these basics.
"""

import re

from .models import Request, Source

PROTOCOLS = {
    "mcp": Source(
        id="protocol-mcp",
        url="https://modelcontextprotocol.io/docs/getting-started/intro",
        text="MCP (Model Context Protocol) connects AI applications to tools, data sources and external systems through a shared client/server interface.",
    ),
    "a2a": Source(
        id="protocol-a2a",
        url="https://a2a-protocol.org/latest/topics/what-is-a2a/",
        text="A2A (Agent2Agent) is a protocol for agents to discover each other, exchange messages and collaborate across frameworks or vendors. MCP connects an agent to tools; A2A connects agents to other agents.",
    ),
    "acp": Source(
        id="protocol-acp",
        url="https://agentclientprotocol.com/get-started/introduction",
        text="ACP (Agent Client Protocol) standardizes communication between coding agents and clients such as editors. A client can use the same interface to work with different compatible coding agents.",
    ),
}


def resolved_question(request):
    question = request.query
    if re.fullmatch(
        r"\s*(?:tell me more|more|go on|explain more|can you elaborate|please elaborate)[.!?\s]*",
        question,
        re.I,
    ):
        previous = next(
            (turn.content for turn in reversed(request.history) if turn.role == "user"), None
        )
        if previous:
            return previous
    return question


def chat_fallback(service, request):
    question = resolved_question(request)
    if re.fullmatch(
        r"\s*(?:hi|hello|hey|good (?:morning|afternoon|evening)|thanks|thank you)[.!?\s]*",
        question,
        re.I,
    ):
        return service.result(
            "Hi! I'm AgentEng. Ask me about the events, speakers, or agent engineering tools. What would you like to explore?"
        )
    protocols = list(dict.fromkeys(re.findall(r"\b(?:mcp|a2a|acp)\b", question.casefold())))
    definition = re.search(
        r"\b(?:what(?:'s| is| are)|explain|mean|difference|compare|tell me about|understand)\b",
        question,
        re.I,
    )
    event_or_tools = re.search(
        r"\b(?:speakers?|talks?|agenda|schedule|tickets?|price|tools?|libraries|frameworks|conference)\b",
        question,
        re.I,
    )
    if (
        protocols
        and not event_or_tools
        and (definition or question.strip().casefold() in PROTOCOLS)
    ):
        sources = [PROTOCOLS[name] for name in protocols]
        return service.result("\n\n".join(source.text for source in sources)).model_copy(
            update={"sources": sources}
        )
    result = service.lookup(Request(operation="ask", query=question, limit=request.limit))
    return result


def cited_data(candidates, source_ids):
    """Choose cards from the lookup actually cited, not an unrelated last tool call."""
    chosen = set(source_ids)
    matching = [
        (len(chosen & ids), index, data)
        for index, (ids, data) in enumerate(candidates)
        if chosen & ids
    ]
    return max(matching, key=lambda item: item[:2])[2] if matching else {}
