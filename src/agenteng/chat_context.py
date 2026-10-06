"""Small, reviewed public context for chat and its model-free fallback.

Protocol summaries are bundled paraphrases of the linked official introductions.
No runtime web, private catalogue, or model is needed to answer these basics.
"""

import re

from .models import Request, Source

PROTOCOLS = {
    "cli": Source(
        id="protocol-cli",
        url="https://docs.agentengineering.world/COMMANDS/",
        text="CLI means command-line interface. The AgentEng CLI lets you explore public events, speakers, agendas and agent engineering tools from your terminal.",
    ),
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

TOOLING = Source(
    id="agenteng-tooling",
    url="https://docs.agentengineering.world/INTEGRATIONS/",
    text="AgentEng combines Agent Engineering events with open-source agent infrastructure: a CLI, MCP tools, an A2A agent and optional ACP coding-agent integration. Install it with curl -fsSL https://agentengineering.world/install.sh | sh. Run agenteng connect cursor, agenteng connect codex or agenteng connect claude-code for MCP setup.",
)


def attendance_question(question):
    """FAQ is an attendance resource, never a general chat search."""
    return bool(
        re.search(
            r"\b(?:faq|attend(?:ing|ance)?|tickets?|refunds?|invoices?|transfer|approval|"
            r"approved|registration|register|accessible|accessibility|wheelchair|dietary|"
            r"food|lunch|drinks?|catering|cancel(?:led|lation)?|conduct|dress|seats?)\b",
            question,
            re.I,
        )
    )


def focused_search(service, question, limit, *, allow_faq=None):
    """Ignore conversational filler and require meaningful overlap with a source."""
    from .service import terms

    if allow_faq is None:
        allow_faq = attendance_question(question)
    filler = {
        "you",
        "your",
        "yours",
        "we",
        "our",
        "they",
        "their",
        "it",
        "its",
        "do",
        "have",
        "has",
        "to",
        "be",
        "in",
        "on",
        "at",
        "from",
        "an",
        "as",
        "by",
        "am",
        "my",
        "would",
        "could",
        "should",
        "will",
        "want",
        "need",
        "know",
        "help",
        "explain",
        "understand",
        "give",
        "get",
        "some",
        "any",
        "more",
        "there",
    }
    wanted = terms(question) - filler
    minimum = max(1, len(wanted) // 2 + 1)
    ranked = sorted(
        (
            (len(wanted & terms(source.text)), source)
            for source in service.catalogue.sources
            if allow_faq or source.kind not in {"faq", "conduct", "tickets"}
        ),
        key=lambda item: (-item[0], item[1].id),
    )
    matches = [source for score, source in ranked if score >= minimum][: min(limit, 2)]
    if not wanted or not matches:
        return service.result(
            "I don't have enough public information to answer that yet. Ask me about AgentEng, the events, or agent engineering tools, or add a little more detail.",
            status="not_found",
        )
    return service.result("\n\n".join(source.text[:900] for source in matches)).model_copy(
        update={"sources": matches}
    )


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
    plain = question.casefold().replace("’", "'").strip(" .!?\n\t")
    if re.fullmatch(
        r"(?:hi|hello|hey)(?: there| agenteng)?(?:[,!] ?)?(?: how are you)?", plain
    ) or plain in {
        "how are you",
        "how are you doing",
        "how's it going",
        "what's up",
        "good morning",
        "good afternoon",
        "good evening",
    }:
        return service.result(
            "Hey! I'm ready to help. Want to explore AgentEng, the events, or building with MCP, A2A and ACP?"
            if "how" in plain or "what's up" in plain
            else "Hi! I'm AgentEng. Ask me about the events, speakers, or agent engineering tools. What would you like to explore?"
        )
    if plain in {"thanks", "thank you", "thank you very much", "great", "cool", "ok", "okay"}:
        return service.result("You're welcome! What would you like to explore next?")
    if re.fullmatch(
        r"(?:who are you|what (?:are you|can you do)|help|(?:what(?:'s| is) |tell me about )agenteng)",
        plain,
    ):
        return service.result(
            "I'm AgentEng, your guide to Agent Engineering events and open-source agent infrastructure. Explore speakers, talks and agendas, or build with our CLI, MCP, A2A and ACP tooling. What are you working on?"
        ).model_copy(update={"sources": [TOOLING]})
    if re.fullmatch(r"(?:what(?:'s| is) |explain |tell me about )agent engineering", plain):
        about = service.catalogue.about
        if about and about.definition:
            return service.result(about.definition, source_ids=about.source_ids)
    if re.search(r"\b(?:install|installation|connect|setup|set up)\b", plain) and re.search(
        r"\b(?:agenteng|mcp|a2a|acp)\b", plain
    ):
        origin = service.settings.public_url
        return service.result(
            TOOLING.text
            + f" The public A2A endpoint is {origin} and the remote MCP endpoint is {origin}/mcp/."
        ).model_copy(update={"sources": [TOOLING]})
    protocols = list(dict.fromkeys(re.findall(r"\b(?:mcp|a2a|acp|cli)\b", plain)))
    definition = re.search(
        r"\b(?:what(?:'s| is| are)|explain|mean|difference|compare|tell me about|understand|how .*works?)\b",
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
    if result.answer.startswith(("Published source excerpts", "No published sources")):
        return focused_search(service, question, request.limit)
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
